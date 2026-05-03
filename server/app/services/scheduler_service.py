"""
Scheduler Service
─────────────────
Jobs:
1. classroom_monitor_job  — every MONITORING_INTERVAL seconds
   • For each active session with a camera:
     - Grab frame
     - Run face recognition against checked-in students
     - Update AbsentTracking: reset timer if seen, increment if not
     - Trigger warning (15 min) → in-app bell + alert
     - Trigger email (20 min) → send to configured addresses
   
2. camera_health_job — every 60 seconds
   • Update camera online/offline status in DB

3. daily_attendance_report — cron at DAILY_REPORT_TIME
"""

import asyncio
import json
import logging
import numpy as np
from datetime import datetime, date
from typing import List, Tuple, Dict

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, func, update

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import (
    Attendance, AttendanceStatus, Alert, AlertType, AlertSeverity,
    ClassSession, Student, FaceEmbedding, AbsentTracking,
    Camera, CameraStatus, Teacher,
)
from app.services import camera_service, face_service, email_service

log = logging.getLogger("smartattend.scheduler")
scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

# Used to broadcast WebSocket alerts — set by main.py
_ws_broadcast_fn = None


def set_broadcast_fn(fn):
    global _ws_broadcast_fn
    _ws_broadcast_fn = fn


async def _broadcast(alert):
    if _ws_broadcast_fn:
        try:
            await _ws_broadcast_fn(alert)
        except Exception as e:
            log.warning("WebSocket broadcast failed: %s", e)


# ── Classroom Monitor ─────────────────────────────────────────────────────────

async def classroom_monitor_job():
    """
    For each active session with a camera:
    1. Load embeddings of all checked-in students for that batch
    2. Grab frame from camera
    3. Run face recognition
    4. Update AbsentTracking per student
    5. Fire alerts if thresholds exceeded
    """
    async with AsyncSessionLocal() as db:
        # Get active sessions (not ended) with a camera
        result = await db.execute(
            select(ClassSession, Camera, Teacher)
            .join(Camera, ClassSession.camera_id == Camera.id)
            .join(Teacher, ClassSession.teacher_id == Teacher.id)
            .where(
                ClassSession.ended_at.is_(None),
                ClassSession.camera_id.isnot(None),
                Camera.is_active == True,
            )
        )
        sessions = result.all()

        for session, camera, teacher in sessions:
            await _process_session(db, session, camera, teacher)

        await db.commit()


async def _process_session(db, session, camera, teacher):
    """Process one session's monitoring cycle."""
    cam_id = camera.id

    # Grab latest frame
    frame = camera_service.get_latest_frame(cam_id)
    if frame is None:
        status = camera_service.get_camera_status(cam_id)
        if status == "offline":
            await _create_alert(
                db,
                teacher_id=teacher.id,
                session_id=session.id,
                alert_type=AlertType.CAMERA_OFFLINE,
                severity=AlertSeverity.WARNING,
                message=f"Camera '{camera.name}' is offline for session: {session.subject} ({session.batch}).",
            )
        return

    # Load all embeddings for checked-in students in this batch
    checkin_result = await db.execute(
        select(AbsentTracking, Student)
        .join(Student, AbsentTracking.student_id == Student.id)
        .where(
            AbsentTracking.session_id == session.id,
            AbsentTracking.is_active == True,
        )
    )
    tracked = checkin_result.all()

    if not tracked:
        return  # nobody checked in yet

    # Build embedding cache for this session's students
    student_ids = [t.student_id for t, _ in tracked]
    emb_result = await db.execute(
        select(FaceEmbedding).where(FaceEmbedding.student_id.in_(student_ids))
    )
    embeddings = emb_result.scalars().all()

    # Group: student_db_id → list of embedding vectors
    emb_map: Dict[int, List[np.ndarray]] = {}
    for fe in embeddings:
        emb_map.setdefault(fe.student_id, []).append(fe.get_vector())

    # Average embeddings per student for faster comparison
    avg_embs: List[Tuple[int, np.ndarray]] = []
    for sid, vecs in emb_map.items():
        avg = np.mean(vecs, axis=0)
        avg = avg / (np.linalg.norm(avg) + 1e-9)
        avg_embs.append((sid, avg))

    # Run face recognition on current frame
    seen_student_id, _ = face_service.recognize_face_sync(frame, avg_embs)

    now = datetime.utcnow()

    for tracking, student in tracked:
        if seen_student_id == tracking.student_id:
            # Student spotted — reset absence timer
            tracking.last_seen_at = now
            tracking.consecutive_absent_seconds = 0
            tracking.warning_sent = False  # reset so re-alert if they disappear again
            # Don't reset email_sent — avoid spam
        else:
            # Student NOT spotted — increment timer
            tracking.consecutive_absent_seconds += settings.MONITORING_INTERVAL

            absent_secs = tracking.consecutive_absent_seconds
            absent_mins = absent_secs // 60

            # ── 15-min warning (in-app bell) ────────────────────────────────
            if absent_secs >= settings.ABSENT_WARNING_SECONDS and not tracking.warning_sent:
                tracking.warning_sent = True
                snap_path = camera_service.save_snapshot(
                    frame, prefix=f"absent_{student.student_id}"
                )
                alert = await _create_alert(
                    db,
                    teacher_id=teacher.id,
                    session_id=session.id,
                    student_id=student.id,
                    alert_type=AlertType.STUDENT_ABSENT_WARNING,
                    severity=AlertSeverity.WARNING,
                    message=(
                        f"{student.name} ({student.student_id}) has been absent "
                        f"from {session.subject} for {absent_mins} minutes."
                    ),
                    snapshot_path=snap_path,
                )
                log.info("15-min warning for %s in session %s", student.name, session.id)

            # ── 20-min email alert ─────────────────────────────────────────
            if absent_secs >= settings.ABSENT_EMAIL_SECONDS and not tracking.email_sent:
                tracking.email_sent = True
                asyncio.create_task(
                    email_service.send_absence_warning(
                        student_name=student.name,
                        student_id=student.student_id,
                        subject=session.subject,
                        room=session.room or "",
                        batch=session.batch,
                        absent_minutes=absent_mins,
                        teacher_name=teacher.name,
                    )
                )
                log.info("20-min email sent for %s", student.name)


