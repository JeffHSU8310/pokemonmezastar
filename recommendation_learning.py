"""對戰推薦回饋學習；只保存對戰結果與卡匣編號。"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import threading
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_LEARNING_PATH = Path(__file__).resolve().parent / "data" / "recommendation_learning.json"
_FILE_LOCK = threading.Lock()


def _empty_data() -> Dict[str, Any]:
    return {"version": 1, "feedback": []}


def _context_key(boss_types: Iterable[str]) -> str:
    return "|".join(sorted({str(value).strip() for value in boss_types if str(value).strip()}))


def load_recommendation_learning(path: Path = DEFAULT_LEARNING_PATH) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("feedback"), list):
            return data
    except (OSError, ValueError, TypeError):
        pass
    return _empty_data()


def record_recommendation_feedback(
    boss_name: str,
    boss_types: Iterable[str],
    team_card_ids: Iterable[str],
    won: bool,
    best_card_id: Optional[str] = None,
    path: Path = DEFAULT_LEARNING_PATH,
) -> int:
    team_ids = list(dict.fromkeys(str(card_id).strip() for card_id in team_card_ids if str(card_id).strip()))
    if not team_ids:
        raise ValueError("推薦陣容不得為空")
    context = _context_key(boss_types)
    if not context:
        raise ValueError("Boss 屬性不得為空")
    best_id = str(best_card_id or "").strip()
    if best_id and best_id not in team_ids:
        raise ValueError("最佳表現卡匣必須在本次陣容中")

    with _FILE_LOCK:
        data = load_recommendation_learning(path)
        data["feedback"].append({
            "boss_name": str(boss_name or "未知目標"),
            "boss_context": context,
            "team_card_ids": team_ids,
            "won": bool(won),
            "best_card_id": best_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        })
        data["feedback"] = data["feedback"][-500:]
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
        return len(data["feedback"])


def recommendation_learning_adjustments(
    boss_types: Iterable[str],
    path: Path = DEFAULT_LEARNING_PATH,
) -> Dict[str, Any]:
    """Return conservative card and pair adjustments for the same Boss types."""
    context = _context_key(boss_types)
    relevant = [
        item for item in load_recommendation_learning(path)["feedback"]
        if item.get("boss_context") == context
    ]
    card_stats: Dict[str, List[float]] = {}
    pair_stats: Dict[str, List[float]] = {}
    for item in relevant:
        outcome = 1.0 if item.get("won") else -1.0
        team_ids = list(dict.fromkeys(str(value) for value in item.get("team_card_ids", []) if value))
        for card_id in team_ids:
            signed, count, best = card_stats.get(card_id, [0.0, 0.0, 0.0])
            card_stats[card_id] = [signed + outcome, count + 1.0,
                                   best + (1.0 if item.get("best_card_id") == card_id and outcome > 0 else 0.0)]
        for left_index, left in enumerate(team_ids):
            for right in team_ids[left_index + 1:]:
                key = "|".join(sorted((left, right)))
                signed, count = pair_stats.get(key, [0.0, 0.0])
                pair_stats[key] = [signed + outcome, count + 1.0]

    card_adjustments = {
        card_id: round(max(-6.0, min(8.0, 6.0 * signed / (count + 3.0) + 2.0 * best / (count + 3.0))), 2)
        for card_id, (signed, count, best) in card_stats.items()
    }
    pair_adjustments = {
        key: round(max(-4.0, min(4.0, 4.0 * signed / (count + 4.0))), 2)
        for key, (signed, count) in pair_stats.items()
    }
    return {
        "card_adjustments": card_adjustments,
        "pair_adjustments": pair_adjustments,
        "matching_feedback_count": len(relevant),
    }


def learned_pair_adjustment(team_card_ids: Iterable[str], pair_adjustments: Dict[str, float]) -> float:
    ids = list(dict.fromkeys(str(value) for value in team_card_ids if value))
    total = 0.0
    for left_index, left in enumerate(ids):
        for right in ids[left_index + 1:]:
            total += float(pair_adjustments.get("|".join(sorted((left, right))), 0.0))
    return max(-6.0, min(6.0, total))


def recommendation_feedback_count(path: Path = DEFAULT_LEARNING_PATH) -> int:
    return len(load_recommendation_learning(path)["feedback"])
