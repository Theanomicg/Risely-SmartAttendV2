"""
Camera Service
─────────────────
• Manages RTSP streams in background threads
• Provides latest frames for scheduler face-recognition checks
• Health monitoring with reconnect logic
• Supports adding/removing cameras at runtime
"""

import base64
import logging
import os
import threading
import time
from datetime import datetime
from typing import Dict, Optional

import cv2
import numpy as np

log = logging.getLogger("smartattend.camera")

# Thread-safe state
_frames:       Dict[str, Optional[np.ndarray]]  = {}
_threads:      Dict[str, threading.Thread]       = {}
_stop_events:  Dict[str, threading.Event]        = {}
_status:       Dict[str, dict]                   = {}
_lock = threading.Lock()


def _stream_worker(url: str, stop_event: threading.Event):
    log.info("Camera stream starting: %s", url)
    reconnect_delay = 5

    while not stop_event.is_set():
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            log.warning("Cannot open stream: %s — retry in %ds", url, reconnect_delay)
            with _lock:
                _status[url] = {"online": False, "last_seen": None, "error": "Cannot open stream"}
            stop_event.wait(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 60)
            continue

        reconnect_delay = 5
        log.info("Stream connected: %s", url)
        with _lock:
            _status[url] = {"online": True, "last_seen": datetime.utcnow().isoformat(), "error": None}

        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                log.warning("Frame read failed for %s", url)
                with _lock:
                    _status[url] = {"online": False, "last_seen": _status[url].get("last_seen"), "error": "Frame read failed"}
                break
            with _lock:
                _frames[url] = frame
                _status[url]["online"] = True
                _status[url]["last_seen"] = datetime.utcnow().isoformat()

        cap.release()
        if not stop_event.is_set():
            log.info("Reconnecting stream %s in %ds", url, reconnect_delay)
            stop_event.wait(reconnect_delay)

    log.info("Camera stream stopped: %s", url)


def add_camera(url: str):
    """Start streaming from a new RTSP URL."""
    with _lock:
        if url in _threads and _threads[url].is_alive():
            return  # Already running
        _frames[url] = None
        _status[url] = {"online": False, "last_seen": None, "error": None}

    stop_event = threading.Event()
    t = threading.Thread(target=_stream_worker, args=(url, stop_event), daemon=True)
    _stop_events[url] = stop_event
    _threads[url] = t
    t.start()


def remove_camera(url: str):
    """Stop streaming from an RTSP URL."""
    if url in _stop_events:
        _stop_events[url].set()
    with _lock:
        _frames.pop(url, None)
        _status.pop(url, None)


def start_all_streams(urls: list):
    for url in urls:
        add_camera(url)


def stop_all_streams():
    for event in _stop_events.values():
        event.set()
    for t in _threads.values():
        t.join(timeout=3)


def get_latest_frame(url: str) -> Optional[np.ndarray]:
    with _lock:
        return _frames.get(url)


def capture_frame_b64(url: str, quality: int = 70) -> Optional[str]:
    frame = get_latest_frame(url)
    if frame is None:
        return None
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return None
    return base64.b64encode(buf.tobytes()).decode()


def save_snapshot(frame: np.ndarray, prefix: str = "snap", snapshots_dir: str = "./snapshots") -> str:
    os.makedirs(snapshots_dir, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    path = os.path.join(snapshots_dir, f"{prefix}_{ts}.jpg")
    cv2.imwrite(path, frame)
    return path


def get_all_stream_status() -> dict:
    with _lock:
        return dict(_status)


def get_stream_status(url: str) -> dict:
    with _lock:
        return _status.get(url, {"online": False, "last_seen": None, "error": "Not configured"})


def test_camera_connection(url: str, timeout: int = 8) -> dict:
    """
    Test if a camera URL is reachable. Returns status dict.
    Used when adding a new camera from the admin panel.
    """
    try:
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)
        start = time.time()

        opened = cap.isOpened()
        if not opened:
            cap.release()
            return {"success": False, "message": "Cannot connect to camera stream."}

        ret, frame = cap.read()
        elapsed = round(time.time() - start, 2)
        cap.release()

        if not ret or frame is None:
            return {"success": False, "message": "Connected but could not grab frame."}

        h, w = frame.shape[:2]
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
        preview_b64 = base64.b64encode(buf.tobytes()).decode() if ok else None

        return {
            "success":    True,
            "message":    f"Connected — {w}×{h} @ {elapsed}s",
            "resolution": f"{w}x{h}",
            "preview_b64": preview_b64,
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
