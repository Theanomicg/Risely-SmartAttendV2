"""
SmartAttend v2 — Database Models
"""

from datetime import datetime, date
from typing import Optional, List
import enum

from sqlalchemy import (
    String, Integer, Float, Boolean, Text, Date, DateTime,
    ForeignKey, Enum as SAEnum, UniqueConstraint, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class AttendanceStatus(str, enum.Enum):
    PRESENT  = "present"
    ABSENT   = "absent"
    LATE     = "late"

class AlertType(str, enum.Enum):
    STUDENT_MISSING_15   = "student_missing_15"
    STUDENT_MISSING_20   = "student_missing_20"
    STUDENT_LEFT         = "student_left"
    UNRECOGNIZED_FACE    = "unrecognized_face"
    CAMERA_OFFLINE       = "camera_offline"
    CAMERA_RECONNECTED   = "camera_reconnected"
    SYSTEM               = "system"

class AlertSeverity(str, enum.Enum):
    INFO    = "info"
    WARNING = "warning"
    URGENT  = "urgent"

class CameraStatus(str, enum.Enum):
    ONLINE   = "online"
    OFFLINE  = "offline"
    UNKNOWN  = "unknown"


# ── Admin Users ───────────────────────────────────────────────────────────────

class Admin(Base):
    __tablename__ = "admins"

    id:         Mapped[int]      = mapped_column(Integer, primary_key=True)
    name:       Mapped[str]      = mapped_column(String(120))
    email:      Mapped[str]      = mapped_column(String(200), unique=True, index=True)
    hashed_pw:  Mapped[str]      = mapped_column(String(256))
    is_active:  Mapped[bool]     = mapped_column(Boolean, default=True)
    role:       Mapped[str]      = mapped_column(String(20), default="admin")  # admin | superadmin
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sessions: Mapped[List["ClassSession"]] = relationship(back_populates="teacher")
    alerts:   Mapped[List["Alert"]]        = relationship(back_populates="teacher")


# ── Students ──────────────────────────────────────────────────────────────────

class Student(Base):
    __tablename__ = "students"

    id:          Mapped[int]           = mapped_column(Integer, primary_key=True)
    student_id:  Mapped[str]           = mapped_column(String(40), unique=True, index=True)
    name:        Mapped[str]           = mapped_column(String(120))
    batch:       Mapped[str]           = mapped_column(String(60))
    email:       Mapped[Optional[str]] = mapped_column(String(200))
    phone:       Mapped[Optional[str]] = mapped_column(String(20))
    photo_path:  Mapped[Optional[str]] = mapped_column(String(500))
    is_active:   Mapped[bool]          = mapped_column(Boolean, default=True)
    enrolled_at: Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)

    face_samples: Mapped[List["FaceSample"]]  = relationship(back_populates="student", cascade="all, delete-orphan")
    attendances:  Mapped[List["Attendance"]]  = relationship(back_populates="student")


# ── Face Samples (InsightFace 512-d embeddings stored as JSON) ─────────────────

class FaceSample(Base):
    __tablename__ = "face_samples"

    id:         Mapped[int]      = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int]      = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    embedding:  Mapped[str]      = mapped_column(Text)   # JSON list of 512 floats
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped["Student"] = relationship(back_populates="face_samples")


# ── Cameras ───────────────────────────────────────────────────────────────────

class Camera(Base):
    __tablename__ = "cameras"

    id:          Mapped[int]           = mapped_column(Integer, primary_key=True)
    name:        Mapped[str]           = mapped_column(String(120))
    location:    Mapped[str]           = mapped_column(String(200))   # "Room A", "Lab-1" etc.
    rtsp_url:    Mapped[str]           = mapped_column(String(500))
    status:      Mapped[str]           = mapped_column(String(20), default="unknown")
    last_seen:   Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_active:   Mapped[bool]          = mapped_column(Boolean, default=True)
    created_at:  Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)
    notes:       Mapped[Optional[str]] = mapped_column(Text)

    sessions: Mapped[List["ClassSession"]] = relationship(back_populates="camera")


# ── Class Sessions ────────────────────────────────────────────────────────────

