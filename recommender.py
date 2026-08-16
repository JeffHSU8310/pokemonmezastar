"""
Pokemon Mezastar Battle Lineup Optimizer & Recommender Engine
Calculates type advantages, damage formulas, special mechanic multipliers,
and generates optimal counter battle lineups.
"""

from typing import Dict, List, Any, Optional
from mezastar_data import (
    calculate_type_effectiveness,
    get_weaknesses,
    TYPES,
    TYPE_COLORS
)

SPECIAL_MULTIPLIERS = {
    "超極巨化": 1.40,
    "雙重衝刺": 1.40,
    "雙重攻擊": 1.40,
    "雙重招式": 1.40,
    "太晶化": 1.35,
    "極巨化": 1.35,
    "超級進化": 1.35,
    "Mega進化": 1.35,
    "Z招式": 1.35,
    "連擊": 1.30,
    "連擊卡匣": 1.30,
    "組合招式": 1.30,
    "組合卡匣": 1.30,
    "原始回歸": 1.35,
    "特別活動": 1.15,
    "無": 1.0
}

STAR_MULTIPLIERS = {
    6: 1.25,
    5: 1.10,
    4: 0.95,
    3: 0.85,
    2: 0.75,
    1: 0.65
}

def evaluate_card_performance(card: Dict[str, Any], boss_types: List[str], boss_move_type: Optional[str] = None) -> Dict[str, Any]:
    """
    評估單張卡匣面對特定 Boss 時的攻防綜合表現與傷害數值
    """
    move_type = card.get("move_type", "一般")
    move_power = card.get("move_power", 100)
    move_name = card.get("move_name", "攻擊")
    atk = card.get("atk", 100)
    sp_atk = card.get("sp_atk", 100)
    defense = card.get("def", 80)
    sp_def = card.get("sp_def", 80)
    hp = card.get("hp", 100)
    speed = card.get("spd", 100)
    energy = card.get("energy", 100)
    card_types = card.get("types", [])
    star = card.get("star", 5)
    special = card.get("special", "無")
    special_mechanics = card.get("special_mechanics", [])

    # 1. 檢查主要招式與第二招式之屬性倍率
    best_move_name = move_name
    best_move_type = move_type
    best_move_power = move_power
    best_type_mult = calculate_type_effectiveness(move_type, boss_types)

    sec_move = card.get("second_move", {})
    if sec_move and "type" in sec_move:
        sec_mult = calculate_type_effectiveness(sec_move["type"], boss_types)
        # 若第二招面對 Boss 剋制倍率更高，則切換計算
        if sec_mult > best_type_mult or (sec_mult == best_type_mult and sec_move.get("power", 0) > best_move_power):
            best_move_name = sec_move.get("name", move_name)
            best_move_type = sec_move.get("type", move_type)
            best_move_power = sec_move.get("power", move_power)
            best_type_mult = sec_mult

    # 2. 本系屬性一致加成 (STAB - Same-Type Attack Bonus)
    stab_mult = 1.25 if best_move_type in card_types else 1.0

    # 3. 特殊機制倍率
    spec_mult = 1.0
    for mech in special_mechanics + [special]:
        m_mult = SPECIAL_MULTIPLIERS.get(mech, 1.0)
        if m_mult > spec_mult:
            spec_mult = m_mult

    # 4. 星級與能量加權
    star_mult = STAR_MULTIPLIERS.get(star, 1.0)
    energy_bonus = 1.0 + (energy / 1000.0)  # 例如 210 能量 -> 1.21x

    # 5. 攻防數值加權 (取物攻/特攻較高者)
    best_atk_stat = max(atk, sp_atk)
    
    # 綜合傷害評分 (Damage Score)
    damage_score = (
        (best_move_power * (best_atk_stat / 100.0))
        * best_type_mult
        * stab_mult
        * spec_mult
        * star_mult
        * energy_bonus
    )

    # 6. 面對 Boss 攻擊時的防禦生存評估
    defensive_mult = 1.0
    if boss_move_type:
        defensive_mult = calculate_type_effectiveness(boss_move_type, card_types)
    else:
        if boss_types:
            mults = [calculate_type_effectiveness(bt, card_types) for bt in boss_types]
            defensive_mult = sum(mults) / len(mults)

    # 生存能力分 (以 HP + 防禦/特防評估)
    survival_score = (hp * 0.4 + max(defense, sp_def) * 0.6) / (defensive_mult if defensive_mult > 0 else 0.25)

    # 7. 作戰標籤
    tags = []
    if best_type_mult >= 4.0:
        tags.append("💥 4倍極限剋制")
    elif best_type_mult >= 2.0:
        tags.append("🎯 2倍弱點剋制")
    elif best_type_mult <= 0.5:
        tags.append("⚠️ 屬性被抗")

    for mech in special_mechanics:
        tags.append(f"✨ {mech}")

    if defensive_mult <= 0.5:
        tags.append("🛡️ 絕佳抗性防守")
    elif defensive_mult >= 2.0:
        tags.append("⚠️ 易被Boss反擊")

    return {
        "card": card,
        "best_move_name": best_move_name,
        "best_move_type": best_move_type,
        "best_move_power": best_move_power,
        "type_mult": best_type_mult,
        "stab_mult": stab_mult,
        "special_mult": spec_mult,
        "star_mult": star_mult,
        "damage_score": round(damage_score, 1),
        "defensive_mult": defensive_mult,
        "survival_score": round(survival_score, 1),
        "energy": energy,
        "speed": speed,
        "tags": list(dict.fromkeys(tags))
    }

