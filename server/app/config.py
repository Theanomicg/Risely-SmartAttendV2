from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    APP_NAME: str = "SmartAttend"
    DEBUG: bool = False

    # SQLite by default; swap to postgresql+asyncpg:// for production
    DATABASE_URL: str = "sqlite+aiosqlite:///./smartattend.db"

    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    KIOSK_API_KEY: str = "CHANGE_ME_KIOSK_SECRET"

    # InsightFace
    FACE_MODEL: str = "buffalo_l"
    FACE_THRESHOLD: float = 0.35      # cosine similarity (higher = stricter)
    FACE_ENROLLMENT_SAMPLES: int = 5

    # Camera monitoring
    MONITORING_INTERVAL: int = 300    # seconds between frame grabs
    ABSENT_WARNING_SECONDS: int = 900   # 15 min → in-app bell + alert
    ABSENT_EMAIL_SECONDS: int = 1200    # 20 min → email

    # Zoho SMTP
    SMTP_HOST: str = "smtp.zoho.in"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "SmartAttend Alerts"

    # Comma-separated alert recipient emails
    ALERT_EMAILS: str = ""

    DAILY_REPORT_TIME: str = "18:00"

    FRONTEND_URL: str = "http://localhost:5173"

    @property
    def alert_email_list(self) -> List[str]:
        return [e.strip() for e in self.ALERT_EMAILS.split(",") if e.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
