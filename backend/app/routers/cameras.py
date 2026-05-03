from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Admin, Camera
from app.schemas import CameraCreate, CameraUpdate, CameraOut
from app.deps import get_current_admin
from app.services.camera_service import (
    add_camera, remove_camera, test_camera_connection,
    capture_frame_b64, get_stream_status,
)

router = APIRouter(prefix="/cameras", tags=["Cameras"])


@router.get("/", response_model=List[CameraOut])
async def list_cameras(db: AsyncSession = Depends(get_db), _: Admin = Depends(get_current_admin)):
    result = await db.execute(select(Camera).order_by(Camera.name))
    return result.scalars().all()


@router.post("/test-connection")
async def test_connection(payload: dict, _: Admin = Depends(get_current_admin)):
    """Test an RTSP URL before saving."""
    rtsp_url = payload.get("rtsp_url", "")
    if not rtsp_url:
        raise HTTPException(400, "rtsp_url is required.")
    result = test_camera_connection(rtsp_url)
    return result


@router.post("/", response_model=CameraOut, status_code=201)
async def create_camera(
    req: CameraCreate,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    cam = Camera(
        name=req.name,
        location=req.location,
        rtsp_url=req.rtsp_url,
        notes=req.notes,
        status="unknown",
    )
    db.add(cam)
    await db.commit()
    await db.refresh(cam)
    # Start streaming immediately
    add_camera(cam.rtsp_url)
    return cam


@router.get("/{camera_id}", response_model=CameraOut)
async def get_camera(camera_id: int, db: AsyncSession = Depends(get_db),
                     _: Admin = Depends(get_current_admin)):
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(404, "Camera not found.")
    return cam


@router.patch("/{camera_id}", response_model=CameraOut)
async def update_camera(
    camera_id: int,
    req: CameraUpdate,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(404, "Camera not found.")

    old_url = cam.rtsp_url
    for k, v in req.model_dump(exclude_none=True).items():
        setattr(cam, k, v)
    await db.commit()
    await db.refresh(cam)

    # Restart stream if URL changed
    if req.rtsp_url and req.rtsp_url != old_url:
        remove_camera(old_url)
        if cam.is_active:
            add_camera(cam.rtsp_url)
    elif req.is_active is False:
        remove_camera(cam.rtsp_url)
    elif req.is_active is True:
        add_camera(cam.rtsp_url)

    return cam


@router.delete("/{camera_id}")
async def delete_camera(camera_id: int, db: AsyncSession = Depends(get_db),
                        _: Admin = Depends(get_current_admin)):
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(404, "Camera not found.")
    remove_camera(cam.rtsp_url)
    cam.is_active = False
    await db.commit()
    return {"ok": True}


@router.get("/{camera_id}/snapshot")
async def get_snapshot(camera_id: int, db: AsyncSession = Depends(get_db),
                       _: Admin = Depends(get_current_admin)):
    """Get latest JPEG frame as base64."""
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(404, "Camera not found.")
    b64 = capture_frame_b64(cam.rtsp_url)
    if not b64:
        raise HTTPException(503, "No frame available — camera may be offline.")
    return {"image_b64": b64, "camera_id": camera_id}


@router.get("/{camera_id}/stream-status")
async def stream_status(camera_id: int, db: AsyncSession = Depends(get_db),
                        _: Admin = Depends(get_current_admin)):
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(404, "Camera not found.")
    return get_stream_status(cam.rtsp_url)