def recommend_best_lineup(
    user_cards: Optional[List[Dict[str, Any]]] = None,
    boss_name: str = "未知目標",
    boss_types: Optional[List[str]] = None,
    boss_move_type: Optional[str] = None,
    team_size: int = 3,
    candidate_cards: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    依據 Boss 弱點與卡匣庫存，推薦最佳戰鬥出戰陣容 (Top 3)
    """
    cards_pool = user_cards if user_cards is not None else (candidate_cards or [])
    if boss_types is None:
        boss_types = ["一般"]

    if not cards_pool:
        return {
            "success": False,
            "boss_name": boss_name,
            "boss_types": boss_types,
            "recommended_team": [],
            "top_team": [],
            "recommendations": [],
            "strategy": "您目前尚未在「我的卡匣庫存」中標記擁有的卡匣，請先勾選擁有的卡匣！",
            "tactics": ["您目前尚未在「我的卡匣庫存」中標記擁有的卡匣，請先勾選擁有的卡匣！"],
            "message": "您目前尚未在「我的卡匣庫存」中標記擁有的卡匣，請先勾選擁有的卡匣！"
        }

    # 計算所有卡匣評分
    evaluated = []
    for c in cards_pool:
        res = evaluate_card_performance(c, boss_types, boss_move_type)
        evaluated.append(res)

    # 排序：優先考慮「傷害評分」(90%) + 「生存抗性」(10%)
    evaluated.sort(
        key=lambda x: (
            x["damage_score"] * 0.9 + x["survival_score"] * 0.1
        ),
        reverse=True
    )

    # 篩選前 N 名（避免完全重複的卡匣）
    selected = []
    seen_names = set()
    for item in evaluated:
        c_name = item["card"]["name"]
        if c_name not in seen_names:
            selected.append(item)
            seen_names.add(c_name)
        if len(selected) >= team_size:
            break

    # 若去重後不足 team_size，則取評分最高者補足
    if len(selected) < team_size:
        for item in evaluated:
            if item not in selected:
                selected.append(item)
            if len(selected) >= team_size:
                break

    # 出戰戰術指引建議
    tactics = []
    weaknesses = get_weaknesses(boss_types)
    weak_str = "、".join(weaknesses) if weaknesses else "無明顯弱點"
    tactics.append(f"🎯 **Boss 弱點屬性**：{weak_str}")

    if selected:
        best_attacker = selected[0]
        tactics.append(
            f"👑 **主攻手（第1棒）**：推薦派出 **{best_attacker['card']['name']}** "
            f"（{best_attacker['card']['series']} {best_attacker['card']['star']}⭐ 能量:{best_attacker['energy']}），"
            f"使用「{best_attacker['best_move_name']}」({best_attacker['best_move_type']}屬性) "
            f"可打出 **{best_attacker['type_mult']}x** 屬性剋制與預估 **{best_attacker['damage_score']}** 傷害評分！"
        )
        if len(selected) > 1:
            tactics.append(
                f"⚡ **副攻手（第2棒）**：推薦派出 **{selected[1]['card']['name']}** "
                f"（{selected[1]['card']['star']}⭐ 能量:{selected[1]['energy']}），戰術機制「{selected[1]['card'].get('special', '無')}」可進行爆發攻擊！"
            )
        if len(selected) > 2:
            tactics.append(
                f"🛡️ **收尾防守（第3棒）**：推薦派出 **{selected[2]['card']['name']}** "
                f"（{selected[2]['card']['star']}⭐），確保屬性抗性防禦與穩定輸出。"
            )

    strategy_str = "\n\n".join(tactics)

    return {
        "success": True,
        "boss_name": boss_name,
        "boss_types": boss_types,
        "boss_weaknesses": weaknesses,
        "recommended_team": selected,
        "top_team": selected,
        "recommendations": evaluated,
        "all_ranked": evaluated,
        "strategy": strategy_str,
        "tactics": tactics
    }

