from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, EmailStr
from app.models import AttendanceStatus, AlertSeverity, AlertType, CameraStatus


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    is_admin: bool = False
    admin_secret: Optional[str] = None  # required to create admin accounts

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    teacher_id: int
    name: str
    is_admin: bool

class TeacherOut(BaseModel):
    id: int
    name: str
    email: str
    is_admin: bool
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True


# ── Students ──────────────────────────────────────────────────────────────────

class StudentCreate(BaseModel):
    student_id: str
    name: str
    batch: str
    email: Optional[str] = None
    phone: Optional[str] = None

class StudentUpdate(BaseModel):
    name: Optional[str] = None
    batch: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None

class StudentOut(BaseModel):
    id: int
    student_id: str
    name: str
    batch: str
    email: Optional[str]
    phone: Optional[str]
    photo_path: Optional[str]
    is_active: bool
    enrolled_at: datetime
    enrollment_complete: bool = False
    samples_stored: int = 0
    class Config:
        from_attributes = True

class EnrollRequest(BaseModel):
    image_b64: str   # base64 JPEG/PNG

class EnrollResponse(BaseModel):
    success: bool
    message: str
    samples_stored: int
    required_samples: int
    enrollment_complete: bool


# ── Cameras ───────────────────────────────────────────────────────────────────

class CameraCreate(BaseModel):
    name: str
    location: Optional[str] = None
    rtsp_url: str
    username: Optional[str] = None
    password: Optional[str] = None
    notes: Optional[str] = None

class CameraUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    rtsp_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None

class CameraOut(BaseModel):
    id: int
    name: str
    location: Optional[str]
    rtsp_url: str
    is_active: bool
    status: CameraStatus
    last_seen: Optional[datetime]
    snapshot_path: Optional[str]
    created_at: datetime
    notes: Optional[str]
    class Config:
        from_attributes = True

class CameraTestResult(BaseModel):
    success: bool
    message: str
    snapshot_b64: Optional[str] = None


# ── Sessions ──────────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    subject: str
    batch: str
    room: Optional[str] = None
    camera_id: Optional[int] = None

class SessionOut(BaseModel):
    id: int
    teacher_id: int
    camera_id: Optional[int]
    subject: str
    batch: str
    room: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    class Config:
        from_attributes = True


# ── Attendance ─────────────────────────────────────────────────────────────────

class KioskCheckIn(BaseModel):
    session_id: int
    image_b64: str
    captured_at: Optional[datetime] = None

class RecognitionResult(BaseModel):
    matched: bool
    student_id: Optional[str] = None
    name: Optional[str] = None
    confidence: Optional[float] = None
    message: str

class AttendanceOut(BaseModel):
    id: int
    student_id: int
    session_id: int
    date: date
    status: AttendanceStatus
    marked_at: Optional[datetime]
    confidence: Optional[float]
    source: str
    class Config:
        from_attributes = True

class AttendanceSummary(BaseModel):
    session_id: int
    subject: str
    batch: str
    date: date
    total: int
    present: int
    absent: int
    late: int
    percentage: float

class ManualAttendanceUpdate(BaseModel):
    student_id: int
    session_id: int
    status: AttendanceStatus


# ── Alerts ─────────────────────────────────────────────────────────────────────

class AlertOut(BaseModel):
    id: int
    teacher_id: Optional[int]
    session_id: Optional[int]
    student_id: Optional[int]
    type: AlertType
    severity: AlertSeverity
    message: str
    snapshot_path: Optional[str]
    is_read: bool
    created_at: datetime
    class Config:
        from_attributes = True

class AlertMarkRead(BaseModel):
    alert_ids: List[int]


# ── Settings (admin configurable) ─────────────────────────────────────────────

class SystemSettings(BaseModel):
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: Optional[str] = None  # omit to keep existing
    smtp_from_name: str
    alert_emails: List[str]
    monitoring_interval: int
    absent_warning_seconds: int
    absent_email_seconds: int
    face_threshold: float
    face_enrollment_samples: int
