"""
Scheduler Service — APScheduler
────────────────────────────────
Every MONITORING_INTERVAL_SECONDS (default 5 min):
  For each active session with a camera:
    1. Grab latest frame from camera
    2. For each student in watch list:
       - Run face recognition on frame
       - If found → update last_seen_at
       - If missing > 15 min → admin panel alert (bell) + optionally email warn
       - If missing > 20 min → send alert email to recipients (once)
       - Update attendance record

Camera health check every 60 seconds.
Daily report at configured time.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import (
    Alert, AlertType, AlertSeverity,
    Attendance, AttendanceStatus,
    Camera, CameraStatus,
    ClassSession, SessionWatchList,
    AlertRecipient,
)

log = logging.getLogger("smartattend.scheduler")

scheduler = AsyncIOScheduler()

# WebSocket broadcast function (set by main.py)
_broadcast_fn = None


def set_broadcast_fn(fn):
    global _broadcast_fn
    _broadcast_fn = fn


async def _broadcast(msg: dict):
    if _broadcast_fn:
        try:
            await _broadcast_fn(msg)
        except Exception as e:
            log.debug("Broadcast error: %s", e)


# ── Camera Health Check ───────────────────────────────────────────────────────

async def check_camera_health():
    from app.services.camera_service import get_all_stream_status
    statuses = get_all_stream_status()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Camera).where(Camera.is_active == True))
        cameras = result.scalars().all()

        for cam in cameras:
            stream_st = statuses.get(cam.rtsp_url, {})
            is_online = stream_st.get("online", False)
            last_seen_str = stream_st.get("last_seen")
            last_seen = datetime.fromisoformat(last_seen_str) if last_seen_str else None

            new_status = CameraStatus.ONLINE if is_online else CameraStatus.OFFLINE
            prev_status = cam.status

            cam.status = new_status
            if last_seen:
                cam.last_seen = last_seen

            # Alert on transition to offline
            if prev_status == CameraStatus.ONLINE and new_status == CameraStatus.OFFLINE:
                alert = Alert(
                    type=AlertType.CAMERA_OFFLINE,
                    severity=AlertSeverity.WARNING,
                    message=f"Camera '{cam.name}' ({cam.location}) has gone offline.",
                )
                db.add(alert)
                await _broadcast({"type": "camera_offline", "camera_id": cam.id, "name": cam.name})

            elif prev_status != CameraStatus.ONLINE and new_status == CameraStatus.ONLINE:
                alert = Alert(
                    type=AlertType.CAMERA_RECONNECTED,
                    severity=AlertSeverity.INFO,
                    message=f"Camera '{cam.name}' ({cam.location}) is back online.",
                )
                db.add(alert)
                await _broadcast({"type": "camera_online", "camera_id": cam.id, "name": cam.name})

        await db.commit()


# ── Main Monitoring Job ───────────────────────────────────────────────────────

async def monitor_classrooms():
    from app.services.camera_service import get_latest_frame, save_snapshot
    from app.services.face_service import recognize_face_from_frame
    from app.services.email_service import send_missing_15_alert, send_missing_20_alert

    log.info("Running classroom monitoring scan...")

    async with AsyncSessionLocal() as db:
        # Get all active sessions with a camera assigned
        result = await db.execute(
            select(ClassSession)
            .where(ClassSession.ended_at == None)  # noqa: E711
        )
        sessions = result.scalars().all()

        for session in sessions:
            if not session.camera_id:
                continue

            # Get camera
            cam_result = await db.execute(select(Camera).where(Camera.id == session.camera_id))
            camera = cam_result.scalar_one_or_none()
            if not camera or not camera.is_active:
                continue

            frame = get_latest_frame(camera.rtsp_url)
            if frame is None:
                log.warning("No frame for camera %s (session %d)", camera.name, session.id)
                continue

            # Get active watch list for this session
            wl_result = await db.execute(
                select(SessionWatchList)
                .where(
                    SessionWatchList.session_id == session.id,
                    SessionWatchList.is_active == True,
                )
            )
            watch_entries = wl_result.scalars().all()

            if not watch_entries:
                continue

            # Run recognition on frame once per session
            recog = await recognize_face_from_frame(frame, db, batch_filter=session.batch)
            found_db_id: Optional[int] = recog.get("_db_id") if recog.get("matched") else None

            now = datetime.utcnow()

            for entry in watch_entries:
                student_matched = (found_db_id == entry.student_id)

                if student_matched:
                    # Update last seen
                    entry.last_seen_at = now
                    # Update attendance to present
                    att_result = await db.execute(
                        select(Attendance)
                        .where(
                            Attendance.student_id == entry.student_id,
                            Attendance.session_id == session.id,
                        )
                    )
                    att = att_result.scalar_one_or_none()
                    if att and att.status != AttendanceStatus.PRESENT:
                        att.status = AttendanceStatus.PRESENT
                        att.marked_at = now
                        att.confidence = recog.get("confidence")
                        att.source = "camera"
                    continue

                # Student NOT seen in this frame — check missing duration
                last_seen = entry.last_seen_at or entry.checked_in_at
                missing_minutes = (now - last_seen).total_seconds() / 60

                # Get recipients from DB
                rec_result = await db.execute(
                    select(AlertRecipient).where(AlertRecipient.is_active == True)
                )
                recipients_db = [r.email for r in rec_result.scalars().all()]
                recipients = recipients_db or settings.alert_recipients_list

                # Get student info
                from app.models import Student, Admin
                stu_result = await db.execute(select(Student).where(Student.id == entry.student_id))
                student = stu_result.scalar_one_or_none()
                teacher_result = await db.execute(select(Admin).where(Admin.id == session.teacher_id))
                teacher = teacher_result.scalar_one_or_none()

                if not student:
                    continue

                checked_in_str = entry.checked_in_at.strftime("%H:%M:%S")
                last_seen_str = last_seen.strftime("%H:%M:%S")
                room_str = session.room or camera.location or "—"
                teacher_str = teacher.name if teacher else "—"

                # 15-min warning (panel alert + optional email)
                if missing_minutes >= settings.ABSENT_WARN_MINUTES and not entry.warn_15_sent:
                    entry.warn_15_sent = True
                    snap_path = save_snapshot(frame, prefix=f"warn15_{student.student_id}", snapshots_dir=settings.SNAPSHOTS_DIR)

                    alert = Alert(
                        teacher_id=session.teacher_id,
                        session_id=session.id,
                        student_id=student.id,
                        type=AlertType.STUDENT_MISSING_15,
                        severity=AlertSeverity.WARNING,
                        message=f"{student.name} ({student.student_id}) has not been seen for {int(missing_minutes)} minutes in {session.subject}.",
                        snapshot_path=snap_path,
                    )
                    db.add(alert)
                    await db.flush()

                    await _broadcast({
                        "type":         "alert",
                        "alert_type":   "student_missing_15",
                        "severity":     "warning",
                        "student_name": student.name,
                        "student_id":   student.student_id,
                        "session":      session.subject,
                        "minutes":      int(missing_minutes),
                        "alert_id":     alert.id,
                        "play_bell":    True,
                    })

                    log.warning("15-min alert: %s in session %s", student.name, session.subject)

                # 20-min email alert
                if missing_minutes >= settings.ABSENT_EMAIL_MINUTES and not entry.email_20_sent:
                    entry.email_20_sent = True
                    snap_path = save_snapshot(frame, prefix=f"absent20_{student.student_id}", snapshots_dir=settings.SNAPSHOTS_DIR)

                    alert = Alert(
                        teacher_id=session.teacher_id,
                        session_id=session.id,
                        student_id=student.id,
                        type=AlertType.STUDENT_MISSING_20,
                        severity=AlertSeverity.URGENT,
                        message=f"URGENT: {student.name} ({student.student_id}) absent 20+ min from {session.subject}.",
                        snapshot_path=snap_path,
                        email_sent=True,
                    )
                    db.add(alert)
                    await db.flush()

                    await _broadcast({
                        "type":         "alert",
                        "alert_type":   "student_missing_20",
                        "severity":     "urgent",
                        "student_name": student.name,
                        "student_id":   student.student_id,
                        "session":      session.subject,
                        "minutes":      int(missing_minutes),
                        "alert_id":     alert.id,
                        "play_bell":    True,
                    })

                    # Send email async (don't block monitoring)
                    import asyncio
                    asyncio.create_task(send_missing_20_alert(
                        recipients=recipients,
                        student_name=student.name,
                        student_id=student.student_id,
                        session=session.subject,
                        room=room_str,
                        teacher=teacher_str,
                        checked_in=checked_in_str,
                        last_seen=last_seen_str,
                    ))

                    log.warning("20-min email alert: %s in session %s", student.name, session.subject)

        await db.commit()
    log.info("Monitoring scan complete.")


# ── Daily Report ──────────────────────────────────────────────────────────────

async def send_daily_report():
    from app.services.email_service import send_daily_report as _send_report
    from app.models import Attendance, ClassSession
    from datetime import date

    today = date.today()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ClassSession).where(
                ClassSession.started_at >= datetime.combine(today, datetime.min.time())
            )
        )
        sessions = result.scalars().all()

        rows = []
        for s in sessions:
            att_result = await db.execute(
                select(Attendance).where(Attendance.session_id == s.id)
            )
            atts = att_result.scalars().all()
            total = len(atts)
            present = sum(1 for a in atts if a.status == AttendanceStatus.PRESENT)
            absent = total - present
            rows.append({
                "subject":    s.subject,
                "batch":      s.batch,
                "total":      total,
                "present":    present,
                "absent":     absent,
                "percentage": (present / total * 100) if total else 0,
            })

        recipients = settings.report_recipients_list
        if recipients and rows:
            await _send_report(recipients, today.strftime("%B %d, %Y"), rows)


# ── Scheduler Setup ───────────────────────────────────────────────────────────

def start_scheduler():
    scheduler.add_job(
        monitor_classrooms,
        "interval",
        seconds=settings.MONITORING_INTERVAL_SECONDS,
        id="monitor_classrooms",
        replace_existing=True,
        misfire_grace_time=30,
    )
    scheduler.add_job(
        check_camera_health,
        "interval",
        seconds=60,
        id="camera_health",
        replace_existing=True,
    )

    # Daily report at configured time
    try:
        hour, minute = map(int, settings.DAILY_REPORT_TIME.split(":"))
        scheduler.add_job(
            send_daily_report,
            "cron",
            hour=hour,
            minute=minute,
            id="daily_report",
            replace_existing=True,
        )
    except Exception:
        pass

    scheduler.start()
    log.info("Scheduler started — monitoring every %ds", settings.MONITORING_INTERVAL_SECONDS)


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
