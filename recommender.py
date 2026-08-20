"""Pokemon Mezastar battle lineup optimizer."""

from itertools import combinations, permutations
from math import ceil
from typing import Any, Dict, List, Optional

from mezastar_data import TYPES, calculate_type_effectiveness, get_weaknesses


SPECIAL_MULTIPLIERS = {
    "超極巨化": 1.15, "雙重衝刺": 1.15, "雙重攻擊": 1.15, "雙重招式": 1.15,
    "太晶化": 1.12, "極巨化": 1.12, "超級進化": 1.12, "Mega進化": 1.12,
    "Z招式": 1.12, "原始回歸": 1.12,
    "連擊": 1.08, "連擊卡匣": 1.08, "組合招式": 1.08, "組合卡匣": 1.08,
    "特別活動": 1.03, "無": 1.0,
}
ROLE_NAMES = ("主攻手（第1棒）", "爆發手（第2棒）", "收尾手（第3棒）")


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _accuracy(value: Any) -> float:
    if value in (None, "", "必中", "必定命中", "—", "-"):
        return 1.0
    parsed = _number(str(value).replace("%", ""), 100.0)
    if parsed > 1:
        parsed /= 100.0
    return min(1.0, max(0.0, parsed))


def _category(value: Any, card: Dict[str, Any]) -> str:
    text = str(value or "").strip()
    if "特殊" in text or text in {"特攻", "special", "Special"}:
        return "特殊"
    if "物理" in text or text in {"物攻", "physical", "Physical"}:
        return "物理"
    return "物理" if _number(card.get("atk"), 100) >= _number(card.get("sp_atk"), 100) else "特殊"


