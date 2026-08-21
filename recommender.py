"""Pokemon Mezastar battle lineup optimizer."""

from itertools import combinations, permutations
from math import ceil, log2
from typing import Any, Dict, List, Optional

from mezastar_data import TYPES, calculate_type_effectiveness, get_weaknesses
from recommendation_learning import learned_pair_adjustment, recommendation_learning_adjustments


MEZASTAR_EFFECTIVENESS_STEP = 1.6
DEFENSE_OVERRIDE_MOVES = {"精神擊破", "精神衝擊", "神秘之劍"}
COMBINED_MECHANICS = {"雙重招式", "雙重攻擊", "雙重衝刺", "組合招式", "組合卡匣"}
ROLE_NAMES = ("主攻手（第1棒）", "爆發手（第2棒）", "收尾手（第3棒）")
# Removing unsupported STAB/star/mechanic re-multiplication changes the score scale.
# Keep the existing 2-3 rotation Boss expectation calibrated to the new reference formula.
BOSS_HP_MULTIPLIER = 4.0
BOSS_ENERGY_MULTIPLIER = 2.0
MIN_BOSS_KO_TURNS = 2


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def filter_candidate_cards_by_stars(cards: List[Dict[str, Any]], selected_stars) -> List[Dict[str, Any]]:
    """Filter either collection or catalog candidates while preserving source order."""
    allowed_stars = {
        int(_number(value, -1)) for value in (selected_stars or [])
        if int(_number(value, -1)) > 0
    }
    if not allowed_stars:
        return []
    return [
        card for card in cards
        if int(_number(card.get("star"), -1)) in allowed_stars
    ]


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


def _mechanics(card: Dict[str, Any]) -> List[str]:
    mechanics = card.get("special_mechanics", [])
    if not isinstance(mechanics, list):
        mechanics = [mechanics]
    return [str(value) for value in mechanics + [card.get("special", "無")] if value]


def _mezastar_type_multiplier(move_type: str, defender_types: List[str]) -> float:
    """Convert the main-series 2x step into Mezastar's 1.6x damage step."""
    canonical = calculate_type_effectiveness(move_type, defender_types)
    if canonical <= 0:
        return 0.0
    return round(MEZASTAR_EFFECTIVENESS_STEP ** log2(canonical), 4)


def _fallback_mechanic_multiplier(card: Dict[str, Any], move: Dict[str, Any]) -> float:
    """Use documented wheel bonuses only when card-face damage is unavailable."""
    mechanics = set(_mechanics(card))
    move_name = str(move.get("name", ""))
    if card.get("has_z_move") or "Z招式" in mechanics:
        return 1.4
    if "極巨" in move_name or (
        len(_moves(card)) == 1
        and (card.get("has_dynamax") or card.get("has_gigantamax")
             or mechanics.intersection({"極巨化", "超極巨化"}))
    ):
        return 1.2
    return 1.0


def _uses_combined_moves(card: Dict[str, Any]) -> bool:
    return bool(
        card.get("has_double_attack")
        or card.get("has_combo_tag")
        or set(_mechanics(card)).intersection(COMBINED_MECHANICS)
    )


def _mechanic_score(card: Dict[str, Any]) -> float:
    mechanics = set(_mechanics(card))
    if _uses_combined_moves(card):
        return 100.0
    if card.get("has_z_move") or "Z招式" in mechanics:
        return 90.0
    if card.get("has_dynamax") or card.get("has_gigantamax") or mechanics.intersection({"極巨化", "超極巨化"}):
        return 85.0
    if card.get("has_mega") or mechanics.intersection({"超級進化", "Mega進化", "原始回歸"}):
        return 80.0
    if any(value not in {"", "無", "常規卡匣"} for value in mechanics):
        return 55.0
    return 0.0


