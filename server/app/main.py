"""
SmartAttend — main.py
Run: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import create_tables
from app.routers import auth, students, attendance, alerts, cameras, admin
from app.services.scheduler_service import start_scheduler, stop_scheduler
from app.services import camera_service

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger("smartattend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("SmartAttend starting up...")
    await create_tables()

    os.makedirs("snapshots", exist_ok=True)
    os.makedirs("student_photos", exist_ok=True)

    # Wire WebSocket broadcast into scheduler
    from app.routers.alerts import broadcast_alert
    from app.services.scheduler_service import set_broadcast_fn
    set_broadcast_fn(broadcast_alert)

    # Start scheduler (also starts camera streams from DB)
    start_scheduler()

    log.info("SmartAttend ready. API docs: http://localhost:8000/docs")
    yield

    log.info("SmartAttend shutting down...")
    stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered face recognition attendance & classroom monitoring by Risely",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(students.router)
app.include_router(attendance.router)
app.include_router(alerts.router)
app.include_router(cameras.router)
app.include_router(admin.router)

# ── Static files ───────────────────────────────────────────────────────────────
app.mount("/snapshots", StaticFiles(directory="snapshots"), name="snapshots")
app.mount("/student_photos", StaticFiles(directory="student_photos"), name="student_photos")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": "2.0.0",
        "cameras_active": len(camera_service._stream_threads),
    }
