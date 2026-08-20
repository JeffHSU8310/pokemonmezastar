"""卡匣辨識回饋學習：只保存不可還原成照片的影像特徵。"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import threading
from typing import Any, Dict, Optional

import numpy as np

from vision_runtime import cv2, require_opencv


DEFAULT_LEARNING_PATH = Path(__file__).resolve().parent / "data" / "recognition_learning.json"
_FILE_LOCK = threading.Lock()


def _decode(image_bytes: bytes) -> np.ndarray:
    require_opencv()
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("無法建立學習特徵")
    return image


def image_signature(image_bytes: bytes) -> Dict[str, Any]:
    image = _decode(image_bytes)
    gray = cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (9, 8), interpolation=cv2.INTER_AREA)
    bits = (gray[:, 1:] > gray[:, :-1]).flatten()
    hash_value = 0
    for bit in bits:
        hash_value = (hash_value << 1) | int(bit)

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    histogram = cv2.calcHist([hsv], [0, 1], None, [12, 4], [0, 180, 0, 256]).flatten()
    norm = float(np.linalg.norm(histogram))
    if norm:
        histogram /= norm
    return {
        "dhash": f"{hash_value:016x}",
        "histogram": [round(float(value), 6) for value in histogram],
    }


def _empty_data() -> Dict[str, Any]:
    return {"version": 1, "examples": []}


def load_learning_data(path: Path = DEFAULT_LEARNING_PATH) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("examples"), list):
            return data
    except (OSError, ValueError, TypeError):
        pass
    return _empty_data()


def _signature_similarity(left: Dict[str, Any], right: Dict[str, Any]) -> float:
    try:
        xor = int(left["dhash"], 16) ^ int(right["dhash"], 16)
        hash_similarity = 1.0 - xor.bit_count() / 64.0
        left_hist = np.asarray(left["histogram"], dtype=np.float32)
        right_hist = np.asarray(right["histogram"], dtype=np.float32)
        if left_hist.shape != right_hist.shape or left_hist.size == 0:
            return 0.0
        denominator = float(np.linalg.norm(left_hist) * np.linalg.norm(right_hist))
        histogram_similarity = max(0.0, float(np.dot(left_hist, right_hist)) / denominator) if denominator else 0.0
        return max(0.0, min(1.0, hash_similarity * 0.62 + histogram_similarity * 0.38))
    except (KeyError, TypeError, ValueError):
        return 0.0


def learning_adjustments(image_bytes: bytes, path: Path = DEFAULT_LEARNING_PATH) -> Dict[str, float]:
    query = image_signature(image_bytes)
    data = load_learning_data(path)
    positive: Dict[str, float] = {}
    negative: Dict[str, float] = {}
    for example in data["examples"]:
        similarity = _signature_similarity(query, example)
        if similarity < 0.58:
            continue
        correct_id = str(example.get("correct_card_id", ""))
        rejected_id = str(example.get("rejected_card_id", ""))
        if correct_id:
            positive[correct_id] = max(positive.get(correct_id, 0.0), similarity)
        if rejected_id and rejected_id != correct_id:
            negative[rejected_id] = max(negative.get(rejected_id, 0.0), similarity)
    card_ids = set(positive) | set(negative)
    return {
        card_id: round(positive.get(card_id, 0.0) - negative.get(card_id, 0.0) * 0.45, 4)
        for card_id in card_ids
    }


def record_confirmation(
    image_bytes: bytes,
    correct_card_id: str,
    rejected_card_id: Optional[str] = None,
    path: Path = DEFAULT_LEARNING_PATH,
) -> int:
    signature = image_signature(image_bytes)
    with _FILE_LOCK:
        data = load_learning_data(path)
        examples = data["examples"]
        duplicate = next(
            (
                item for item in examples
                if str(item.get("correct_card_id")) == str(correct_card_id)
                and _signature_similarity(signature, item) >= 0.97
            ),
            None,
        )
        if duplicate:
            duplicate["confirmations"] = int(duplicate.get("confirmations", 1)) + 1
            duplicate["updated_at"] = datetime.now().isoformat(timespec="seconds")
            if rejected_card_id and str(rejected_card_id) != str(correct_card_id):
                duplicate["rejected_card_id"] = str(rejected_card_id)
        else:
            examples.append({
                **signature,
                "correct_card_id": str(correct_card_id),
                "rejected_card_id": str(rejected_card_id or ""),
                "confirmations": 1,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            })
        data["examples"] = examples[-300:]
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
        return len(data["examples"])


def learning_example_count(path: Path = DEFAULT_LEARNING_PATH) -> int:
    return len(load_learning_data(path)["examples"])