def _move_expected_damage(move, attacker, defender, defender_types):
    category = move["category"]
    attack_key = "atk" if category == "物理" else "sp_atk"
    defense_key = "def" if category == "物理" or move["name"] in DEFENSE_OVERRIDE_MOVES else "sp_def"
    attack_stat = max(1.0, _number(attacker.get(attack_key), 100.0))
    defense_stat = max(1.0, _number((defender or {}).get(defense_key), 100.0))
    has_card_face_damage = move["damage"] > 0
    mechanic_mult = 1.0 if has_card_face_damage else _fallback_mechanic_multiplier(attacker, move)
    raw_damage = move["damage"] if has_card_face_damage else move["power"] * attack_stat * mechanic_mult
    canonical_type_mult = calculate_type_effectiveness(move["type"], defender_types)
    type_mult = _mezastar_type_multiplier(move["type"], defender_types)
    defense_factor = 100.0 / defense_stat
    damage_before_accuracy = raw_damage * type_mult / defense_stat
    expected = damage_before_accuracy * move["accuracy"]
    return {**move, "attack_stat": attack_stat, "defense_stat": defense_stat,
            "defense_key": defense_key, "canonical_type_mult": canonical_type_mult,
            "type_mult": type_mult, "stab_mult": 1.0, "special_mult": mechanic_mult,
            "star_mult": 1.0, "defense_factor": defense_factor, "base_damage": raw_damage,
            "damage_source": "card_face" if has_card_face_damage else "estimated",
            "damage_before_accuracy": damage_before_accuracy, "expected_damage": expected}


def _best_attack_result(card, evaluated_moves):
    """Sum separately-evaluated attacks only for double/combo cards."""
    primary = max(evaluated_moves, key=lambda item: item["expected_damage"])
    if not _uses_combined_moves(card) or len(evaluated_moves) < 2:
        return {**primary, "is_combined_move": False, "move_components": [primary]}

    combined = dict(primary)
    combined["name"] = "＋".join(move["name"] for move in evaluated_moves)
    combined["type"] = "＋".join(dict.fromkeys(move["type"] for move in evaluated_moves))
    categories = list(dict.fromkeys(move["category"] for move in evaluated_moves))
    combined["category"] = categories[0] if len(categories) == 1 else "複合"
    combined["power"] = sum(move["power"] for move in evaluated_moves)
    combined["base_damage"] = sum(move["base_damage"] for move in evaluated_moves)
    combined["expected_damage"] = sum(move["expected_damage"] for move in evaluated_moves)
    combined["damage_before_accuracy"] = sum(move["damage_before_accuracy"] for move in evaluated_moves)
    if combined["damage_before_accuracy"] > 0:
        combined["accuracy"] = combined["expected_damage"] / combined["damage_before_accuracy"]
    combined["type_mult"] = max(move["type_mult"] for move in evaluated_moves)
    combined["canonical_type_mult"] = max(move["canonical_type_mult"] for move in evaluated_moves)
    combined["is_combined_move"] = True
    combined["move_components"] = evaluated_moves
    return combined


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
    return _best_attack_result(attacker, estimates)


def _estimated_boss_durability(boss_card: Optional[Dict[str, Any]]) -> float:
    """Convert card HP/energy to a battle-scale Boss durability estimate.

    Card HP and the recommender's expected-damage score use different scales.
    Comparing them directly made nearly every attacker look like a one-turn KO.
    """
    boss = boss_card or {}
    hp = max(1.0, _number(boss.get("hp"), 150.0))
    energy = max(1.0, _number(boss.get("energy"), 120.0))
    star = max(1.0, _number(boss.get("star"), 5.0))
    rarity_multiplier = 1.0 + max(0.0, star - 4.0) * 0.15
    return (hp * BOSS_HP_MULTIPLIER + energy * BOSS_ENERGY_MULTIPLIER) * rarity_multiplier


