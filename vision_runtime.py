"""集中載入 OpenCV，避免原生套件故障時拖垮整個 Streamlit 應用。"""

from __future__ import annotations

from typing import Any, Optional


_opencv_import_error: Optional[BaseException] = None
try:
    import cv2 as _cv2
except Exception as exc:  # OpenCV 原生函式庫也可能丟出 ImportError 以外的載入錯誤。
    _cv2 = None
    _opencv_import_error = exc

cv2: Any = _cv2


def opencv_available() -> bool:
    return cv2 is not None


def opencv_error_message() -> str:
    if _opencv_import_error is None:
        return ""
    return f"相機影像引擎載入失敗：{_opencv_import_error}"


def require_opencv() -> Any:
    if cv2 is None:
        raise RuntimeError(opencv_error_message() or "相機影像引擎目前無法使用")
    return cv2
