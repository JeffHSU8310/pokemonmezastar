"""WebRTC 即時相機掃描：只在畫面清楚且穩定時交付單張影格辨識。"""

from __future__ import annotations

import threading
import time
from typing import Optional, Tuple

import av
import cv2
import numpy as np


def frame_quality(image: np.ndarray) -> Tuple[float, float]:
    scale = min(1.0, 480.0 / max(image.shape[:2]))
    if scale < 1.0:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    return sharpness, brightness


class LiveCardScanner:
    """由 WebRTC 執行緒收集影格，供 Streamlit 主執行緒安全取出。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._latest: Optional[np.ndarray] = None
        self._last_analysis_at = 0.0
        self._sharpness = 0.0
        self._brightness = 0.0

    def ingest(self, image: np.ndarray) -> None:
        sharpness, brightness = frame_quality(image)
        with self._lock:
            self._latest = image.copy()
            self._sharpness = sharpness
            self._brightness = brightness

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        # 預覽串流不做連續辨識；每 0.2 秒更新一次待掃描影格即可。
        now = time.monotonic()
        if now - self._last_analysis_at >= 0.2:
            self._last_analysis_at = now
            self.ingest(frame.to_ndarray(format="bgr24"))
        return frame

    def capture_current(self) -> Tuple[Optional[bytes], Optional[str]]:
        with self._lock:
            if self._latest is None:
                return None, "相機尚未取得畫面，請稍候再按掃描"
            if self._brightness < 32.0:
                return None, "光線不足，請移到較亮的位置"
            if self._brightness > 235.0:
                return None, "畫面過亮，請避開卡匣反光"
            if self._sharpness < 48.0:
                return None, "畫面尚未對焦，請靠近卡匣並保持穩定"
            image = self._latest.copy()
        encoded, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if not encoded:
            return None, "無法擷取目前畫面，請重新掃描"
        return buffer.tobytes(), None