def evaluate_card_performance(card, boss_types, boss_move_type=None, boss_card=None):
    """Evaluate one card with correct attack class, accuracy and Boss defenses."""
    boss_types = boss_types or ["一般"]
    effective_boss = dict(boss_card) if boss_card else None
    if effective_boss is not None:
        effective_boss["types"] = boss_types
    evaluated_moves = [_move_expected_damage(move, card, effective_boss, boss_types) for move in _moves(card)]
    best_move = _best_attack_result(card, evaluated_moves)
    incoming_types = [boss_move_type] if boss_move_type and not effective_boss else boss_types
    incoming = _incoming_damage(card, effective_boss, incoming_types)
    hp = max(1.0, _number(card.get("hp"), 100.0))
    survival_hits = hp / max(1.0, incoming["expected_damage"])
    survival_score = min(300.0, survival_hits * 100.0)
    boss_durability = _estimated_boss_durability(effective_boss)

    tags = []
    if best_move["type_mult"] >= 2.56:
        tags.append("💥 4倍極限剋制")
    elif best_move["type_mult"] >= 1.6:
        tags.append("🎯 2倍弱點剋制")
    elif best_move["type_mult"] <= 0.625:
        tags.append("⚠️ 屬性被抗")
    if best_move["is_combined_move"]:
        tags.append("💫 雙招分算後相加")
    if best_move["accuracy"] < 0.85:
        tags.append("🎲 招式命中率偏低")
    mechanics = card.get("special_mechanics", [])
    if isinstance(mechanics, list):
        tags.extend(f"✨ {m}" for m in mechanics if m and m != "無")
    if incoming["type_mult"] <= 0.625:
        tags.append("🛡️ 絕佳抗性防守")
    elif incoming["type_mult"] >= 1.6:
        tags.append("⚠️ 易被Boss反擊")

    move_components = [
        {
            "name": move["name"], "type": move["type"], "category": move["category"],
            "power": move["power"], "accuracy": round(move["accuracy"] * 100, 1),
            "attack_stat": move["attack_stat"], "defense_stat": move["defense_stat"],
            "defense_key": move["defense_key"], "base_damage": round(move["base_damage"], 1),
            "type_mult": move["type_mult"], "expected_damage": round(move["expected_damage"], 1),
            "damage_source": move["damage_source"],
        }
        for move in best_move["move_components"]
    ]

    return {
        "card": card, "best_move_name": best_move["name"], "best_move_type": best_move["type"],
        "best_move_power": best_move["power"], "best_move_category": best_move["category"],
        "move_accuracy": round(best_move["accuracy"] * 100, 1), "attack_stat": best_move["attack_stat"],
        "boss_defense_stat": best_move["defense_stat"], "type_mult": best_move["type_mult"],
        "stab_mult": best_move["stab_mult"], "special_mult": best_move["special_mult"],
        "star_mult": round(best_move["star_mult"], 2), "base_damage": round(best_move["base_damage"], 1),
        "defense_key": best_move["defense_key"], "damage_source": best_move["damage_source"],
        "is_combined_move": best_move["is_combined_move"], "move_components": move_components,
        "expected_damage": round(best_move["expected_damage"], 1),
        "damage_score": round(best_move["expected_damage"], 1),
        # 單張卡匣不顯示一回合擊退 Boss；Boss 耐久已換算到與傷害評分相近的尺度。
        "boss_durability": round(boss_durability, 1),
        "expected_ko_turns": max(
            MIN_BOSS_KO_TURNS,
            ceil(boss_durability / max(1.0, best_move["expected_damage"])),
        ),
        "incoming_damage": round(incoming["expected_damage"], 1), "defensive_mult": incoming["type_mult"],
        "survival_hits": round(survival_hits, 2), "survival_score": round(survival_score, 1),
        "energy": _number(card.get("energy"), 100.0), "speed": _number(card.get("spd"), 100.0),
        "reliability_score": round(best_move["accuracy"] * 100, 1),
        "mechanic_score": _mechanic_score(card),
        "tags": list(dict.fromkeys(tags)),
    }


def _normalized(values):
    maximum = max(values, default=0.0)
    return [value / maximum * 100.0 for value in values] if maximum > 0 else [0.0 for _ in values]


def _weakness_set(card):
    card_types = card.get("types", []) or ["一般"]
    return {move_type for move_type in TYPES if calculate_type_effectiveness(move_type, card_types) > 1.0}


def _team_synergy(team, pair_adjustments=None):
    synergy = max(0, len({item["best_move_type"] for item in team}) - 1) * 1.5
    mechanics = {str(item["card"].get("special")) for item in team
                 if item["card"].get("special") not in (None, "", "無")}
    synergy += min(2.25, len(mechanics) * 0.75)
    weakness_sets = [_weakness_set(item["card"]) for item in team]
    if weakness_sets:
        synergy -= len(set.intersection(*weakness_sets)) * 4.0
    for left, right in combinations(weakness_sets, 2):
        synergy -= len(left & right) * 0.35
    if pair_adjustments:
        synergy += learned_pair_adjustment(
            [item["card"].get("id") for item in team], pair_adjustments
        )
    return synergy


