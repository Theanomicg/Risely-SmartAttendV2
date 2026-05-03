import os
import base64
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_teacher
from app.models import Student, FaceEmbedding, Teacher
from app.schemas import (
    StudentCreate, StudentUpdate, StudentOut,
    EnrollRequest, EnrollResponse,
)
from app.services import face_service

router = APIRouter(prefix="/students", tags=["students"])
log = logging.getLogger("smartattend.students")


def _enrich(student: Student, count: int) -> StudentOut:
    from app.config import settings
    out = StudentOut.model_validate(student)
    out.samples_stored = count
    out.enrollment_complete = count >= settings.FACE_ENROLLMENT_SAMPLES
    return out


@router.post("", response_model=StudentOut, status_code=201)
async def create_student(
    body: StudentCreate,
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    existing = await db.execute(
        select(Student).where(Student.student_id == body.student_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Student ID '{body.student_id}' already exists.")

    student = Student(**body.model_dump())
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return _enrich(student, 0)


@router.get("", response_model=List[StudentOut])
async def list_students(
    batch: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    q = select(Student).where(Student.is_active == True)
    if batch:
        q = q.where(Student.batch == batch)
    if search:
        q = q.where(Student.name.ilike(f"%{search}%") | Student.student_id.ilike(f"%{search}%"))
    result = await db.execute(q.order_by(Student.name))
    students = result.scalars().all()

    enriched = []
    for s in students:
        cnt_r = await db.execute(
            select(func.count()).where(FaceEmbedding.student_id == s.id)
        )
        count = int(cnt_r.scalar())
        enriched.append(_enrich(s, count))
    return enriched


@router.get("/{student_id}", response_model=StudentOut)
async def get_student(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(
        select(Student).where(Student.student_id == student_id)
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student not found.")
    cnt_r = await db.execute(
        select(func.count()).where(FaceEmbedding.student_id == student.id)
    )
    return _enrich(student, int(cnt_r.scalar()))


@router.patch("/{student_id}", response_model=StudentOut)
async def update_student(
    student_id: str,
    body: StudentUpdate,
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(select(Student).where(Student.student_id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student not found.")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(student, k, v)
    await db.commit()
    await db.refresh(student)
    cnt_r = await db.execute(select(func.count()).where(FaceEmbedding.student_id == student.id))
    return _enrich(student, int(cnt_r.scalar()))


@router.delete("/{student_id}", status_code=204)
async def delete_student(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(select(Student).where(Student.student_id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student not found.")
    student.is_active = False
    await db.commit()


@router.post("/{student_id}/enroll", response_model=EnrollResponse)
async def enroll_face(
    student_id: str,
    body: EnrollRequest,
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    """Enroll one face sample for a student (base64 image)."""
    result = await db.execute(select(Student).where(Student.student_id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student not found.")

    success, msg, count = await face_service.enroll_face(student.id, body.image_b64, db)
    from app.config import settings
    return EnrollResponse(
        success=success,
        message=msg,
        samples_stored=count,
        required_samples=settings.FACE_ENROLLMENT_SAMPLES,
        enrollment_complete=count >= settings.FACE_ENROLLMENT_SAMPLES,
    )


@router.post("/{student_id}/enroll-file", response_model=EnrollResponse)
async def enroll_face_file(
    student_id: str,
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    """Enroll one face sample via file upload."""
    result = await db.execute(select(Student).where(Student.student_id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student not found.")

    data = await image.read()
    b64 = base64.b64encode(data).decode()

    # Save photo if first enrollment
    cnt_r = await db.execute(select(func.count()).where(FaceEmbedding.student_id == student.id))
    if int(cnt_r.scalar()) == 0:
        os.makedirs("student_photos", exist_ok=True)
        photo_path = f"student_photos/{student.student_id}.jpg"
        with open(photo_path, "wb") as f:
            f.write(data)
        student.photo_path = photo_path
        await db.commit()

    success, msg, count = await face_service.enroll_face(student.id, b64, db)
    from app.config import settings
    return EnrollResponse(
        success=success,
        message=msg,
        samples_stored=count,
        required_samples=settings.FACE_ENROLLMENT_SAMPLES,
        enrollment_complete=count >= settings.FACE_ENROLLMENT_SAMPLES,
    )


@router.delete("/{student_id}/enrollments", status_code=204)
async def clear_enrollments(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    """Clear all face samples for re-enrollment."""
    result = await db.execute(select(Student).where(Student.student_id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student not found.")
    embs = await db.execute(
        select(FaceEmbedding).where(FaceEmbedding.student_id == student.id)
    )
    for fe in embs.scalars().all():
        await db.delete(fe)
    await db.commit()


@router.get("/{student_id}/enrollment-status")
async def enrollment_status(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(select(Student).where(Student.student_id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student not found.")
    return await face_service.get_enrollment_status(student.id, db)