async def _create_alert(
    db,
    teacher_id: int,
    session_id: int,
    alert_type: AlertType,
    severity: AlertSeverity,
    message: str,
    student_id: int = None,
    snapshot_path: str = None,
) -> Alert:
    alert = Alert(
        teacher_id=teacher_id,
        session_id=session_id,
        student_id=student_id,
        type=alert_type,
        severity=severity,
        message=message,
        snapshot_path=snapshot_path,
    )
    db.add(alert)
    await db.flush()  # get ID
    await _broadcast(alert)
    return alert


# ── Camera Health ──────────────────────────────────────────────────────────────

async def camera_health_job():
    """Sync in-memory camera status to the database."""
    statuses = camera_service.get_all_statuses()
    async with AsyncSessionLocal() as db:
        for cam_id, status_str in statuses.items():
            cam = await db.get(Camera, cam_id)
            if cam:
                new_status = {
                    "online": CameraStatus.ONLINE,
                    "offline": CameraStatus.OFFLINE,
                }.get(status_str, CameraStatus.UNKNOWN)
                cam.status = new_status
                if status_str == "online":
                    cam.last_seen = datetime.utcnow()
                    # Save snapshot for admin panel preview
                    frame = camera_service.get_latest_frame(cam_id)
                    if frame is not None:
                        snap = camera_service.save_snapshot(frame, prefix=f"cam_{cam_id}_preview")
                        cam.snapshot_path = snap
        await db.commit()


# ── Daily Report ───────────────────────────────────────────────────────────────

async def daily_attendance_report():
    today = date.today()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(
                ClassSession.subject,
                ClassSession.batch,
                func.count(Attendance.id).label("total"),
                func.sum(
                    (Attendance.status == AttendanceStatus.PRESENT).cast(int)
                ).label("present"),
            )
            .join(Attendance, Attendance.session_id == ClassSession.id)
            .where(Attendance.date == today)
            .group_by(ClassSession.subject, ClassSession.batch)
        )
        rows = [
            {"subject": r.subject, "batch": r.batch, "total": r.total or 0, "present": r.present or 0}
            for r in result.all()
        ]

    if rows:
        await email_service.send_daily_report(rows, today.isoformat())
    log.info("Daily report processed. %d sessions.", len(rows))


# ── Startup / Shutdown ────────────────────────────────────────────────────────

async def _start_active_cameras():
    """On startup, start stream threads for all active cameras in DB."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Camera).where(Camera.is_active == True)
        )
        cameras = result.scalars().all()
        for cam in cameras:
            camera_service.start_camera(cam.id, cam.rtsp_url)
            log.info("Auto-started camera: %s (%s)", cam.name, cam.rtsp_url)


def start_scheduler():
    hour, minute = settings.DAILY_REPORT_TIME.split(":")

    scheduler.add_job(
        classroom_monitor_job,
        trigger=IntervalTrigger(seconds=settings.MONITORING_INTERVAL),
        id="classroom_monitor",
        replace_existing=True,
        misfire_grace_time=30,
    )
    scheduler.add_job(
        camera_health_job,
        trigger=IntervalTrigger(seconds=60),
        id="camera_health",
        replace_existing=True,
    )
    scheduler.add_job(
        daily_attendance_report,
        trigger=CronTrigger(hour=int(hour), minute=int(minute)),
        id="daily_report",
        replace_existing=True,
    )
    scheduler.start()

    # Start camera streams (non-blocking)
    asyncio.get_event_loop().create_task(_start_active_cameras())
    log.info("Scheduler started.")


def stop_scheduler():
    scheduler.shutdown(wait=False)
    camera_service.stop_all_cameras()
