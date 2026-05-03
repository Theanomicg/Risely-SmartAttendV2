"""
Camera Service
──────────────
• Manages RTSP streams from IP cameras.
• Each camera runs in its own background thread.
• Exposes latest frame per camera for the scheduler to grab.
• Supports hot-add / hot-remove of cameras without restart.
"""

import base64
import logging
import os
import threading
import time
from datetime import datetime
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

log = logging.getLogger("smartattend.camera")

# camera_id (int) → latest BGR frame
_latest_frames: Dict[int, Optional[np.ndarray]] = {}
_stream_threads: Dict[int, threading.Thread] = {}
_stop_events: Dict[int, threading.Event] = {}
_camera_status: Dict[int, str] = {}   # "online" | "offline"
_lock = threading.Lock()


# ── Stream reader thread ───────────────────────────────────────────────────────

def _read_stream(camera_id: int, rtsp_url: str, stop_event: threading.Event):
    """Continuously reads frames from an RTSP URL. Reconnects on failure."""
    log.info("Camera %d: starting stream %s", camera_id, rtsp_url)

    def _open():
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
        return cap

    cap = _open()
    fail_count = 0

    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            fail_count += 1
            with _lock:
                _camera_status[camera_id] = "offline"
            if fail_count >= 3:
                log.warning("Camera %d offline — reconnecting in 10s", camera_id)
                cap.release()
                time.sleep(10)
                cap = _open()
                fail_count = 0
            else:
                time.sleep(2)
            continue

        fail_count = 0
        with _lock:
            _latest_frames[camera_id] = frame
            _camera_status[camera_id] = "online"

    cap.release()
    log.info("Camera %d: stream stopped", camera_id)


# ── Public API ─────────────────────────────────────────────────────────────────

def start_camera(camera_id: int, rtsp_url: str):
    """Start (or restart) a stream thread for a camera."""
    stop_camera(camera_id)  # stop existing if any

    stop_event = threading.Event()
    t = threading.Thread(
        target=_read_stream,
        args=(camera_id, rtsp_url, stop_event),
        daemon=True,
        name=f"cam-{camera_id}",
    )
    with _lock:
        _stop_events[camera_id] = stop_event
        _stream_threads[camera_id] = t
        _latest_frames[camera_id] = None
        _camera_status[camera_id] = "unknown"
    t.start()


def stop_camera(camera_id: int):
    """Stop and clean up a camera's stream thread."""
    with _lock:
        event = _stop_events.pop(camera_id, None)
        thread = _stream_threads.pop(camera_id, None)
        _latest_frames.pop(camera_id, None)
        _camera_status.pop(camera_id, None)

    if event:
        event.set()
    if thread and thread.is_alive():
        thread.join(timeout=5)


def stop_all_cameras():
    ids = list(_stream_threads.keys())
    for camera_id in ids:
        stop_camera(camera_id)


def get_latest_frame(camera_id: int) -> Optional[np.ndarray]:
    with _lock:
        return _latest_frames.get(camera_id)


def get_camera_status(camera_id: int) -> str:
    with _lock:
        return _camera_status.get(camera_id, "unknown")


def get_all_statuses() -> Dict[int, str]:
    with _lock:
        return dict(_camera_status)


def capture_frame_b64(camera_id: int) -> Optional[str]:
    """Return latest frame as base64 JPEG, or None if camera offline."""
    frame = get_latest_frame(camera_id)
    if frame is None:
        return None
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    if not ok:
        return None
    return base64.b64encode(buf.tobytes()).decode()


def save_snapshot(frame: np.ndarray, prefix: str = "snap") -> str:
    """Save frame to snapshots/ directory and return path."""
    os.makedirs("snapshots", exist_ok=True)
    ts   = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = f"snapshots/{prefix}_{ts}.jpg"
    cv2.imwrite(path, frame)
    return path


def test_camera_connection(rtsp_url: str) -> Tuple[bool, str, Optional[str]]:
    """
    Try to connect to an RTSP URL and grab one frame.
    Returns (success, message, frame_b64 or None).
    Used by the admin panel to validate a new camera before saving.
    """
    try:
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 8000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 8000)

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return False, "Connected but could not read a frame.", None

        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        b64 = base64.b64encode(buf.tobytes()).decode() if ok else None
        return True, "Connection successful.", b64

    except Exception as e:
        return False, f"Connection failed: {e}", None
