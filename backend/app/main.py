"""
SmartAttend v2 — Main Application
"""

import logging
import asyncio
import json
from contextlib import asynccontextmanager
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import os

from app.config import settings
from app.database import create_tables

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("smartattend")


# ── WebSocket Connection Manager ──────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self._connections: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.add(ws)
        log.info("WS connected. Total: %d", len(self._connections))

    def disconnect(self, ws: WebSocket):
        self._connections.discard(ws)
        log.info("WS disconnected. Total: %d", len(self._connections))

    async def broadcast(self, msg: dict):
        dead = set()
        for ws in self._connections:
            try:
                await ws.send_text(json.dumps(msg))
            except Exception:
                dead.add(ws)
        self._connections -= dead


manager = ConnectionManager()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log.info("SmartAttend v2 starting up...")
    await create_tables()

    # Load cameras from DB and start streams
    from app.database import AsyncSessionLocal
    from app.models import Camera
    from sqlalchemy import select
    from app.services.camera_service import start_all_streams

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Camera).where(Camera.is_active == True))
        cameras = result.scalars().all()
        urls = [c.rtsp_url for c in cameras]
        if urls:
            log.info("Starting %d camera streams...", len(urls))
            start_all_streams(urls)

    # Set broadcast fn in scheduler
    from app.services.scheduler_service import set_broadcast_fn, start_scheduler
    set_broadcast_fn(manager.broadcast)
    start_scheduler()

    log.info("SmartAttend v2 ready.")
    yield

    # Shutdown
    log.info("Shutting down...")
    from app.services.scheduler_service import stop_scheduler
    from app.services.camera_service import stop_all_streams
    stop_scheduler()
    stop_all_streams()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SmartAttend v2",
    version="2.0.0",
    description="AI-powered face recognition attendance system",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve snapshots
os.makedirs(settings.SNAPSHOTS_DIR, exist_ok=True)
app.mount("/snapshots", StaticFiles(directory=settings.SNAPSHOTS_DIR), name="snapshots")

# Routers
from app.routers import auth, students, cameras, attendance, alerts

app.include_router(auth.router)
app.include_router(students.router)
app.include_router(cameras.router)
app.include_router(attendance.router)
app.include_router(alerts.router)


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo ping/pong
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/")
async def root():
    return {"message": "SmartAttend v2 API", "docs": "/docs"}
