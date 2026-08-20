"""手機相機卡匣辨識：OCR、星數與卡面影像特徵的本機混合比對。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from functools import lru_cache
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import cv2
import numpy as np
import requests

from recognition_learning import learning_adjustments


def decode_image(image_bytes: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("無法讀取相機圖片，請重新拍攝")
    return image


def normalize_text(value: Any) -> str:
    return re.sub(r"[^0-9A-Z\u4e00-\u9fff]", "", str(value).upper())


@lru_cache(maxsize=1)
def _ocr_engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def extract_ocr(image: np.ndarray) -> Tuple[List[str], float, Optional[str]]:
    """回傳 OCR 文字、平均信心與警告；OCR 故障時仍可繼續影像比對。"""
    try:
        result, _ = _ocr_engine()(image)
        if not result:
            return [], 0.0, None
        texts = [str(row[1]).strip() for row in result if len(row) >= 3 and str(row[1]).strip()]
        scores = [float(row[2]) for row in result if len(row) >= 3]
        return texts, (sum(scores) / len(scores) if scores else 0.0), None
    except Exception as exc:
        return [], 0.0, f"OCR 暫時無法使用：{exc}"


def _star_from_text(texts: Iterable[str]) -> Optional[int]:
    joined = " ".join(texts)
    explicit = re.search(r"([1-6])\s*(?:★|⭐|星)", joined)
    if explicit:
        return int(explicit.group(1))
    repeated = max((len(x) for x in re.findall(r"[★⭐]+", joined)), default=0)
    return repeated if 1 <= repeated <= 6 else None


def detect_star_count(image: np.ndarray, ocr_texts: Iterable[str] = ()) -> Tuple[Optional[int], float]:
    text_count = _star_from_text(ocr_texts)
    if text_count:
        return text_count, 0.95

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    yellow = cv2.inRange(hsv, np.array([14, 70, 110]), np.array([42, 255, 255]))
    kernel = np.ones((3, 3), np.uint8)
    yellow = cv2.morphologyEx(yellow, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(yellow, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area = image.shape[0] * image.shape[1]
    stars = []
    for contour in contours:
        contour_area = cv2.contourArea(contour)
        if not (area * 0.00008 <= contour_area <= area * 0.025):
            continue
        x, y, w, h = cv2.boundingRect(contour)
        ratio = w / max(h, 1)
        if 0.55 <= ratio <= 1.8 and cv2.arcLength(contour, True) > 0:
            stars.append((x, y, w, h))

    # 星星通常會排列在相近高度；取最大橫列，減少卡面黃色圖案誤判。
    best = 0
    for _, y, _, h in stars:
        row = sum(1 for _, other_y, _, other_h in stars if abs((y + h / 2) - (other_y + other_h / 2)) <= max(h, other_h) * 0.9)
        best = max(best, row)
    if 1 <= best <= 6:
        return best, min(0.82, 0.48 + best * 0.055)
    return None, 0.0


def _text_score(card: Dict[str, Any], texts: Iterable[str]) -> Tuple[float, str]:
    tokens = [normalize_text(t) for t in texts if normalize_text(t)]
    if not tokens:
        return 0.0, ""
    joined = normalize_text(" ".join(texts))
    fields = [normalize_text(card.get(key, "")) for key in ("id", "name", "name_en")]
    best, evidence = 0.0, ""
    for field in (x for x in fields if x):
        if field in joined:
            score = 1.0 if len(field) >= 4 else 0.9
        else:
            score = max(SequenceMatcher(None, field, token).ratio() for token in tokens)
        if score > best:
            best, evidence = score, field
    return best, evidence


def _orb_descriptor(image: np.ndarray):
    scale = min(1.0, 720.0 / max(image.shape[:2]))
    if scale < 1.0:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    orb = cv2.ORB_create(nfeatures=1100, scaleFactor=1.2, nlevels=8)
    keypoints, descriptors = orb.detectAndCompute(gray, None)
    return keypoints, descriptors


@lru_cache(maxsize=700)
def _reference_descriptor(url: str):
    if not url:
        return None
    response = requests.get(url, timeout=7, headers={"User-Agent": "PokemonMezastarScanner/2.3"})
    response.raise_for_status()
    reference = decode_image(response.content)
    _, descriptor = _orb_descriptor(reference)
    return descriptor


def _visual_score(query_descriptor, card: Dict[str, Any]) -> float:
    if query_descriptor is None:
        return 0.0
    try:
        reference_descriptor = _reference_descriptor(str(card.get("image", "")))
        if reference_descriptor is None or len(reference_descriptor) < 8:
            return 0.0
        matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(query_descriptor, reference_descriptor, k=2)
        good = []
        for pair in matches:
            if len(pair) == 2 and pair[0].distance < 0.76 * pair[1].distance:
                good.append(pair[0])
        denominator = max(18, min(len(query_descriptor), len(reference_descriptor)) * 0.16)
        return min(1.0, len(good) / denominator)
    except Exception:
        return 0.0


def recognize_card(image_bytes: bytes, cards: List[Dict[str, Any]], top_n: int = 3) -> Dict[str, Any]:
    image = decode_image(image_bytes)
    learned_adjustments = learning_adjustments(image_bytes)
    texts, ocr_confidence, warning = extract_ocr(image)
    star, star_confidence = detect_star_count(image, texts)
    _, query_descriptor = _orb_descriptor(image)

    text_ranked = []
    for card in cards:
        score, evidence = _text_score(card, texts)
        text_ranked.append((score, evidence, card))
    text_ranked.sort(key=lambda row: row[0], reverse=True)

    # OCR 有明顯線索時只比對最相關卡匣；否則用星數縮小影像搜尋範圍。
    best_text = text_ranked[0][0] if text_ranked else 0.0
    if best_text >= 0.60:
        visual_pool = [row[2] for row in text_ranked[:60]]
    else:
        # OCR 不清楚時完整搜尋圖鑑，避免錯誤星數造成真正卡匣被排除。
        visual_pool = list(cards)
    visual_ids = {str(card.get("id")) for card in visual_pool}

    visual_scores: Dict[str, float] = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        jobs = {executor.submit(_visual_score, query_descriptor, card): card for card in visual_pool}
        for future in as_completed(jobs):
            card = jobs[future]
            visual_scores[str(card.get("id"))] = future.result()

    ranked = []
    for text_score, evidence, card in text_ranked:
        card_id = str(card.get("id", ""))
        visual_score = visual_scores.get(card_id, 0.0)
        star_match = 1.0 if star and int(card.get("star", 0) or 0) == star else 0.0
        components = [(text_score, 0.58 if texts else 0.0), (visual_score, 0.34 if card_id in visual_ids else 0.0)]
        if star:
            components.append((star_match, 0.08 * max(0.5, star_confidence)))
        weight = sum(item[1] for item in components)
        score = sum(value * part_weight for value, part_weight in components) / weight if weight else 0.0
        learned_score = learned_adjustments.get(card_id, 0.0)
        if learned_score > 0.58:
            score = max(score, min(0.92, learned_score * 0.90))
        elif learned_score < 0.0:
            score *= max(0.55, 1.0 + learned_score * 0.70)
        ranked.append({
            "card": card,
            "score": round(score, 4),
            "text_score": round(text_score, 4),
            "visual_score": round(visual_score, 4),
            "star_match": bool(star_match),
            "learned_score": round(learned_score, 4),
            "evidence": evidence,
        })
    ranked.sort(key=lambda item: item["score"], reverse=True)

    best_score = ranked[0]["score"] if ranked else 0.0
    confidence = "高" if best_score >= 0.72 else "中" if best_score >= 0.48 else "低"
    return {
        "success": bool(ranked),
        "ocr_text": " / ".join(texts),
        "ocr_confidence": round(ocr_confidence, 3),
        "detected_star": star,
        "star_confidence": round(star_confidence, 3),
        "confidence": confidence,
        "candidates": ranked[:top_n],
        "warning": warning,
    }
