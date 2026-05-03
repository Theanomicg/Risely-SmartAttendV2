from fastapi import Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Teacher

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_teacher(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Teacher:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        teacher_id: int = int(payload.get("sub", 0))
    except (JWTError, ValueError):
        raise exc

    teacher = await db.get(Teacher, teacher_id)
    if not teacher or not teacher.is_active:
        raise exc
    return teacher


async def require_admin(teacher: Teacher = Depends(get_current_teacher)) -> Teacher:
    if not teacher.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return teacher


async def require_kiosk_key(x_kiosk_key: str = Header(...)):
    if x_kiosk_key != settings.KIOSK_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid kiosk key.")
