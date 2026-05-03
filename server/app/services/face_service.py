"""
Face Recognition Service — InsightFace buffalo_l
─────────────────────────────────────────────────
• buffalo_l: ArcFace R100 backbone, 512-d embeddings
• Enrollment: store N embeddings per student as JSON in SQLite
• Recognition: cosine similarity against all enrolled embeddings
• No GPU required — onnxruntime CPU works fine for ~1000 students
"""

import base64
import json
import logging
import os
from io import BytesIO
from typing import Optional, Tuple, List

import cv2
import numpy as np
from PIL import Image
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Student, FaceEmbedding

log = logging.getLogger("smartattend.face")

# Lazy-loaded InsightFace app
_face_app = None


def _get_face_app():
    global _face_app
    if _face_app is None:
        import insightface
        from insightface.app import FaceAnalysis
        log.info("Loading InsightFace model: %s", settings.FACE_MODEL)
        _face_app = FaceAnalysis(
            name=settings.FACE_MODEL,
            providers=["CPUExecutionProvider"],
        )
        _face_app.prepare(ctx_id=0, det_size=(640, 640))
        log.info("InsightFace ready.")
    return _face_app


# ── Image helpers ─────────────────────────────────────────────────────────────

def decode_b64_image(b64: str) -> np.ndarray:
    """Decode base64 JPEG/PNG → BGR numpy array (OpenCV format)."""
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    data = base64.b64decode(b64)
    img = Image.open(BytesIO(data)).convert("RGB")
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def frame_to_b64(frame: np.ndarray) -> str:
    """BGR numpy → base64 JPEG string."""
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
    return base64.b64encode(buf.tobytes()).decode()


def _extract_embedding(img_bgr: np.ndarray) -> Optional[List[float]]:
    """
    Extract a 512-d ArcFace embedding from a BGR frame.
    Returns None if no face is detected.
    """
    app = _get_face_app()
    faces = app.get(img_bgr)
    if not faces:
        return None
    # Pick largest face if multiple detected
    face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    emb = face.normed_embedding  # already L2-normalised
    return emb.tolist()


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two L2-normalised vectors (range 0–1)."""
    return float(np.dot(a, b))


# ── Enrollment ────────────────────────────────────────────────────────────────

async def enroll_face(
    student_db_id: int,
    image_b64: str,
    db: AsyncSession,
) -> Tuple[bool, str, int]:
    """
    Enroll one face sample.
    Returns (success, message, total_samples).
    """
    img = decode_b64_image(image_b64)
    embedding = _extract_embedding(img)
    if embedding is None:
        return False, "No face detected — please face the camera directly.", 0

    fe = FaceEmbedding(
        student_id=student_db_id,
        embedding=json.dumps(embedding),
    )
    db.add(fe)
    await db.commit()

    result = await db.execute(
        select(func.count()).where(FaceEmbedding.student_id == student_db_id)
    )
    count = int(result.scalar())
    complete = count >= settings.FACE_ENROLLMENT_SAMPLES
    msg = (
        f"Enrolled sample {count}/{settings.FACE_ENROLLMENT_SAMPLES}."
        if not complete
        else f"Enrollment complete! ({count} samples stored)"
    )
    return True, msg, count


async def get_enrollment_status(student_db_id: int, db: AsyncSession) -> dict:
    result = await db.execute(
        select(func.count()).where(FaceEmbedding.student_id == student_db_id)
    )
    count = int(result.scalar())
    return {
        "samples_stored": count,
        "required_samples": settings.FACE_ENROLLMENT_SAMPLES,
        "enrollment_complete": count >= settings.FACE_ENROLLMENT_SAMPLES,
    }


# ── Recognition ───────────────────────────────────────────────────────────────

async def recognize_face(
    image_b64: str,
    db: AsyncSession,
    batch_filter: Optional[str] = None,
) -> dict:
    """
    Recognise a face against all enrolled embeddings.
    Optionally filter to a specific batch for faster search.
    Returns dict compatible with RecognitionResult schema.
    """
    img = decode_b64_image(image_b64)
    query_emb = _extract_embedding(img)

    if query_emb is None:
        return {"matched": False, "message": "No face detected — please try again."}

    query_vec = np.array(query_emb, dtype=np.float32)

    # Load all relevant embeddings
    q = (
        select(FaceEmbedding, Student)
        .join(Student, FaceEmbedding.student_id == Student.id)
        .where(Student.is_active == True)
    )
    if batch_filter:
        q = q.where(Student.batch == batch_filter)

    result = await db.execute(q)
    rows = result.all()

    if not rows:
        return {"matched": False, "message": "No enrolled students found."}

    best_sim = -1.0
    best_student = None

    for fe, student in rows:
        db_vec = fe.get_vector()
        sim = cosine_similarity(query_vec, db_vec)
        if sim > best_sim:
            best_sim = sim
            best_student = student

    if best_sim < settings.FACE_THRESHOLD:
        return {
            "matched": False,
            "message": f"Face not recognised (similarity={best_sim:.3f}).",
            "confidence": round(float(best_sim), 4),
        }

    return {
        "matched": True,
        "student_id": best_student.student_id,
        "name": best_student.name,
        "confidence": round(float(best_sim), 4),
        "message": "Recognised.",
    }


def recognize_face_sync(
    img_bgr: np.ndarray,
    stored_embeddings: List[Tuple[int, np.ndarray]],  # [(student_db_id, vector)]
) -> Tuple[Optional[int], float]:
    """
    Synchronous recognition used by camera monitor thread.
    Returns (student_db_id, similarity) or (None, 0.0).
    """
    query_emb = _extract_embedding(img_bgr)
    if query_emb is None:
        return None, 0.0

    query_vec = np.array(query_emb, dtype=np.float32)
    best_id  = None
    best_sim = -1.0

    for student_db_id, db_vec in stored_embeddings:
        sim = cosine_similarity(query_vec, db_vec)
        if sim > best_sim:
            best_sim = sim
            best_id  = student_db_id

    if best_sim < settings.FACE_THRESHOLD:
        return None, float(best_sim)
    return best_id, float(best_sim)
