from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models import Admin, Alert, AlertRecipient, Student, ClassSession
from app.schemas import AlertOut, AlertMarkRead, RecipientCreate, RecipientOut
from app.deps import get_current_admin
from app.services.email_service import send_test_email
from app.config import settings

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("/", response_model=List[AlertOut])
async def list_alerts(
    unread_only: bool = False,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    q = (
        select(Alert, Student, ClassSession)
        .outerjoin(Student, Alert.student_id == Student.id)
        .outerjoin(ClassSession, Alert.session_id == ClassSession.id)
        .order_by(desc(Alert.created_at))
        .limit(limit)
    )
    if unread_only:
        q = q.where(Alert.is_read == False)  # noqa: E712
    result = await db.execute(q)
    rows = result.all()
    return [
        AlertOut(
            id=a.id, session_id=a.session_id, student_id=a.student_id,
            type=a.type, severity=a.severity, message=a.message,
            snapshot_path=a.snapshot_path, email_sent=a.email_sent,
            is_read=a.is_read, created_at=a.created_at,
            student_name=s.name if s else None,
            session_subject=sess.subject if sess else None,
        )
        for a, s, sess in rows
    ]


@router.post("/mark-read")
async def mark_read(req: AlertMarkRead, db: AsyncSession = Depends(get_db),
                    _: Admin = Depends(get_current_admin)):
    result = await db.execute(select(Alert).where(Alert.id.in_(req.alert_ids)))
    for alert in result.scalars().all():
        alert.is_read = True
    await db.commit()
    return {"ok": True}


@router.post("/mark-all-read")
async def mark_all_read(db: AsyncSession = Depends(get_db), _: Admin = Depends(get_current_admin)):
    result = await db.execute(select(Alert).where(Alert.is_read == False))  # noqa: E712
    for alert in result.scalars().all():
        alert.is_read = True
    await db.commit()
    return {"ok": True}


@router.get("/unread-count")
async def unread_count(db: AsyncSession = Depends(get_db), _: Admin = Depends(get_current_admin)):
    from sqlalchemy import func
    result = await db.execute(
        select(func.count()).where(Alert.is_read == False)  # noqa: E712
    )
    return {"count": result.scalar()}


# ── Email Recipients ──────────────────────────────────────────────────────────

@router.get("/recipients", response_model=List[RecipientOut])
async def list_recipients(db: AsyncSession = Depends(get_db), _: Admin = Depends(get_current_admin)):
    result = await db.execute(select(AlertRecipient).order_by(AlertRecipient.name))
    return result.scalars().all()


@router.post("/recipients", response_model=RecipientOut, status_code=201)
async def add_recipient(req: RecipientCreate, db: AsyncSession = Depends(get_db),
                        _: Admin = Depends(get_current_admin)):
    exists = await db.execute(select(AlertRecipient).where(AlertRecipient.email == req.email))
    if exists.scalar_one_or_none():
        raise HTTPException(400, "Email already added.")
    r = AlertRecipient(email=req.email, name=req.name)
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return r


@router.delete("/recipients/{recipient_id}")
async def delete_recipient(recipient_id: int, db: AsyncSession = Depends(get_db),
                           _: Admin = Depends(get_current_admin)):
    result = await db.execute(select(AlertRecipient).where(AlertRecipient.id == recipient_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Recipient not found.")
    await db.delete(r)
    await db.commit()
    return {"ok": True}


@router.post("/test-email")
async def test_email(db: AsyncSession = Depends(get_db), _: Admin = Depends(get_current_admin)):
    result = await db.execute(select(AlertRecipient).where(AlertRecipient.is_active == True))
    recipients = [r.email for r in result.scalars().all()]
    if not recipients:
        recipients = settings.alert_recipients_list
    if not recipients:
        raise HTTPException(400, "No recipients configured.")
    try:
        ok = await send_test_email(recipients)
    except Exception as exc:
        raise HTTPException(502, f"SMTP test failed: {exc}") from exc
    return {"ok": ok, "sent_to": recipients}
