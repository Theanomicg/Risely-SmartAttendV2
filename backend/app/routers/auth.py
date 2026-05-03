from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt
from passlib.context import CryptContext

from app.database import get_db
from app.models import Admin
from app.schemas import RegisterRequest, LoginRequest, TokenResponse
from app.config import settings
from app.deps import get_current_admin

router = APIRouter(prefix="/auth", tags=["Auth"])
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash(pw: str) -> str:
    return pwd_ctx.hash(pw)


def _verify(pw: str, hashed: str) -> bool:
    return pwd_ctx.verify(pw, hashed)


def _create_token(admin_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(admin_id), "exp": expire}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@router.post("/setup", response_model=TokenResponse, summary="Create first superadmin")
async def setup(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Admin))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Setup already done. Use /auth/register.")
    admin = Admin(name=req.name, email=req.email, hashed_pw=_hash(req.password), role="superadmin")
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return TokenResponse(access_token=_create_token(admin.id), admin_id=admin.id,
                         name=admin.name, email=admin.email, role=admin.role)


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db),
                   current: Admin = Depends(get_current_admin)):
    if current.role != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin can register new admins.")
    exists = await db.execute(select(Admin).where(Admin.email == req.email))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered.")
    admin = Admin(name=req.name, email=req.email, hashed_pw=_hash(req.password))
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return TokenResponse(access_token=_create_token(admin.id), admin_id=admin.id,
                         name=admin.name, email=admin.email, role=admin.role)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Admin).where(Admin.email == req.email))
    admin = result.scalar_one_or_none()
    if not admin or not _verify(req.password, admin.hashed_pw):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    if not admin.is_active:
        raise HTTPException(status_code=403, detail="Account disabled.")
    return TokenResponse(access_token=_create_token(admin.id), admin_id=admin.id,
                         name=admin.name, email=admin.email, role=admin.role)


@router.get("/me")
async def me(current: Admin = Depends(get_current_admin)):
    return {"id": current.id, "name": current.name, "email": current.email, "role": current.role}