def _moves(card: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize moves from both legacy and extended card formats."""
    raw_moves: List[Dict[str, Any]] = []
    if isinstance(card.get("moves"), list):
        raw_moves.extend(move for move in card["moves"] if isinstance(move, dict))
    if card.get("move_name") or not raw_moves:
        raw_moves.append({
            "name": card.get("move_name", "攻擊"), "type": card.get("move_type", "一般"),
            "power": card.get("move_power", 100), "category": card.get("move_category"),
            "accuracy": card.get("move_accuracy", 100), "damage": card.get("move_damage"),
        })
    if isinstance(card.get("second_move"), dict):
        raw_moves.append(card["second_move"])

    normalized, seen = [], set()
    for move in raw_moves:
        name, move_type = str(move.get("name") or "攻擊"), str(move.get("type") or "一般")
        if (name, move_type) in seen:
            continue
        seen.add((name, move_type))
        normalized.append({
            "name": name, "type": move_type,
            "power": max(0.0, _number(move.get("power"), 100.0)),
            "category": _category(move.get("category"), card),
            "accuracy": _accuracy(move.get("accuracy")),
            "damage": max(0.0, _number(move.get("damage"), 0.0)),
        })
    return normalized


def _special_multiplier(card: Dict[str, Any]) -> float:
    mechanics = card.get("special_mechanics", [])
    if not isinstance(mechanics, list):
        mechanics = [mechanics]
    return max((SPECIAL_MULTIPLIERS.get(str(m), 1.0) for m in mechanics + [card.get("special", "無")]), default=1.0)


def _quality_multiplier(card: Dict[str, Any]) -> float:
    # Stats/damage already carry most of a card's strength; energy is only a tie-breaker.
    energy = _number(card.get("energy"), 120.0)
    return 1.0 + min(0.06, max(-0.04, (energy - 120.0) / 1500.0))


def _move_expected_damage(move, attacker, defender, defender_types):
    category = move["category"]
    attack_key = "atk" if category == "物理" else "sp_atk"
    defense_key = "def" if category == "物理" else "sp_def"
    attack_stat = max(1.0, _number(attacker.get(attack_key), 100.0))
    defense_stat = max(1.0, _number((defender or {}).get(defense_key), 100.0))
    raw_damage = move["damage"] or (move["power"] * attack_stat * 1.3)
    type_mult = calculate_type_effectiveness(move["type"], defender_types)
    stab_mult = 1.25 if move["type"] in attacker.get("types", []) else 1.0
    defense_factor = min(1.6, max(0.55, 100.0 / defense_stat))
    special_mult = _special_multiplier(attacker)
    expected = (raw_damage / 100.0 * move["accuracy"] * type_mult * stab_mult
                * defense_factor * special_mult * _quality_multiplier(attacker))
    return {**move, "attack_stat": attack_stat, "defense_stat": defense_stat,
            "type_mult": type_mult, "stab_mult": stab_mult, "special_mult": special_mult,
            "defense_factor": defense_factor, "expected_damage": expected}


def _boss_moves(boss_card, boss_types):
    if boss_card:
        found = _moves(boss_card)
        if found:
            return found
    return [{"name": f"{t}屬性攻擊", "type": t, "power": 100.0, "category": c,
             "accuracy": 1.0, "damage": 0.0}
            for t in (boss_types or ["一般"]) for c in ("物理", "特殊")]


def _incoming_damage(card, boss_card, boss_types):
    attacker = boss_card or {"atk": 120, "sp_atk": 120, "types": boss_types,
                             "energy": 120, "special": "無"}
    estimates = [_move_expected_damage(move, attacker, card, card.get("types", []) or ["一般"])
                 for move in _boss_moves(boss_card, boss_types)]
    return max(estimates, key=lambda item: item["expected_damage"])


def evaluate_card_performance(card, boss_types, boss_move_type=None, boss_card=None):
    """Evaluate one card with correct attack class, accuracy and Boss defenses."""
    boss_types = boss_types or ["一般"]
    effective_boss = dict(boss_card) if boss_card else None
    if effective_boss is not None:
        effective_boss["types"] = boss_types
    evaluated_moves = [_move_expected_damage(move, card, effective_boss, boss_types) for move in _moves(card)]
    best_move = max(evaluated_moves, key=lambda item: item["expected_damage"])
    incoming_types = [boss_move_type] if boss_move_type and not effective_boss else boss_types
    incoming = _incoming_damage(card, effective_boss, incoming_types)
    hp = max(1.0, _number(card.get("hp"), 100.0))
    survival_hits = hp / max(1.0, incoming["expected_damage"])
    survival_score = min(300.0, survival_hits * 100.0)
    boss_hp = max(1.0, _number((effective_boss or {}).get("hp"), 150.0))

    tags = []
    if best_move["type_mult"] >= 4:
        tags.append("💥 4倍極限剋制")
    elif best_move["type_mult"] >= 2:
        tags.append("🎯 2倍弱點剋制")
    elif best_move["type_mult"] <= 0.5:
        tags.append("⚠️ 屬性被抗")
    if best_move["accuracy"] < 0.85:
        tags.append("🎲 招式命中率偏低")
    mechanics = card.get("special_mechanics", [])
    if isinstance(mechanics, list):
        tags.extend(f"✨ {m}" for m in mechanics if m and m != "無")
    if incoming["type_mult"] <= 0.5:
        tags.append("🛡️ 絕佳抗性防守")
    elif incoming["type_mult"] >= 2:
        tags.append("⚠️ 易被Boss反擊")

    return {
        "card": card, "best_move_name": best_move["name"], "best_move_type": best_move["type"],
        "best_move_power": best_move["power"], "best_move_category": best_move["category"],
        "move_accuracy": round(best_move["accuracy"] * 100, 1), "attack_stat": best_move["attack_stat"],
        "boss_defense_stat": best_move["defense_stat"], "type_mult": best_move["type_mult"],
        "stab_mult": best_move["stab_mult"], "special_mult": best_move["special_mult"], "star_mult": 1.0,
        "expected_damage": round(best_move["expected_damage"], 1),
        "damage_score": round(best_move["expected_damage"], 1),
        "expected_ko_turns": ceil(boss_hp / max(1.0, best_move["expected_damage"])),
        "incoming_damage": round(incoming["expected_damage"], 1), "defensive_mult": incoming["type_mult"],
        "survival_hits": round(survival_hits, 2), "survival_score": round(survival_score, 1),
        "energy": _number(card.get("energy"), 100.0), "speed": _number(card.get("spd"), 100.0),
        "reliability_score": round(best_move["accuracy"] * 100, 1),
        "mechanic_score": round(min(100.0, (best_move["special_mult"] - 1.0) / 0.15 * 100.0), 1),
        "tags": list(dict.fromkeys(tags)),
    }


def _normalized(values):
    maximum = max(values, default=0.0)
    return [value / maximum * 100.0 for value in values] if maximum > 0 else [0.0 for _ in values]


def _weakness_set(card):
    card_types = card.get("types", []) or ["一般"]
    return {move_type for move_type in TYPES if calculate_type_effectiveness(move_type, card_types) > 1.0}


def _team_synergy(team):
    synergy = max(0, len({item["best_move_type"] for item in team}) - 1) * 1.5
    mechanics = {str(item["card"].get("special")) for item in team
                 if item["card"].get("special") not in (None, "", "無")}
    synergy += min(2.25, len(mechanics) * 0.75)
    weakness_sets = [_weakness_set(item["card"]) for item in team]
    if weakness_sets:
        synergy -= len(set.intersection(*weakness_sets)) * 4.0
    for left, right in combinations(weakness_sets, 2):
        synergy -= len(left & right) * 0.35
    return synergy


def _assign_scores(evaluated, boss_card):
    offense = _normalized([item["expected_damage"] for item in evaluated])
    survival = _normalized([item["survival_score"] for item in evaluated])
    speeds = _normalized([item["speed"] for item in evaluated])
    boss_speed = _number((boss_card or {}).get("spd"), 120.0)
    for index, item in enumerate(evaluated):
        speed_probability = item["speed"] / max(1.0, item["speed"] + boss_speed) * 100.0
        speed_score = (speeds[index] + speed_probability) / 2.0
        reliability, mechanic = item["reliability_score"], item["mechanic_score"]
        type_score = min(100.0, item["type_mult"] / 4.0 * 100.0)
        role_scores = {
            ROLE_NAMES[0]: .60 * offense[index] + .18 * speed_score + .12 * reliability + .10 * survival[index],
            ROLE_NAMES[1]: .58 * offense[index] + .17 * mechanic + .13 * type_score + .12 * survival[index],
            ROLE_NAMES[2]: .35 * offense[index] + .40 * survival[index] + .15 * reliability + .10 * speed_score,
        }
        item["offense_score"], item["speed_score"] = round(offense[index], 1), round(speed_score, 1)
        item["role_scores"] = {key: round(value, 1) for key, value in role_scores.items()}
        item["overall_score"] = round(.55 * offense[index] + .20 * survival[index] + .10 * speed_score
                                      + .10 * reliability + .05 * mechanic, 1)


def _optimize_three_card_team(evaluated):
    shortlist = sorted(evaluated, key=lambda item: max(item["overall_score"], *item["role_scores"].values()),
                       reverse=True)[:24]
    best_team, best_score, best_synergy = None, float("-inf"), 0.0
    for group in combinations(shortlist, 3):
        if len({item["card"].get("name") for item in group}) < 3:
            continue
        synergy = _team_synergy(list(group))
        for ordered in permutations(group):
            role_total = sum(ordered[i]["role_scores"][ROLE_NAMES[i]] for i in range(3)) / 3.0
            if role_total + synergy > best_score:
                best_team, best_score, best_synergy = ordered, role_total + synergy, synergy
    if best_team is None:
        best_team = tuple(sorted(evaluated, key=lambda item: item["overall_score"], reverse=True)[:3])
        best_score = sum(item["overall_score"] for item in best_team) / max(1, len(best_team))
    selected = []
    for index, item in enumerate(best_team):
        result, role = dict(item), ROLE_NAMES[index]
        result["assigned_role"], result["role_score"] = role, item["role_scores"].get(role, item["overall_score"])
        selected.append(result)
    return selected, round(best_score, 1), round(best_synergy, 1)


def recommend_best_lineup(user_cards=None, boss_name="未知目標", boss_types=None, boss_move_type=None,
                          team_size=3, candidate_cards=None, boss_card=None):
    """Recommend a role-aware team against the selected Boss."""
    cards_pool = user_cards if user_cards is not None else (candidate_cards or [])
    boss_types = boss_types or ["一般"]
    if not cards_pool:
        message = "您目前尚未在「我的卡匣庫存」中標記擁有的卡匣，請先勾選擁有的卡匣！"
        return {"success": False, "boss_name": boss_name, "boss_types": boss_types,
                "recommended_team": [], "top_team": [], "recommendations": [],
                "strategy": message, "tactics": [message], "message": message}

    evaluated = [evaluate_card_performance(card, boss_types, boss_move_type, boss_card) for card in cards_pool]
    _assign_scores(evaluated, boss_card)
    evaluated.sort(key=lambda item: item["overall_score"], reverse=True)
    if team_size == 3 and len(evaluated) >= 3:
        selected, team_score, team_synergy = _optimize_three_card_team(evaluated)
    else:
        selected = [dict(item) for item in evaluated[:team_size]]
        for index, item in enumerate(selected):
            role = ROLE_NAMES[min(index, 2)]
            item["assigned_role"], item["role_score"] = role, item["role_scores"].get(role, item["overall_score"])
        team_score = round(sum(item["overall_score"] for item in selected) / max(1, len(selected)), 1)
        team_synergy = 0.0

    weaknesses = get_weaknesses(boss_types)
    tactics = [f"🎯 **Boss 弱點屬性**：{'、'.join(weaknesses) if weaknesses else '無明顯弱點'}"]
    for item in selected:
        tactics.append(f"**{item['assigned_role']}**：**{item['card'].get('name', '未知')}** 使用「{item['best_move_name']}」"
                       f"（{item['best_move_type']}／{item['best_move_category']}，命中 {item['move_accuracy']:g}%），"
                       f"期望傷害 {item['expected_damage']:g}、預估 {item['expected_ko_turns']} 回合擊倒。")
    tactics.append(f"🧩 **陣容總評**：{team_score:g} 分（組合加成 {team_synergy:+g}）")
    return {"success": True, "boss_name": boss_name, "boss_types": boss_types,
            "boss_weaknesses": weaknesses, "boss_card": boss_card,
            "recommended_team": selected, "top_team": selected, "recommendations": evaluated,
            "all_ranked": evaluated, "team_score": team_score, "team_synergy": team_synergy,
            "strategy": "\n\n".join(tactics), "tactics": tactics}