class ClassSession(Base):
    __tablename__ = "class_sessions"

    id:         Mapped[int]           = mapped_column(Integer, primary_key=True)
    teacher_id: Mapped[int]           = mapped_column(ForeignKey("admins.id"))
    camera_id:  Mapped[Optional[int]] = mapped_column(ForeignKey("cameras.id"))
    subject:    Mapped[str]           = mapped_column(String(120))
    batch:      Mapped[str]           = mapped_column(String(60))
    room:       Mapped[Optional[str]] = mapped_column(String(60))
    started_at: Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)
    ended_at:   Mapped[Optional[datetime]] = mapped_column(DateTime)

    teacher:     Mapped["Admin"]           = relationship(back_populates="sessions")
    camera:      Mapped[Optional["Camera"]] = relationship(back_populates="sessions")
    attendances: Mapped[List["Attendance"]] = relationship(back_populates="session")
    alerts:      Mapped[List["Alert"]]      = relationship(back_populates="session")
    watch_list:  Mapped[List["SessionWatchList"]] = relationship(back_populates="session", cascade="all, delete-orphan")


# ── Session Watch List (students the camera must track) ───────────────────────

class SessionWatchList(Base):
    """
    When a student checks in via kiosk, they're added here.
    Scheduler checks frames for each student in this list.
    When the student leaves (or session ends) they're removed.
    """
    __tablename__ = "session_watch_list"

    id:              Mapped[int]           = mapped_column(Integer, primary_key=True)
    session_id:      Mapped[int]           = mapped_column(ForeignKey("class_sessions.id", ondelete="CASCADE"))
    student_id:      Mapped[int]           = mapped_column(ForeignKey("students.id"))
    checked_in_at:   Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at:    Mapped[Optional[datetime]] = mapped_column(DateTime)
    warn_15_sent:    Mapped[bool]          = mapped_column(Boolean, default=False)
    email_20_sent:   Mapped[bool]          = mapped_column(Boolean, default=False)
    is_active:       Mapped[bool]          = mapped_column(Boolean, default=True)  # False = left class

    session: Mapped["ClassSession"] = relationship(back_populates="watch_list")
    student: Mapped["Student"]      = relationship()

    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_session_student"),
    )


# ── Attendance ────────────────────────────────────────────────────────────────

class Attendance(Base):
    __tablename__ = "attendance"

    id:         Mapped[int]              = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int]              = mapped_column(ForeignKey("students.id"))
    session_id: Mapped[int]              = mapped_column(ForeignKey("class_sessions.id"))
    date:       Mapped[date]             = mapped_column(Date, default=date.today)
    status:     Mapped[AttendanceStatus] = mapped_column(SAEnum(AttendanceStatus), default=AttendanceStatus.ABSENT)
    marked_at:  Mapped[Optional[datetime]] = mapped_column(DateTime)
    confidence: Mapped[Optional[float]]  = mapped_column(Float)
    source:     Mapped[str]              = mapped_column(String(20), default="kiosk")

    student: Mapped["Student"]      = relationship(back_populates="attendances")
    session: Mapped["ClassSession"] = relationship(back_populates="attendances")

    __table_args__ = (
        UniqueConstraint("student_id", "session_id", "date", name="uq_attendance"),
    )


# ── Alerts ────────────────────────────────────────────────────────────────────

class Alert(Base):
    __tablename__ = "alerts"

    id:            Mapped[int]           = mapped_column(Integer, primary_key=True)
    teacher_id:    Mapped[Optional[int]] = mapped_column(ForeignKey("admins.id"))
    session_id:    Mapped[Optional[int]] = mapped_column(ForeignKey("class_sessions.id"))
    student_id:    Mapped[Optional[int]] = mapped_column(ForeignKey("students.id"))
    type:          Mapped[AlertType]     = mapped_column(SAEnum(AlertType))
    severity:      Mapped[AlertSeverity] = mapped_column(SAEnum(AlertSeverity), default=AlertSeverity.INFO)
    message:       Mapped[str]           = mapped_column(Text)
    snapshot_path: Mapped[Optional[str]] = mapped_column(String(500))
    email_sent:    Mapped[bool]          = mapped_column(Boolean, default=False)
    is_read:       Mapped[bool]          = mapped_column(Boolean, default=False)
    created_at:    Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)

    teacher: Mapped[Optional["Admin"]]         = relationship(back_populates="alerts")
    session: Mapped[Optional["ClassSession"]]  = relationship(back_populates="alerts")
    student: Mapped[Optional["Student"]]       = relationship()


# ── Alert Email Recipients (configurable from admin panel) ────────────────────

class AlertRecipient(Base):
    __tablename__ = "alert_recipients"

    id:         Mapped[int]  = mapped_column(Integer, primary_key=True)
    email:      Mapped[str]  = mapped_column(String(200), unique=True)
    name:       Mapped[str]  = mapped_column(String(120))
    is_active:  Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
