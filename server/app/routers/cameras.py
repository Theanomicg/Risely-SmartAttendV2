"""Cameras router — CRUD + test + live status."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_teacher, require_admin
from app.models import Camera, CameraStatus, Teacher
from app.schemas import CameraCreate, CameraUpdate, CameraOut, CameraTestResult
from app.services import camera_service

router = APIRouter(prefix="/cameras", tags=["cameras"])
log = logging.getLogger("smartattend.cameras")


@router.post("", response_model=CameraOut, status_code=201)
async def add_camera(
    body: CameraCreate,
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(require_admin),
):
    existing = await db.execute(select(Camera).where(Camera.rtsp_url == body.rtsp_url))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "A camera with this RTSP URL already exists.")

    cam = Camera(**body.model_dump())
    db.add(cam)
    await db.commit()
    await db.refresh(cam)

    # Start stream immediately
    camera_service.start_camera(cam.id, cam.rtsp_url)
    log.info("Camera added and started: %s", cam.name)
    return cam


@router.get("", response_model=List[CameraOut])
async def list_cameras(
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(select(Camera).order_by(Camera.name))
    cameras = result.scalars().all()

    # Overlay live status from camera_service
    live_statuses = camera_service.get_all_statuses()
    for cam in cameras:
        live = live_statuses.get(cam.id)
        if live:
            cam.status = CameraStatus.ONLINE if live == "online" else CameraStatus.OFFLINE
    return cameras


@router.get("/{camera_id}", response_model=CameraOut)
async def get_camera(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    cam = await db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found.")
    live = camera_service.get_camera_status(camera_id)
    if live:
        cam.status = CameraStatus.ONLINE if live == "online" else CameraStatus.OFFLINE
    return cam


@router.patch("/{camera_id}", response_model=CameraOut)
async def update_camera(
    camera_id: int,
    body: CameraUpdate,
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(require_admin),
):
    cam = await db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found.")

    old_url = cam.rtsp_url
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(cam, k, v)
    await db.commit()
    await db.refresh(cam)

    # Restart stream if URL or active status changed
    if body.rtsp_url or body.is_active is not None:
        camera_service.stop_camera(camera_id)
        if cam.is_active:
            camera_service.start_camera(cam.id, cam.rtsp_url)
    return cam


@router.delete("/{camera_id}", status_code=204)
async def delete_camera(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(require_admin),
):
    cam = await db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found.")
    camera_service.stop_camera(camera_id)
    await db.delete(cam)
    await db.commit()


@router.post("/{camera_id}/restart")
async def restart_camera(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(require_admin),
):
    cam = await db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found.")
    camera_service.stop_camera(camera_id)
    camera_service.start_camera(cam.id, cam.rtsp_url)
    return {"message": f"Camera '{cam.name}' restarted."}


@router.get("/{camera_id}/snapshot")
async def get_snapshot(
    camera_id: int,
    _: Teacher = Depends(get_current_teacher),
):
    """Return latest frame as base64 JPEG."""
    b64 = camera_service.capture_frame_b64(camera_id)
    if b64 is None:
        raise HTTPException(503, "Camera offline or no frame available.")
    return {"snapshot_b64": b64}


@router.post("/test", response_model=CameraTestResult)
async def test_camera(
    body: CameraCreate,
    _: Teacher = Depends(require_admin),
):
    """Test an RTSP URL before saving — returns a snapshot."""
    success, message, b64 = camera_service.test_camera_connection(body.rtsp_url)
    return CameraTestResult(success=success, message=message, snapshot_b64=b64)
