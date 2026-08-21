"""WebRTC 即時相機掃描：只在畫面清楚且穩定時交付單張影格辨識。"""

from __future__ import annotations

from collections import deque
import threading
import time
from typing import Optional, Tuple

import av
import numpy as np

from vision_runtime import cv2, require_opencv


def frame_quality(image: np.ndarray) -> Tuple[float, float]:
    require_opencv()
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
        # 約保留最近一秒的高頻影格。按下掃描時從中挑選最清楚的一張，
        # 避免剛好取到手機鏡頭仍在重新對焦的單一模糊畫面。
        self._recent_frames = deque(maxlen=12)
        self._last_analysis_at = 0.0
        self._latest_resolution = (0, 0)

    def ingest(self, image: np.ndarray) -> None:
        sharpness, brightness = frame_quality(image)
        with self._lock:
            self._recent_frames.append((sharpness, brightness, image.copy()))
            self._latest_resolution = (int(image.shape[1]), int(image.shape[0]))

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        # 預覽串流不做連續辨識；每秒最多取樣約 12 張供手動掃描挑選。
        # 不再在伺服器端裁切、放大或重採樣，完整保留相機原始解析度供辨識。
        image = frame.to_ndarray(format="bgr24")
        now = time.monotonic()
        if now - self._last_analysis_at >= 1.0 / 12.0:
            self._last_analysis_at = now
            # 保存沒有提示框與文字的乾淨畫面，避免影響 OCR 與卡面比對。
            self.ingest(image)

        preview = image.copy()
        height, width = preview.shape[:2]
        guide_left, guide_right = int(width * 0.07), int(width * 0.93)
        guide_top, guide_bottom = int(height * 0.10), int(height * 0.90)
        cv2.rectangle(preview, (guide_left, guide_top), (guide_right, guide_bottom), (40, 220, 90), 4)
        cv2.putText(
            preview,
            "HD SCAN | AUTO FOCUS",
            (guide_left + 10, max(32, guide_top - 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            max(0.55, width / 1200.0),
            (40, 220, 90),
            2,
            cv2.LINE_AA,
        )
        return av.VideoFrame.from_ndarray(preview, format="bgr24")

    @property
    def latest_resolution(self) -> Tuple[int, int]:
        with self._lock:
            return self._latest_resolution

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
            # 下一次掃描只能使用擷取完成後的新影格，避免換卡時挑到上一張卡。
            self._recent_frames.clear()
        # 辨識使用原始相機影格，不沿用 WebRTC 回傳預覽的壓縮畫面。
        encoded, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 97])
        if not encoded:
            return None, "無法擷取目前畫面，請重新掃描", sharpness
        return buffer.tobytes(), None, sharpness
