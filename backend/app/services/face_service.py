"""
Face Recognition Service — InsightFace Buffalo_L
─────────────────────────────────────────────────
• Model: buffalo_l (ArcFace backbone, 512-d embeddings)
• Fast cosine similarity matching
• Embeddings stored as JSON in SQLite (no pgvector needed)
• Thread-safe lazy loading
"""

import json
import logging
import threading
import base64
from io import BytesIO
from typing import Optional, List, Tuple

import cv2
import numpy as np
from PIL import Image
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Student, FaceSample

log = logging.getLogger("smartattend.face")

_model = None
_model_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                log.info("Loading InsightFace model: %s", settings.FACE_MODEL)
                import insightface
                app = insightface.app.FaceAnalysis(
                    name=settings.FACE_MODEL,
                    allowed_modules=["detection", "recognition"],
                    providers=["CPUExecutionProvider"],
                )
                app.prepare(ctx_id=0, det_size=(640, 640))
                _model = app
                log.info("InsightFace model loaded.")
    return _model


# ── Image helpers ─────────────────────────────────────────────────────────────

def _b64_to_bgr(b64: str) -> Optional[np.ndarray]:
    try:
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        data = base64.b64decode(b64)
        img = Image.open(BytesIO(data)).convert("RGB")
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    except Exception as e:
        log.warning("Image decode failed: %s", e)
        return None


def _file_to_bgr(path: str) -> Optional[np.ndarray]:
    img = cv2.imread(path)
    return img


def _extract_embedding(bgr: np.ndarray) -> Optional[List[float]]:
    try:
        app = _get_model()
        faces = app.get(bgr)
        if not faces:
            return None
        # Pick largest face
        face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        return face.normed_embedding.tolist()
    except Exception as e:
        log.warning("Embedding extraction failed: %s", e)
        return None


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    va, vb = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


# ── Public API ────────────────────────────────────────────────────────────────

async def enroll_face(
    student_db_id: int,
    image_b64: str,
    db: AsyncSession,
) -> Tuple[bool, str]:
    bgr = _b64_to_bgr(image_b64)
    if bgr is None:
        return False, "Could not decode image."

    emb = _extract_embedding(bgr)
    if emb is None:
        return False, "No face detected. Please ensure clear lighting and face the camera directly."

    sample = FaceSample(student_id=student_db_id, embedding=json.dumps(emb))
    db.add(sample)
    await db.commit()

    result = await db.execute(
        select(func.count()).where(FaceSample.student_id == student_db_id)
    )
    count = result.scalar()
    return True, f"Sample {count}/{settings.FACE_ENROLLMENT_SAMPLES} enrolled."


async def enroll_face_from_file(
    student_db_id: int,
    file_path: str,
    db: AsyncSession,
) -> Tuple[bool, str]:
    bgr = _file_to_bgr(file_path)
    if bgr is None:
        return False, "Could not read image file."
    emb = _extract_embedding(bgr)
    if emb is None:
        return False, "No face detected in file."
    sample = FaceSample(student_id=student_db_id, embedding=json.dumps(emb))
    db.add(sample)
    await db.commit()
    result = await db.execute(
        select(func.count()).where(FaceSample.student_id == student_db_id)
    )
    count = result.scalar()
    return True, f"Sample {count}/{settings.FACE_ENROLLMENT_SAMPLES} enrolled."


async def recognize_face(
    image_b64: str,
    db: AsyncSession,
    batch_filter: Optional[str] = None,
) -> dict:
    bgr = _b64_to_bgr(image_b64)
    if bgr is None:
        return {"matched": False, "message": "Could not decode image."}

    query_emb = _extract_embedding(bgr)
    if query_emb is None:
        return {"matched": False, "message": "No face detected."}

    # Load all embeddings (with optional batch filter)
    if batch_filter:
        q = (
            select(FaceSample, Student)
            .join(Student, FaceSample.student_id == Student.id)
            .where(Student.is_active == True, Student.batch == batch_filter)
        )
    else:
        q = (
            select(FaceSample, Student)
            .join(Student, FaceSample.student_id == Student.id)
            .where(Student.is_active == True)
        )

    result = await db.execute(q)
    rows = result.all()

    if not rows:
        return {"matched": False, "message": "No enrolled students found."}

    best_sim   = -1.0
    best_student = None

    for sample, student in rows:
        stored_emb = json.loads(sample.embedding)
        sim = _cosine_similarity(query_emb, stored_emb)
        if sim > best_sim:
            best_sim = sim
            best_student = student

    if best_sim < settings.FACE_THRESHOLD:
        return {
            "matched": False,
            "message": f"Face not recognised (similarity={best_sim:.3f}).",
            "confidence": round(best_sim, 4),
        }

    return {
        "matched":    True,
        "student_id": best_student.student_id,
        "name":       best_student.name,
        "confidence": round(best_sim, 4),
        "message":    "Recognised.",
        "_db_id":     best_student.id,
    }


async def recognize_face_from_frame(
    bgr: np.ndarray,
    db: AsyncSession,
    batch_filter: Optional[str] = None,
) -> dict:
    """Same as recognize_face but takes a BGR numpy frame directly."""
    query_emb = _extract_embedding(bgr)
    if query_emb is None:
        return {"matched": False, "message": "No face detected."}

    if batch_filter:
        q = (
            select(FaceSample, Student)
            .join(Student, FaceSample.student_id == Student.id)
            .where(Student.is_active == True, Student.batch == batch_filter)
        )
    else:
        q = (
            select(FaceSample, Student)
            .join(Student, FaceSample.student_id == Student.id)
            .where(Student.is_active == True)
        )

    result = await db.execute(q)
    rows = result.all()

    if not rows:
        return {"matched": False, "message": "No enrolled students."}

    best_sim = -1.0
    best_student = None

    for sample, student in rows:
        stored_emb = json.loads(sample.embedding)
        sim = _cosine_similarity(query_emb, stored_emb)
        if sim > best_sim:
            best_sim = sim
            best_student = student

    if best_sim < settings.FACE_THRESHOLD:
        return {"matched": False, "message": f"Unrecognised (sim={best_sim:.3f})", "confidence": round(best_sim, 4)}

    return {
        "matched":    True,
        "student_id": best_student.student_id,
        "name":       best_student.name,
        "confidence": round(best_sim, 4),
        "message":    "Recognised.",
        "_db_id":     best_student.id,
    }


async def get_enrollment_status(student_db_id: int, db: AsyncSession) -> dict:
    result = await db.execute(
        select(func.count()).where(FaceSample.student_id == student_db_id)
    )
    count = result.scalar()
    return {
        "samples_stored":  count,
        "required_samples": settings.FACE_ENROLLMENT_SAMPLES,
        "is_complete":      count >= settings.FACE_ENROLLMENT_SAMPLES,
    }
