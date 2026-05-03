from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_teacher
from app.models import Teacher
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, TeacherOut

router = APIRouter(prefix="/auth", tags=["auth"])
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

ADMIN_SECRET = "SMARTATTEND_ADMIN_2024"  # Change this or move to .env


def _make_token(teacher_id: int) -> str:
    exp = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(teacher_id), "exp": exp},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Teacher).where(Teacher.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email already registered.")

    if body.is_admin:
        if body.admin_secret != ADMIN_SECRET:
            raise HTTPException(403, "Invalid admin secret.")

    teacher = Teacher(
        name=body.name,
        email=body.email,
        hashed_pw=_pwd.hash(body.password),
        is_admin=body.is_admin,
    )
    db.add(teacher)
    await db.commit()
    await db.refresh(teacher)
    return TokenResponse(
        access_token=_make_token(teacher.id),
        teacher_id=teacher.id,
        name=teacher.name,
        is_admin=teacher.is_admin,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Teacher).where(Teacher.email == body.email))
    teacher = result.scalar_one_or_none()
    if not teacher or not _pwd.verify(body.password, teacher.hashed_pw):
        raise HTTPException(401, "Invalid email or password.")
    if not teacher.is_active:
        raise HTTPException(403, "Account disabled.")
    return TokenResponse(
        access_token=_make_token(teacher.id),
        teacher_id=teacher.id,
        name=teacher.name,
        is_admin=teacher.is_admin,
    )


@router.get("/me", response_model=TeacherOut)
async def me(teacher: Teacher = Depends(get_current_teacher)):
    return teacher
