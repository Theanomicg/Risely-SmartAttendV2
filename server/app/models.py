"""
SmartAttend — ORM Models
Tables: teachers, students, face_embeddings, cameras, class_sessions,
        attendance, absent_tracking, alerts
"""

from datetime import datetime, date
from typing import Optional, List
import json
import enum

from sqlalchemy import (
    String, Integer, Float, Boolean, Text, Date, DateTime,
    ForeignKey, Enum as SAEnum, UniqueConstraint, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"
    ABSENT  = "absent"
    LATE    = "late"

class AlertSeverity(str, enum.Enum):
    INFO    = "info"
    WARNING = "warning"
    URGENT  = "urgent"

class AlertType(str, enum.Enum):
    STUDENT_ABSENT_WARNING = "student_absent_warning"   # 15 min
    STUDENT_ABSENT_EMAIL   = "student_absent_email"     # 20 min
    UNRECOGNIZED_FACE      = "unrecognized_face"
    LOW_ATTENDANCE         = "low_attendance"
    CAMERA_OFFLINE         = "camera_offline"
    SYSTEM                 = "system"

class CameraStatus(str, enum.Enum):
    ONLINE  = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


# ── Teachers ──────────────────────────────────────────────────────────────────

class Teacher(Base):
    __tablename__ = "teachers"

    id:         Mapped[int]  = mapped_column(Integer, primary_key=True)
    name:       Mapped[str]  = mapped_column(String(120))
    email:      Mapped[str]  = mapped_column(String(200), unique=True, index=True)
    hashed_pw:  Mapped[str]  = mapped_column(String(256))
    is_admin:   Mapped[bool] = mapped_column(Boolean, default=False)
    is_active:  Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sessions: Mapped[List["ClassSession"]] = relationship(back_populates="teacher")
    alerts:   Mapped[List["Alert"]]        = relationship(back_populates="teacher")


# ── Students ──────────────────────────────────────────────────────────────────

class Student(Base):
    __tablename__ = "students"

    id:           Mapped[int]           = mapped_column(Integer, primary_key=True)
    student_id:   Mapped[str]           = mapped_column(String(40), unique=True, index=True)
    name:         Mapped[str]           = mapped_column(String(120))
    batch:        Mapped[str]           = mapped_column(String(60))
    email:        Mapped[Optional[str]] = mapped_column(String(200))
    phone:        Mapped[Optional[str]] = mapped_column(String(20))
    photo_path:   Mapped[Optional[str]] = mapped_column(String(500))
    is_active:    Mapped[bool]          = mapped_column(Boolean, default=True)
    enrolled_at:  Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)

    embeddings:   Mapped[List["FaceEmbedding"]] = relationship(
                      back_populates="student", cascade="all, delete-orphan"
                  )
    attendances:  Mapped[List["Attendance"]]    = relationship(back_populates="student")
    absent_tracks: Mapped[List["AbsentTracking"]] = relationship(
                      back_populates="student", cascade="all, delete-orphan"
                  )


# ── Face Embeddings (stored as JSON array since no pgvector) ──────────────────

class FaceEmbedding(Base):
    """
    One row per enrollment photo.
    embedding stored as JSON text (512-d float array from InsightFace).
    """
    __tablename__ = "face_embeddings"

    id:         Mapped[int]  = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int]  = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    embedding:  Mapped[str]  = mapped_column(Text)   # JSON array string
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped["Student"] = relationship(back_populates="embeddings")

    def get_vector(self):
        import numpy as np
        return np.array(json.loads(self.embedding), dtype=np.float32)


# ── Cameras ───────────────────────────────────────────────────────────────────

class Camera(Base):
    """A physical classroom camera (RTSP stream)."""
    __tablename__ = "cameras"

    id:          Mapped[int]           = mapped_column(Integer, primary_key=True)
    name:        Mapped[str]           = mapped_column(String(120))      # "Lab-1 Front"
    location:    Mapped[Optional[str]] = mapped_column(String(200))      # "Room 301, Building A"
    rtsp_url:    Mapped[str]           = mapped_column(String(500), unique=True)
    username:    Mapped[Optional[str]] = mapped_column(String(100))
    password:    Mapped[Optional[str]] = mapped_column(String(100))
    is_active:   Mapped[bool]          = mapped_column(Boolean, default=True)
    status:      Mapped[CameraStatus]  = mapped_column(
                     SAEnum(CameraStatus), default=CameraStatus.UNKNOWN
                 )
    last_seen:   Mapped[Optional[datetime]] = mapped_column(DateTime)
    snapshot_path: Mapped[Optional[str]]    = mapped_column(String(500))
    created_at:  Mapped[datetime]           = mapped_column(DateTime, default=datetime.utcnow)
    notes:       Mapped[Optional[str]]      = mapped_column(Text)

    sessions: Mapped[List["ClassSession"]] = relationship(back_populates="camera")


# ── Class Sessions ─────────────────────────────────────────────────────────────

