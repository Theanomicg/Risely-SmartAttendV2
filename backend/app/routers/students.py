import os
import base64
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Admin, Student, FaceSample
from app.schemas import StudentCreate, StudentOut, StudentUpdate
from app.deps import get_current_admin
from app.config import settings
from app.services import face_service

router = APIRouter(prefix="/students", tags=["Students"])


@router.get("/", response_model=List[StudentOut])
async def list_students(
    batch: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    q = select(Student).where(Student.is_active == True)
    if batch:
        q = q.where(Student.batch == batch)
    if search:
        q = q.where(Student.name.ilike(f"%{search}%") | Student.student_id.ilike(f"%{search}%"))
    result = await db.execute(q.order_by(Student.name))
    students = result.scalars().all()

    out = []
    for s in students:
        cnt_result = await db.execute(
            select(func.count()).where(FaceSample.student_id == s.id)
        )
        cnt = cnt_result.scalar()
        out.append(StudentOut(
            id=s.id, student_id=s.student_id, name=s.name, batch=s.batch,
            email=s.email, phone=s.phone, photo_path=s.photo_path,
            is_active=s.is_active, enrolled_at=s.enrolled_at,
            face_samples_count=cnt,
            is_face_enrolled=cnt >= settings.FACE_ENROLLMENT_SAMPLES,
        ))
    return out


@router.post("/", response_model=StudentOut, status_code=201)
async def create_student(
    req: StudentCreate,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    exists = await db.execute(select(Student).where(Student.student_id == req.student_id))
    if exists.scalar_one_or_none():
        raise HTTPException(400, "Student ID already exists.")
    s = Student(**req.model_dump())
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return StudentOut(
        id=s.id, student_id=s.student_id, name=s.name, batch=s.batch,
        email=s.email, phone=s.phone, photo_path=s.photo_path,
        is_active=s.is_active, enrolled_at=s.enrolled_at,
        face_samples_count=0, is_face_enrolled=False,
    )


@router.get("/{student_id}", response_model=StudentOut)
async def get_student(student_id: str, db: AsyncSession = Depends(get_db),
                      _: Admin = Depends(get_current_admin)):
    result = await db.execute(select(Student).where(Student.student_id == student_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Student not found.")
    cnt_result = await db.execute(select(func.count()).where(FaceSample.student_id == s.id))
    cnt = cnt_result.scalar()
    return StudentOut(
        id=s.id, student_id=s.student_id, name=s.name, batch=s.batch,
        email=s.email, phone=s.phone, photo_path=s.photo_path,
        is_active=s.is_active, enrolled_at=s.enrolled_at,
        face_samples_count=cnt,
        is_face_enrolled=cnt >= settings.FACE_ENROLLMENT_SAMPLES,
    )


@router.patch("/{student_id}", response_model=StudentOut)
async def update_student(student_id: str, req: StudentUpdate,
                         db: AsyncSession = Depends(get_db),
                         _: Admin = Depends(get_current_admin)):
    result = await db.execute(select(Student).where(Student.student_id == student_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Student not found.")
    for k, v in req.model_dump(exclude_none=True).items():
        setattr(s, k, v)
    await db.commit()
    await db.refresh(s)
    cnt_result = await db.execute(select(func.count()).where(FaceSample.student_id == s.id))
    cnt = cnt_result.scalar()
    return StudentOut(
        id=s.id, student_id=s.student_id, name=s.name, batch=s.batch,
        email=s.email, phone=s.phone, photo_path=s.photo_path,
        is_active=s.is_active, enrolled_at=s.enrolled_at,
        face_samples_count=cnt,
        is_face_enrolled=cnt >= settings.FACE_ENROLLMENT_SAMPLES,
    )


@router.delete("/{student_id}")
async def delete_student(student_id: str, db: AsyncSession = Depends(get_db),
                         _: Admin = Depends(get_current_admin)):
    result = await db.execute(select(Student).where(Student.student_id == student_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Student not found.")
    s.is_active = False
    await db.commit()
    return {"ok": True}


# ── Face Enrollment ───────────────────────────────────────────────────────────

@router.post("/{student_id}/enroll-face")
async def enroll_face(
    student_id: str,
    image_b64: str = Form(...),
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    result = await db.execute(select(Student).where(Student.student_id == student_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Student not found.")

    ok, msg = await face_service.enroll_face(s.id, image_b64, db)
    if not ok:
        raise HTTPException(400, msg)

    status_info = await face_service.get_enrollment_status(s.id, db)
    return {"ok": True, "message": msg, **status_info}


@router.post("/{student_id}/enroll-face/upload")
async def enroll_face_upload(
    student_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    result = await db.execute(select(Student).where(Student.student_id == student_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Student not found.")

    data = await file.read()
    b64 = base64.b64encode(data).decode()

    ok, msg = await face_service.enroll_face(s.id, b64, db)
    if not ok:
        raise HTTPException(400, msg)

    status_info = await face_service.get_enrollment_status(s.id, db)
    return {"ok": True, "message": msg, **status_info}


@router.get("/{student_id}/enrollment-status")
async def enrollment_status(student_id: str, db: AsyncSession = Depends(get_db),
                             _: Admin = Depends(get_current_admin)):
    result = await db.execute(select(Student).where(Student.student_id == student_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Student not found.")
    return await face_service.get_enrollment_status(s.id, db)


@router.delete("/{student_id}/face-samples")
async def delete_face_samples(student_id: str, db: AsyncSession = Depends(get_db),
                               _: Admin = Depends(get_current_admin)):
    result = await db.execute(select(Student).where(Student.student_id == student_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Student not found.")
    samples_result = await db.execute(select(FaceSample).where(FaceSample.student_id == s.id))
    for sample in samples_result.scalars().all():
        await db.delete(sample)
    await db.commit()
    return {"ok": True, "message": "Face samples deleted."}
