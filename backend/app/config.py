from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    APP_NAME: str = "SmartAttend"
    DEBUG: bool = False

    DATABASE_URL: str = "sqlite+aiosqlite:///./smartattend.db"

    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    KIOSK_API_KEY: str = "CHANGE_ME_KIOSK"

    # Face recognition
    FACE_MODEL: str = "buffalo_l"
    FACE_THRESHOLD: float = 0.45
    FACE_ENROLLMENT_SAMPLES: int = 5

    # Monitoring timings
    MONITORING_INTERVAL_SECONDS: int = 300
    ABSENT_WARN_MINUTES: int = 15
    ABSENT_EMAIL_MINUTES: int = 20

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Zoho SMTP
    SMTP_HOST: str = "smtp.zoho.in"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "SmartAttend Alerts"
    ALERT_EMAIL_RECIPIENTS: str = ""
    DAILY_REPORT_TIME: str = "18:00"
    DAILY_REPORT_RECIPIENTS: str = ""

    SNAPSHOTS_DIR: str = "./snapshots"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def alert_recipients_list(self) -> List[str]:
        return [e.strip() for e in self.ALERT_EMAIL_RECIPIENTS.split(",") if e.strip()]

    @property
    def report_recipients_list(self) -> List[str]:
        return [e.strip() for e in self.DAILY_REPORT_RECIPIENTS.split(",") if e.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
os.makedirs(settings.SNAPSHOTS_DIR, exist_ok=True)
