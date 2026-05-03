from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, date


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name:     str
    email:    str
    password: str

class LoginRequest(BaseModel):
    email:    str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    admin_id:     int
    name:         str
    email:        str
    role:         str


# ── Students ──────────────────────────────────────────────────────────────────

class StudentCreate(BaseModel):
    student_id: str
    name:       str
    batch:      str
    email:      Optional[str] = None
    phone:      Optional[str] = None

class StudentOut(BaseModel):
    id:           int
    student_id:   str
    name:         str
    batch:        str
    email:        Optional[str]
    phone:        Optional[str]
    photo_path:   Optional[str]
    is_active:    bool
    enrolled_at:  datetime
    face_samples_count: int = 0
    is_face_enrolled:   bool = False

    class Config:
        from_attributes = True

class StudentUpdate(BaseModel):
    name:     Optional[str] = None
    batch:    Optional[str] = None
    email:    Optional[str] = None
    phone:    Optional[str] = None
    is_active: Optional[bool] = None


# ── Cameras ───────────────────────────────────────────────────────────────────

class CameraCreate(BaseModel):
    name:     str
    location: str
    rtsp_url: str
    notes:    Optional[str] = None

class CameraUpdate(BaseModel):
    name:      Optional[str]  = None
    location:  Optional[str]  = None
    rtsp_url:  Optional[str]  = None
    notes:     Optional[str]  = None
    is_active: Optional[bool] = None

class CameraOut(BaseModel):
    id:        int
    name:      str
    location:  str
    rtsp_url:  str
    status:    str
    last_seen: Optional[datetime]
    is_active: bool
    created_at: datetime
    notes:     Optional[str]

    class Config:
        from_attributes = True


# ── Sessions ──────────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    subject:   str
    batch:     str
    room:      Optional[str] = None
    camera_id: Optional[int] = None

class SessionOut(BaseModel):
    id:         int
    subject:    str
    batch:      str
    room:       Optional[str]
    camera_id:  Optional[int]
    started_at: datetime
    ended_at:   Optional[datetime]
    teacher_name: Optional[str] = None

    class Config:
        from_attributes = True


# ── Attendance ────────────────────────────────────────────────────────────────

class AttendanceOut(BaseModel):
    id:          int
    student_id:  int
    session_id:  int
    date:        date
    status:      str
    marked_at:   Optional[datetime]
    confidence:  Optional[float]
    source:      str
    student_name: Optional[str] = None
    student_code: Optional[str] = None

    class Config:
        from_attributes = True

class AttendanceSummary(BaseModel):
    session_id:  int
    subject:     str
    batch:       str
    date:        date
    total:       int
    present:     int
    absent:      int
    late:        int
    percentage:  float

class KioskCheckIn(BaseModel):
    session_id:  int
    image_b64:   str
    captured_at: Optional[datetime] = None

class ManualAttendanceUpdate(BaseModel):
    student_id: int
    session_id: int
    status:     str

class RecognitionResult(BaseModel):
    matched:    bool
    message:    str
    student_id: Optional[str]   = None
    name:       Optional[str]   = None
    confidence: Optional[float] = None


# ── Alerts ────────────────────────────────────────────────────────────────────

class AlertOut(BaseModel):
    id:            int
    session_id:    Optional[int]
    student_id:    Optional[int]
    type:          str
    severity:      str
    message:       str
    snapshot_path: Optional[str]
    email_sent:    bool
    is_read:       bool
    created_at:    datetime
    student_name:  Optional[str] = None
    session_subject: Optional[str] = None

    class Config:
        from_attributes = True

class AlertMarkRead(BaseModel):
    alert_ids: List[int]


# ── Alert Recipients ──────────────────────────────────────────────────────────

class RecipientCreate(BaseModel):
    email: str
    name:  str

class RecipientOut(BaseModel):
    id:         int
    email:      str
    name:       str
    is_active:  bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Watch List ────────────────────────────────────────────────────────────────

class WatchListOut(BaseModel):
    id:            int
    session_id:    int
    student_id:    int
    checked_in_at: datetime
    last_seen_at:  Optional[datetime]
    warn_15_sent:  bool
    email_20_sent: bool
    is_active:     bool
    student_name:  Optional[str] = None
    student_code:  Optional[str] = None

    class Config:
        from_attributes = True
