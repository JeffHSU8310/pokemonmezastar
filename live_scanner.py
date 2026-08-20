"""WebRTC 即時相機掃描：只在畫面清楚且穩定時交付單張影格辨識。"""

from __future__ import annotations

import threading
import time
from typing import Optional, Tuple

import av
import cv2
import numpy as np


def frame_quality(image: np.ndarray) -> Tuple[float, float]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    return sharpness, brightness


class LiveCardScanner:
    """由 WebRTC 執行緒收集影格，供 Streamlit 主執行緒安全取出。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._latest: Optional[np.ndarray] = None
        self._previous_gray: Optional[np.ndarray] = None
        self._stable_frames = 0
        self._last_capture_at = 0.0
        self._sharpness = 0.0
        self._brightness = 0.0

    def ingest(self, image: np.ndarray) -> None:
        preview_gray = cv2.resize(
            cv2.cvtColor(image, cv2.COLOR_BGR2GRAY),
            (160, 120),
            interpolation=cv2.INTER_AREA,
        )
        sharpness, brightness = frame_quality(image)
        with self._lock:
            if self._previous_gray is None:
                motion = 255.0
            else:
                motion = float(cv2.absdiff(preview_gray, self._previous_gray).mean())
            self._stable_frames = self._stable_frames + 1 if motion < 11.0 else 0
            self._previous_gray = preview_gray
            self._latest = image.copy()
            self._sharpness = sharpness
            self._brightness = brightness

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        self.ingest(frame.to_ndarray(format="bgr24"))
        return frame

    def status(self) -> Tuple[float, float, int]:
        with self._lock:
            return self._sharpness, self._brightness, self._stable_frames

    def pop_candidate(self, minimum_interval: float = 2.0) -> Optional[bytes]:
        now = time.monotonic()
        with self._lock:
            ready = (
                self._latest is not None
                and self._stable_frames >= 5
                and self._sharpness >= 48.0
                and 32.0 <= self._brightness <= 235.0
                and now - self._last_capture_at >= minimum_interval
            )
            if not ready:
                return None
            image = self._latest.copy()
            self._last_capture_at = now
            self._stable_frames = 0
        encoded, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return buffer.tobytes() if encoded else None
