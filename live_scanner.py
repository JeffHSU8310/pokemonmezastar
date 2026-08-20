"""WebRTC 即時相機掃描：只在畫面清楚且穩定時交付單張影格辨識。"""

from __future__ import annotations

from collections import deque
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
        self._recent_frames = deque(maxlen=6)
        self._last_analysis_at = 0.0

    def ingest(self, image: np.ndarray) -> None:
        sharpness, brightness = frame_quality(image)
        with self._lock:
            self._recent_frames.append((sharpness, brightness, image.copy()))

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        # 預覽串流不做連續辨識；每 0.2 秒更新一次待掃描影格即可。
        now = time.monotonic()
        if now - self._last_analysis_at >= 0.2:
            self._last_analysis_at = now
            self.ingest(frame.to_ndarray(format="bgr24"))
        return frame

    def capture_current(self) -> Tuple[Optional[bytes], Optional[str], float]:
        with self._lock:
            if not self._recent_frames:
                return None, "相機尚未取得畫面，請稍候再按掃描", 0.0
            properly_exposed = [item for item in self._recent_frames if 32.0 <= item[1] <= 235.0]
            if not properly_exposed:
                average_brightness = sum(item[1] for item in self._recent_frames) / len(self._recent_frames)
                message = "光線不足，請移到較亮的位置" if average_brightness < 32.0 else "畫面過亮，請避開卡匣反光"
                return None, message, 0.0
            # 按下掃描時，從最近約一秒影格中挑選最清楚的一張。
            sharpness, _, image = max(properly_exposed, key=lambda item: item[0])
            if sharpness < 48.0:
                return None, f"畫面尚未對焦（清晰度 {sharpness:.0f}），請靠近卡匣、等待自動對焦並保持穩定", sharpness
            image = image.copy()
        encoded, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if not encoded:
            return None, "無法擷取目前畫面，請重新掃描", sharpness
        return buffer.tobytes(), None, sharpness