class ClassSession(Base):
    __tablename__ = "class_sessions"

    id:         Mapped[int]           = mapped_column(Integer, primary_key=True)
    teacher_id: Mapped[int]           = mapped_column(ForeignKey("teachers.id"))
    camera_id:  Mapped[Optional[int]] = mapped_column(ForeignKey("cameras.id"))
    subject:    Mapped[str]           = mapped_column(String(120))
    batch:      Mapped[str]           = mapped_column(String(60))
    room:       Mapped[Optional[str]] = mapped_column(String(60))
    started_at: Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)
    ended_at:   Mapped[Optional[datetime]] = mapped_column(DateTime)

    teacher:     Mapped["Teacher"]           = relationship(back_populates="sessions")
    camera:      Mapped[Optional["Camera"]]  = relationship(back_populates="sessions")
    attendances: Mapped[List["Attendance"]]  = relationship(back_populates="session")
    alerts:      Mapped[List["Alert"]]       = relationship(back_populates="session")
    absent_tracks: Mapped[List["AbsentTracking"]] = relationship(
                       back_populates="session", cascade="all, delete-orphan"
                   )


# ── Attendance ─────────────────────────────────────────────────────────────────

class Attendance(Base):
    __tablename__ = "attendance"

    id:          Mapped[int]              = mapped_column(Integer, primary_key=True)
    student_id:  Mapped[int]              = mapped_column(ForeignKey("students.id"))
    session_id:  Mapped[int]              = mapped_column(ForeignKey("class_sessions.id"))
    date:        Mapped[date]             = mapped_column(Date, default=date.today)
    status:      Mapped[AttendanceStatus] = mapped_column(
                     SAEnum(AttendanceStatus), default=AttendanceStatus.ABSENT
                 )
    marked_at:   Mapped[Optional[datetime]] = mapped_column(DateTime)
    confidence:  Mapped[Optional[float]]    = mapped_column(Float)
    source:      Mapped[str]                = mapped_column(String(20), default="kiosk")
    # "kiosk" | "classroom" | "manual"

    student: Mapped["Student"]      = relationship(back_populates="attendances")
    session: Mapped["ClassSession"] = relationship(back_populates="attendances")

    __table_args__ = (
        UniqueConstraint("student_id", "session_id", "date", name="uq_attendance"),
    )


# ── Absent Tracking ────────────────────────────────────────────────────────────

class AbsentTracking(Base):
    """
    Tracks how long a checked-in student has been unseen by the classroom camera.
    Created when a student checks in at kiosk. Reset when camera re-spots them.
    Drives the 15-min warning and 20-min email alerts.
    """
    __tablename__ = "absent_tracking"

    id:                  Mapped[int]           = mapped_column(Integer, primary_key=True)
    student_id:          Mapped[int]           = mapped_column(ForeignKey("students.id"))
    session_id:          Mapped[int]           = mapped_column(ForeignKey("class_sessions.id"))
    last_seen_at:        Mapped[Optional[datetime]] = mapped_column(DateTime)
    # How long continuously unseen (seconds)
    consecutive_absent_seconds: Mapped[int]   = mapped_column(Integer, default=0)
    warning_sent:        Mapped[bool]          = mapped_column(Boolean, default=False)
    email_sent:          Mapped[bool]          = mapped_column(Boolean, default=False)
    is_active:           Mapped[bool]          = mapped_column(Boolean, default=True)
    created_at:          Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped["Student"]      = relationship(back_populates="absent_tracks")
    session: Mapped["ClassSession"] = relationship(back_populates="absent_tracks")

    __table_args__ = (
        UniqueConstraint("student_id", "session_id", name="uq_tracking"),
    )


# ── Alerts ─────────────────────────────────────────────────────────────────────

class Alert(Base):
    __tablename__ = "alerts"

    id:            Mapped[int]           = mapped_column(Integer, primary_key=True)
    teacher_id:    Mapped[Optional[int]] = mapped_column(ForeignKey("teachers.id"))
    session_id:    Mapped[Optional[int]] = mapped_column(ForeignKey("class_sessions.id"))
    student_id:    Mapped[Optional[int]] = mapped_column(ForeignKey("students.id"))
    type:          Mapped[AlertType]     = mapped_column(SAEnum(AlertType))
    severity:      Mapped[AlertSeverity] = mapped_column(
                       SAEnum(AlertSeverity), default=AlertSeverity.INFO
                   )
    message:       Mapped[str]           = mapped_column(Text)
    snapshot_path: Mapped[Optional[str]] = mapped_column(String(500))
    is_read:       Mapped[bool]          = mapped_column(Boolean, default=False)
    created_at:    Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)

    teacher: Mapped[Optional["Teacher"]]      = relationship(back_populates="alerts")
    session: Mapped[Optional["ClassSession"]] = relationship(back_populates="alerts")
    student: Mapped[Optional["Student"]]      = relationship()