def _assign_scores(evaluated, boss_card):
    offense = _normalized([item["expected_damage"] for item in evaluated])
    survival = _normalized([item["survival_score"] for item in evaluated])
    speeds = _normalized([item["speed"] for item in evaluated])
    energies = _normalized([item["energy"] for item in evaluated])
    boss_speed = _number((boss_card or {}).get("spd"), 120.0)
    for index, item in enumerate(evaluated):
        speed_probability = item["speed"] / max(1.0, item["speed"] + boss_speed) * 100.0
        speed_score = (speeds[index] + speed_probability) / 2.0
        reliability, mechanic = item["reliability_score"], item["mechanic_score"]
        rarity_score = min(100.0, max(0.0, _number(item["card"].get("star"), 1.0) / 6.0 * 100.0))
        type_score = min(100.0, item["type_mult"] / 2.56 * 100.0)
        role_scores = {
            ROLE_NAMES[0]: .72 * offense[index] + .10 * speed_score + .10 * reliability + .08 * survival[index],
            ROLE_NAMES[1]: .70 * offense[index] + .12 * mechanic + .10 * type_score + .08 * survival[index],
            ROLE_NAMES[2]: .55 * offense[index] + .25 * survival[index] + .12 * reliability + .08 * speed_score,
        }
        item["offense_score"], item["speed_score"] = round(offense[index], 1), round(speed_score, 1)
        item["rarity_score"], item["energy_score"] = round(rarity_score, 1), round(energies[index], 1)
        item["role_scores"] = {key: round(value, 1) for key, value in role_scores.items()}
        item["overall_score"] = round(.66 * offense[index] + .12 * survival[index] + .05 * speed_score
                                      + .07 * reliability + .04 * mechanic + .04 * rarity_score
                                      + .02 * energies[index], 1)


def _weakness_score(item):
    """Reward counters without letting a very weak counter win automatically."""
    multiplier = float(item.get("type_mult", 1.0))
    if multiplier >= 2.56:
        return 100.0
    if multiplier >= 1.6:
        return 75.0
    if multiplier > 1.0:
        return 60.0
    return 0.0


