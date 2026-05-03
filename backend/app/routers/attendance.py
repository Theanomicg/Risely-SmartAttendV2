"""
Attendance Router
─────────────────
• Session management (start/end)
• Kiosk face check-in (adds student to watch list)
• Manual attendance overrides
• Watch list management
• Attendance reports
"""

from datetime import datetime, date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.models import (
    Admin, Student, Camera, ClassSession, SessionWatchList,
    Attendance, AttendanceStatus, Alert, AlertType, AlertSeverity,
)
from app.schemas import (
    SessionCreate, SessionOut, AttendanceOut, AttendanceSummary,
    KioskCheckIn, RecognitionResult, ManualAttendanceUpdate, WatchListOut,
)
from app.deps import get_current_admin, require_kiosk_key
from app.services import face_service
from app.config import settings

router = APIRouter(prefix="/attendance", tags=["Attendance"])


# ── Sessions ──────────────────────────────────────────────────────────────────

@router.post("/sessions", response_model=SessionOut, status_code=201)
async def start_session(
    req: SessionCreate,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    session = ClassSession(
        teacher_id=admin.id,
        camera_id=req.camera_id,
        subject=req.subject,
        batch=req.batch,
        room=req.room,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return SessionOut(
        id=session.id, subject=session.subject, batch=session.batch,
        room=session.room, camera_id=session.camera_id,
        started_at=session.started_at, ended_at=session.ended_at,
        teacher_name=admin.name,
    )


@router.get("/sessions", response_model=List[SessionOut])
async def list_sessions(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    q = select(ClassSession, Admin).join(Admin, ClassSession.teacher_id == Admin.id)
    if active_only:
        q = q.where(ClassSession.ended_at == None)  # noqa: E711
    q = q.order_by(ClassSession.started_at.desc()).limit(100)
    result = await db.execute(q)
    rows = result.all()
    return [
        SessionOut(
            id=s.id, subject=s.subject, batch=s.batch, room=s.room,
            camera_id=s.camera_id, started_at=s.started_at, ended_at=s.ended_at,
            teacher_name=a.name,
        )
        for s, a in rows
    ]


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session(session_id: int, db: AsyncSession = Depends(get_db),
                      _: Admin = Depends(get_current_admin)):
    result = await db.execute(
        select(ClassSession, Admin).join(Admin, ClassSession.teacher_id == Admin.id)
        .where(ClassSession.id == session_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(404, "Session not found.")
    s, a = row
    return SessionOut(
        id=s.id, subject=s.subject, batch=s.batch, room=s.room,
        camera_id=s.camera_id, started_at=s.started_at, ended_at=s.ended_at,
        teacher_name=a.name,
    )


@router.post("/sessions/{session_id}/end")
async def end_session(session_id: int, db: AsyncSession = Depends(get_db),
                      _: Admin = Depends(get_current_admin)):
    result = await db.execute(select(ClassSession).where(ClassSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found.")
    if session.ended_at:
        raise HTTPException(400, "Session already ended.")

    session.ended_at = datetime.utcnow()

    # Deactivate all watch list entries
    wl_result = await db.execute(
        select(SessionWatchList).where(
            SessionWatchList.session_id == session_id,
            SessionWatchList.is_active == True,
        )
    )
    for entry in wl_result.scalars().all():
        entry.is_active = False

    await db.commit()
    return {"ok": True, "ended_at": session.ended_at}


# ── Kiosk Check-In ────────────────────────────────────────────────────────────

@router.post("/kiosk/check-in", response_model=RecognitionResult)
async def kiosk_check_in(
    req: KioskCheckIn,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_kiosk_key),
):
    """
    Called by kiosk when student scans face.
    1. Recognises face
    2. Looks up active session
    3. Adds student to watch list
    4. Creates attendance record
    """
    # Get session
    sess_result = await db.execute(select(ClassSession).where(ClassSession.id == req.session_id))
    session = sess_result.scalar_one_or_none()
    if not session or session.ended_at:
        raise HTTPException(400, "Session not found or already ended.")

    # Face recognition
    recog = await face_service.recognize_face(req.image_b64, db, batch_filter=session.batch)
    if not recog["matched"]:
        return RecognitionResult(matched=False, message=recog["message"],
                                 confidence=recog.get("confidence"))

    # Get student
    stu_result = await db.execute(select(Student).where(Student.student_id == recog["student_id"]))
    student = stu_result.scalar_one_or_none()
    if not student:
        return RecognitionResult(matched=False, message="Student record not found.")

    now = datetime.utcnow()

    # Check if already in watch list
    wl_result = await db.execute(
        select(SessionWatchList).where(
            SessionWatchList.session_id == session.id,
            SessionWatchList.student_id == student.id,
        )
    )
    existing_wl = wl_result.scalar_one_or_none()

    if existing_wl:
        if not existing_wl.is_active:
            # Student left and came back
            existing_wl.is_active = True
            existing_wl.checked_in_at = now
            existing_wl.last_seen_at = now
            existing_wl.warn_15_sent = False
            existing_wl.email_20_sent = False
    else:
        wl_entry = SessionWatchList(
            session_id=session.id,
            student_id=student.id,
            checked_in_at=now,
            last_seen_at=now,
        )
        db.add(wl_entry)

    # Attendance record
    att_result = await db.execute(
        select(Attendance).where(
            Attendance.student_id == student.id,
            Attendance.session_id == session.id,
        )
    )
    att = att_result.scalar_one_or_none()
    if not att:
        # Check if late (> 15 min after session start)
        minutes_late = (now - session.started_at).total_seconds() / 60
        status_val = AttendanceStatus.LATE if minutes_late > 15 else AttendanceStatus.PRESENT
        att = Attendance(
            student_id=student.id,
            session_id=session.id,
            date=now.date(),
            status=status_val,
            marked_at=now,
            confidence=recog["confidence"],
            source="kiosk",
        )
        db.add(att)
    else:
        att.status = AttendanceStatus.PRESENT
        att.marked_at = now
        att.confidence = recog["confidence"]

    await db.commit()
    return RecognitionResult(
        matched=True,
        message=f"Welcome, {student.name}! Attendance recorded.",
        student_id=student.student_id,
        name=student.name,
        confidence=recog["confidence"],
    )


# ── Watch List ────────────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/watchlist", response_model=List[WatchListOut])
async def get_watchlist(session_id: int, db: AsyncSession = Depends(get_db),
                        _: Admin = Depends(get_current_admin)):
    result = await db.execute(
        select(SessionWatchList, Student)
        .join(Student, SessionWatchList.student_id == Student.id)
        .where(SessionWatchList.session_id == session_id)
        .order_by(SessionWatchList.checked_in_at)
    )
    rows = result.all()
    return [
        WatchListOut(
            id=wl.id, session_id=wl.session_id, student_id=wl.student_id,
            checked_in_at=wl.checked_in_at, last_seen_at=wl.last_seen_at,
            warn_15_sent=wl.warn_15_sent, email_20_sent=wl.email_20_sent,
            is_active=wl.is_active, student_name=s.name, student_code=s.student_id,
        )
        for wl, s in rows
    ]


@router.post("/sessions/{session_id}/watchlist/{student_id}/checkout")
async def checkout_student(session_id: int, student_id: int,
                           db: AsyncSession = Depends(get_db),
                           _: Admin = Depends(get_current_admin)):
    """Mark student as left the classroom — stops camera watching."""
    result = await db.execute(
        select(SessionWatchList).where(
            SessionWatchList.session_id == session_id,
            SessionWatchList.student_id == student_id,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(404, "Watch list entry not found.")
    entry.is_active = False

    # Create alert
    stu_result = await db.execute(select(Student).where(Student.id == student_id))
    student = stu_result.scalar_one_or_none()
    alert = Alert(
        session_id=session_id,
        student_id=student_id,
        type=AlertType.STUDENT_LEFT,
        severity=AlertSeverity.INFO,
        message=f"{student.name if student else 'Student'} has left the classroom.",
    )
    db.add(alert)
    await db.commit()
    return {"ok": True}


# ── Attendance Records ────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/records", response_model=List[AttendanceOut])
async def get_session_attendance(session_id: int, db: AsyncSession = Depends(get_db),
                                 _: Admin = Depends(get_current_admin)):
    result = await db.execute(
        select(Attendance, Student)
        .join(Student, Attendance.student_id == Student.id)
        .where(Attendance.session_id == session_id)
        .order_by(Student.name)
    )
    rows = result.all()
    return [
        AttendanceOut(
            id=a.id, student_id=a.student_id, session_id=a.session_id,
            date=a.date, status=a.status, marked_at=a.marked_at,
            confidence=a.confidence, source=a.source,
            student_name=s.name, student_code=s.student_id,
        )
        for a, s in rows
    ]


@router.patch("/records/manual")
async def manual_update(req: ManualAttendanceUpdate, db: AsyncSession = Depends(get_db),
                        _: Admin = Depends(get_current_admin)):
    result = await db.execute(
        select(Attendance).where(
            Attendance.student_id == req.student_id,
            Attendance.session_id == req.session_id,
        )
    )
    att = result.scalar_one_or_none()
    try:
        new_status = AttendanceStatus(req.status)
    except ValueError:
        raise HTTPException(400, f"Invalid status: {req.status}")

    if att:
        att.status = new_status
        att.source = "manual"
        att.marked_at = datetime.utcnow()
    else:
        att = Attendance(
            student_id=req.student_id,
            session_id=req.session_id,
            date=date.today(),
            status=new_status,
            source="manual",
            marked_at=datetime.utcnow(),
        )
        db.add(att)
    await db.commit()
    return {"ok": True}


@router.get("/sessions/{session_id}/summary", response_model=AttendanceSummary)
async def session_summary(session_id: int, db: AsyncSession = Depends(get_db),
                          _: Admin = Depends(get_current_admin)):
    sess_result = await db.execute(select(ClassSession).where(ClassSession.id == session_id))
    session = sess_result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found.")

    att_result = await db.execute(select(Attendance).where(Attendance.session_id == session_id))
    atts = att_result.scalars().all()
    total = len(atts)
    present = sum(1 for a in atts if a.status == AttendanceStatus.PRESENT)
    absent = sum(1 for a in atts if a.status == AttendanceStatus.ABSENT)
    late = sum(1 for a in atts if a.status == AttendanceStatus.LATE)

    return AttendanceSummary(
        session_id=session_id,
        subject=session.subject,
        batch=session.batch,
        date=session.started_at.date(),
        total=total,
        present=present,
        absent=absent,
        late=late,
        percentage=round(present / total * 100, 1) if total else 0.0,
    )
