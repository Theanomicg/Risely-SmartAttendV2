"""Alerts router — REST + WebSocket real-time delivery."""

import json
import logging
from typing import List, Set

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_teacher
from app.models import Alert, Teacher
from app.schemas import AlertOut, AlertMarkRead

router = APIRouter(prefix="/alerts", tags=["alerts"])
log    = logging.getLogger("smartattend.alerts")


# ── WebSocket connection manager ──────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self._connections: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket):
        self._connections.discard(ws)

    async def broadcast(self, payload: dict):
        dead = set()
        for ws in self._connections:
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.add(ws)
        self._connections -= dead

    @property
    def count(self):
        return len(self._connections)


manager = ConnectionManager()


async def broadcast_alert(alert: Alert):
    """Called from scheduler after creating an alert."""
    payload = {
        "id":           alert.id,
        "type":         alert.type.value if hasattr(alert.type, 'value') else alert.type,
        "severity":     alert.severity.value if hasattr(alert.severity, 'value') else alert.severity,
        "message":      alert.message,
        "session_id":   alert.session_id,
        "student_id":   alert.student_id,
        "snapshot_path": alert.snapshot_path,
        "created_at":   alert.created_at.isoformat(),
        "is_read":      False,
    }
    await manager.broadcast(payload)


# ── REST ───────────────────────────────────────────────────────────────────────

@router.get("", response_model=List[AlertOut])
async def list_alerts(
    unread_only: bool = Query(False),
    limit:       int  = Query(50, le=200),
    db:          AsyncSession = Depends(get_db),
    teacher:     Teacher      = Depends(get_current_teacher),
):
    q = (
        select(Alert)
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        q = q.where(Alert.is_read == False)  # noqa
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/unread-count")
async def unread_count(
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    from sqlalchemy import func
    r = await db.execute(
        select(func.count()).where(Alert.is_read == False)  # noqa
    )
    return {"count": r.scalar()}


@router.patch("/mark-read")
async def mark_read(
    body: AlertMarkRead,
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(
        select(Alert).where(Alert.id.in_(body.alert_ids))
    )
    for alert in result.scalars().all():
        alert.is_read = True
    await db.commit()
    return {"marked": len(body.alert_ids)}


@router.patch("/mark-all-read")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(select(Alert).where(Alert.is_read == False))  # noqa
    count = 0
    for alert in result.scalars().all():
        alert.is_read = True
        count += 1
    await db.commit()
    return {"marked": count}


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if alert:
        await db.delete(alert)
        await db.commit()


# ── WebSocket ──────────────────────────────────────────────────────────────────

@router.websocket("/ws")
async def alerts_ws(websocket: WebSocket):
    """
    ws://your-server/alerts/ws
    Clients receive JSON alert payloads in real-time.
    Send {"ping":1} for keep-alive.
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data:
                try:
                    msg = json.loads(data)
                    if msg.get("ping"):
                        await websocket.send_text(json.dumps({"pong": 1}))
                except Exception:
                    pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