def _team_output_estimate(selected):
    """Estimate complete-team rotations and individual attacks to defeat the Boss."""
    team_damage = round(sum(item["expected_damage"] for item in selected), 1)
    boss_durability = round(max((item["boss_durability"] for item in selected), default=0.0), 1)
    if not selected:
        return team_damage, boss_durability, 0, 0

    complete_rotations = int(boss_durability // max(1.0, team_damage))
    accumulated = complete_rotations * team_damage
    attack_count = complete_rotations * len(selected)
    if accumulated < boss_durability:
        for item in selected:
            accumulated += item["expected_damage"]
            attack_count += 1
            if accumulated >= boss_durability:
                break
    rotation_count = max(1, ceil(attack_count / len(selected)))
    return team_damage, boss_durability, rotation_count, attack_count


def _optimize_three_card_team(evaluated, pair_adjustments=None):
    # 黃金陣容優先保留兩張不同寶可夢的有效弱點打手，再直接最大化
    # 三張卡的實際合計期望傷害；若收藏只有一隻有效剋制者則退回一張。
    # 角色分工、額外弱點覆蓋與相性只用於總傷害相同時排序。
    output_pool = sorted(evaluated, key=lambda item: item["expected_damage"], reverse=True)[:24]
    counter_pool = sorted(
        (item for item in evaluated if item["type_mult"] > 1.0),
        key=lambda item: item["expected_damage"],
        reverse=True,
    )[:12]
    shortlist, seen = [], set()
    for item in output_pool + counter_pool:
        identity = str(item["card"].get("id") or id(item))
        if identity not in seen:
            seen.add(identity)
            shortlist.append(item)
    shortlist = shortlist[:30]
    distinct_counter_names = {
        str(item["card"].get("name") or item["card"].get("id"))
        for item in shortlist if item["type_mult"] > 1.0
    }
    required_counter_count = min(2, len(distinct_counter_names))
    best_team, best_priority, best_score, best_synergy = None, None, float("-inf"), 0.0
    for group in combinations(shortlist, 3):
        if len({item["card"].get("name") for item in group}) < 3:
            continue
        if sum(item["type_mult"] > 1.0 for item in group) < required_counter_count:
            continue
        synergy = _team_synergy(list(group), pair_adjustments)
        team_damage = round(sum(item["expected_damage"] for item in group), 1)
        for ordered in permutations(group):
            role_total = sum(ordered[i]["role_scores"][ROLE_NAMES[i]] for i in range(3)) / 3.0
            offense_total = sum(item["offense_score"] for item in ordered) / 3.0
            weakness_total = sum(item["weakness_score"] for item in ordered) / 3.0
            quality_total = sum(
                item["rarity_score"] * 0.67 + item["energy_score"] * 0.33 for item in ordered
            ) / 3.0
            applied_synergy = synergy * 0.20
            candidate_score = (offense_total * 0.76 + weakness_total * 0.14
                               + role_total * 0.08 + quality_total * 0.02 + applied_synergy)
            candidate_priority = (team_damage, candidate_score)
            if best_priority is None or candidate_priority > best_priority:
                best_team, best_priority = ordered, candidate_priority
                best_score, best_synergy = candidate_score, applied_synergy
    if best_team is None:
        best_team = tuple(sorted(evaluated, key=lambda item: item["lineup_score"], reverse=True)[:3])
        best_score = sum(item["overall_score"] for item in best_team) / max(1, len(best_team))
    # 黃金陣容的棒次以實際期望傷害排序，確保最高輸出者顯示為第一棒。
    best_team = tuple(sorted(best_team, key=lambda item: item["expected_damage"], reverse=True))
    selected = []
    for index, item in enumerate(best_team):
        result, role = dict(item), ROLE_NAMES[index]
        result["assigned_role"], result["role_score"] = role, item["role_scores"].get(role, item["overall_score"])
        selected.append(result)
    return selected, round(best_score, 1), round(best_synergy, 1)


def recommend_best_lineup(user_cards=None, boss_name="未知目標", boss_types=None, boss_move_type=None,
                          team_size=3, candidate_cards=None, boss_card=None, learning_path=None):
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
    learning = recommendation_learning_adjustments(
        boss_types, **({"path": learning_path} if learning_path is not None else {})
    )
    for item in evaluated:
        adjustment = float(learning["card_adjustments"].get(str(item["card"].get("id")), 0.0))
        item["learning_adjustment"] = round(adjustment, 2)
        item["overall_score"] = round(item["overall_score"] + adjustment, 1)
        item["role_scores"] = {
            role: round(score + adjustment, 1) for role, score in item["role_scores"].items()
        }
        if adjustment >= 0.5:
            item["tags"].append("🧠 實戰勝率加權")
        elif adjustment <= -0.5:
            item["tags"].append("🧠 實戰回饋降權")
        item["weakness_score"] = _weakness_score(item)
        item["lineup_score"] = round(
            item["offense_score"] * 0.80
            + item["weakness_score"] * 0.12
            + item["overall_score"] * 0.08,
            1,
        )
    evaluated.sort(key=lambda item: item["lineup_score"], reverse=True)
    if team_size == 3 and len(evaluated) >= 3:
        selected, team_score, team_synergy = _optimize_three_card_team(
            evaluated, learning["pair_adjustments"]
        )
    else:
        selected = [dict(item) for item in evaluated[:team_size]]
        for index, item in enumerate(selected):
            role = ROLE_NAMES[min(index, 2)]
            item["assigned_role"], item["role_score"] = role, item["role_scores"].get(role, item["overall_score"])
        team_score = round(sum(item["overall_score"] for item in selected) / max(1, len(selected)), 1)
        team_synergy = 0.0
    team_learning_adjustment = learned_pair_adjustment(
        [item["card"].get("id") for item in selected], learning["pair_adjustments"]
    )
    team_expected_damage, boss_durability, team_expected_ko_turns, team_expected_ko_attacks = (
        _team_output_estimate(selected)
    )

    weaknesses = get_weaknesses(boss_types)
    tactics = [f"🎯 **Boss 弱點屬性**：{'、'.join(weaknesses) if weaknesses else '無明顯弱點'}"]
    for item in selected:
        tactics.append(f"**{item['assigned_role']}**：**{item['card'].get('name', '未知')}** 使用「{item['best_move_name']}」"
                       f"（{item['best_move_type']}／{item['best_move_category']}，命中 {item['move_accuracy']:g}%），"
                       f"本輪期望傷害貢獻 {item['expected_damage']:g}。")
    tactics.append(
        f"⚔️ **整隊擊退估算**：三張卡每輪各攻擊一次，合計期望傷害 {team_expected_damage:g}，"
        f"預估 {team_expected_ko_turns} 輪、約 {team_expected_ko_attacks} 次出招擊倒 Boss。"
    )
    tactics.append(
        f"🧩 **陣容總評**：{team_score:g} 分（組合加成 {team_synergy:+g}，"
        f"實戰學習 {team_learning_adjustment:+g}）"
    )
    return {"success": True, "boss_name": boss_name, "boss_types": boss_types,
            "boss_weaknesses": weaknesses, "boss_card": boss_card,
            "recommended_team": selected, "top_team": selected, "recommendations": evaluated,
            "all_ranked": evaluated, "team_score": team_score, "team_synergy": team_synergy,
            "team_expected_damage": team_expected_damage,
            "team_expected_ko_turns": team_expected_ko_turns,
            "team_expected_ko_attacks": team_expected_ko_attacks,
            "boss_durability": boss_durability,
            "team_learning_adjustment": round(team_learning_adjustment, 1),
            "matching_feedback_count": learning["matching_feedback_count"],
            "strategy": "\n\n".join(tactics), "tactics": tactics}
