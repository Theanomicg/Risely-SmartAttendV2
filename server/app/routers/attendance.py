"""Attendance router — kiosk check-in, sessions, reports."""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_teacher, require_kiosk_key
from app.models import (
    Attendance, AttendanceStatus, ClassSession, Student, Teacher,
    AbsentTracking, Camera,
)
from app.schemas import (
    AttendanceOut, AttendanceSummary, KioskCheckIn,
    ManualAttendanceUpdate, RecognitionResult, SessionCreate, SessionOut,
)
from app.services import face_service

router = APIRouter(prefix="/attendance", tags=["attendance"])


# ── Sessions ───────────────────────────────────────────────────────────────────

@router.post("/sessions", response_model=SessionOut, status_code=201)
async def create_session(
    body: SessionCreate,
    db: AsyncSession = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    if body.camera_id:
        cam = await db.get(Camera, body.camera_id)
        if not cam:
            raise HTTPException(404, "Camera not found.")

    session = ClassSession(
        teacher_id=teacher.id,
        camera_id=body.camera_id,
        subject=body.subject,
        batch=body.batch,
        room=body.room,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions", response_model=List[SessionOut])
async def list_sessions(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    q = select(ClassSession).where(ClassSession.teacher_id == teacher.id)
    if active_only:
        q = q.where(ClassSession.ended_at.is_(None))
    result = await db.execute(q.order_by(ClassSession.started_at.desc()))
    return result.scalars().all()


@router.get("/sessions/all", response_model=List[SessionOut])
async def list_all_sessions(
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(
        select(ClassSession).order_by(ClassSession.started_at.desc()).limit(100)
    )
    return result.scalars().all()


@router.patch("/sessions/{session_id}/end", response_model=SessionOut)
async def end_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    session = await db.get(ClassSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found.")
    if session.teacher_id != teacher.id:
        raise HTTPException(403, "Not your session.")
    session.ended_at = datetime.utcnow()

    # Deactivate absence tracking for all students in this session
    result = await db.execute(
        select(AbsentTracking).where(
            AbsentTracking.session_id == session_id,
            AbsentTracking.is_active == True,
        )
    )
    for t in result.scalars().all():
        t.is_active = False

    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions/{session_id}/summary", response_model=AttendanceSummary)
async def session_summary(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    session = await db.get(ClassSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found.")
    result = await db.execute(
        select(
            func.count(Attendance.id).label("total"),
            func.sum((Attendance.status == AttendanceStatus.PRESENT).cast(int)).label("present"),
            func.sum((Attendance.status == AttendanceStatus.ABSENT).cast(int)).label("absent"),
            func.sum((Attendance.status == AttendanceStatus.LATE).cast(int)).label("late"),
        ).where(Attendance.session_id == session_id)
    )
    row = result.one()
    total   = row.total   or 0
    present = row.present or 0
    return AttendanceSummary(
        session_id=session_id,
        subject=session.subject,
        batch=session.batch,
        date=session.started_at.date(),
        total=total,
        present=present,
        absent=(row.absent or 0),
        late=(row.late or 0),
        percentage=round(present / max(total, 1) * 100, 1),
    )


@router.get("/sessions/{session_id}/records", response_model=List[AttendanceOut])
async def session_records(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(
        select(Attendance).where(Attendance.session_id == session_id)
    )
    return result.scalars().all()


# ── Kiosk check-in ────────────────────────────────────────────────────────────

@router.post("/kiosk-checkin", response_model=RecognitionResult)
async def kiosk_checkin(
    body: KioskCheckIn,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_kiosk_key),
):
    """
    Called by the kiosk with a base64 face image.
    1. Recognize face
    2. Mark attendance
    3. Create/activate AbsentTracking so camera starts watching
    """
    session = await db.get(ClassSession, body.session_id)
    if not session or session.ended_at is not None:
        raise HTTPException(404, "Session not found or already ended.")

    result = await face_service.recognize_face(
        body.image_b64, db, batch_filter=session.batch
    )
    if not result["matched"]:
        return result

    # Look up student
    student_q = await db.execute(
        select(Student).where(Student.student_id == result["student_id"])
    )
    student = student_q.scalar_one_or_none()
    if not student:
        return {"matched": False, "message": "Student record not found."}

    today = (body.captured_at or datetime.utcnow()).date()

    # Upsert attendance → PRESENT
    att_q = await db.execute(
        select(Attendance).where(
            Attendance.student_id == student.id,
            Attendance.session_id == session.id,
            Attendance.date == today,
        )
    )
    att = att_q.scalar_one_or_none()
    if att is None:
        att = Attendance(
            student_id=student.id,
            session_id=session.id,
            date=today,
            status=AttendanceStatus.PRESENT,
            marked_at=datetime.utcnow(),
            confidence=result["confidence"],
            source="kiosk",
        )
        db.add(att)
    else:
        att.status = AttendanceStatus.PRESENT
        att.marked_at = datetime.utcnow()
        if result["confidence"] > (att.confidence or 0):
            att.confidence = result["confidence"]

    # Upsert AbsentTracking — start watching this student
    track_q = await db.execute(
        select(AbsentTracking).where(
            AbsentTracking.student_id == student.id,
            AbsentTracking.session_id == session.id,
        )
    )
    track = track_q.scalar_one_or_none()
    if track is None:
        track = AbsentTracking(
            student_id=student.id,
            session_id=session.id,
            last_seen_at=datetime.utcnow(),
            consecutive_absent_seconds=0,
            is_active=True,
        )
        db.add(track)
    else:
        track.last_seen_at = datetime.utcnow()
        track.consecutive_absent_seconds = 0
        track.warning_sent = False
        track.email_sent = False
        track.is_active = True

    await db.commit()
    return result


# ── Student attendance ─────────────────────────────────────────────────────────

@router.get("/student/{student_id}", response_model=List[AttendanceOut])
async def student_attendance(
    student_id: str,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    student_q = await db.execute(
        select(Student).where(Student.student_id == student_id)
    )
    student = student_q.scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student not found.")
    q = select(Attendance).where(Attendance.student_id == student.id)
    if from_date:
        q = q.where(Attendance.date >= from_date)
    if to_date:
        q = q.where(Attendance.date <= to_date)
    result = await db.execute(q.order_by(Attendance.date.desc()))
    return result.scalars().all()


@router.patch("/manual", response_model=AttendanceOut)
async def manual_update(
    body: ManualAttendanceUpdate,
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    att_q = await db.execute(
        select(Attendance).where(
            Attendance.student_id == body.student_id,
            Attendance.session_id == body.session_id,
            Attendance.date == date.today(),
        )
    )
    att = att_q.scalar_one_or_none()
    if att is None:
        att = Attendance(
            student_id=body.student_id,
            session_id=body.session_id,
            date=date.today(),
            status=body.status,
            marked_at=datetime.utcnow(),
            source="manual",
        )
        db.add(att)
    else:
        att.status = body.status
        att.marked_at = datetime.utcnow()
        att.source = "manual"
    await db.commit()
    await db.refresh(att)
    return att
