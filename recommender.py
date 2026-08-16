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
    "雙重衝刺": 1.40,
    "太晶化": 1.35,
    "極巨化": 1.35,
    "超級進化": 1.30,
    "Z招式": 1.30,
    "雙重招式": 1.35,
    "原始回歸": 1.35,
    "無": 1.0
}

STAR_MULTIPLIERS = {
    6: 1.20,
    5: 1.05,
    4: 0.95,
    3: 0.85,
    2: 0.75
}

def evaluate_card_performance(card: Dict[str, Any], boss_types: List[str], boss_move_type: Optional[str] = None) -> Dict[str, Any]:
    """
    評估單張卡匣面對特定 Boss 時的攻防綜合表現與傷害數值
    """
    move_type = card.get("move_type", "一般")
    move_power = card.get("move_power", 100)
    atk = card.get("atk", 100)
    sp_atk = card.get("sp_atk", 100)
    card_types = card.get("types", [])
    star = card.get("star", 5)
    special = card.get("special", "無")

    # 1. 攻擊屬性相剋倍率 (2.0, 4.0, 1.0, 0.5, 0.25, 0.0)
    type_mult = calculate_type_effectiveness(move_type, boss_types)

    # 2. 本系屬性一致加成 (STAB - Same-Type Attack Bonus)
    stab_mult = 1.25 if move_type in card_types else 1.0

    # 3. 特殊機制倍率 (極巨化/Mega/Z招/太晶/雙重衝刺)
    special_mult = SPECIAL_MULTIPLIERS.get(special, 1.0)

    # 4. 星級基礎係數
    star_mult = STAR_MULTIPLIERS.get(star, 1.0)

    # 5. 攻防數值加權 (取物攻/特攻較高者)
    best_atk_stat = max(atk, sp_atk)
    
    # 綜合傷害評分 (Damage Score)
    damage_score = (
        (move_power * (best_atk_stat / 100.0))
        * type_mult
        * stab_mult
        * special_mult
        * star_mult
    )

    # 6. 面對 Boss 攻擊時的防禦生存評估
    defensive_mult = 1.0
    if boss_move_type:
        defensive_mult = calculate_type_effectiveness(boss_move_type, card_types)
    else:
        # 若未指定 Boss 招式，以 Boss 本身屬性攻擊計算平均承受倍率
        if boss_types:
            mults = [calculate_type_effectiveness(bt, card_types) for bt in boss_types]
            defensive_mult = sum(mults) / len(mults)

    # 7. 生成作戰優勢標籤
    tags = []
    if type_mult >= 4.0:
        tags.append("💥 4倍極限剋制")
    elif type_mult >= 2.0:
        tags.append("🎯 2倍弱點剋制")
    elif type_mult <= 0.5:
        tags.append("⚠️ 屬性被抗")

    if special != "無":
        tags.append(f"✨ {special}")

    if defensive_mult <= 0.5:
        tags.append("🛡️ 絕佳抗性防守")
    elif defensive_mult >= 2.0:
        tags.append("⚠️ 易被Boss反擊")

    return {
        "card": card,
        "type_mult": type_mult,
        "stab_mult": stab_mult,
        "special_mult": special_mult,
        "damage_score": round(damage_score, 1),
        "defensive_mult": defensive_mult,
        "tags": tags,
        "is_super_effective": type_mult > 1.0
    }

def recommend_best_lineup(
    candidate_cards: List[Dict[str, Any]],
    boss_types: List[str],
    boss_name: str = "目標寶可夢",
    boss_move_type: Optional[str] = None,
    team_size: int = 3
) -> Dict[str, Any]:
    """
    智慧陣容推薦演算法：
    根據輸入的 Boss 屬性，從候選卡匣庫中精選出最強輸出、最佳搭配的 2~3 張卡匣陣容
    """
    if not candidate_cards:
        return {
            "success": False,
            "message": "候選卡匣庫為空，請先加入或勾選擁有的卡匣！",
            "boss_weaknesses": get_weaknesses(boss_types),
            "recommendations": [],
            "top_team": [],
            "strategy": ""
        }

    # 評估所有卡匣面對 Boss 的數據
    evaluations = []
    for card in candidate_cards:
        eval_res = evaluate_card_performance(card, boss_types, boss_move_type)
        evaluations.append(eval_res)

    # 依傷害評分降序排序
    evaluations.sort(key=lambda x: x["damage_score"], reverse=True)

    # 選出 TOP 隊伍（確保多樣性與最高效益）
    top_team = []
    seen_names = set()
    for ev in evaluations:
        c_name = ev["card"]["name"]
        # 避免同名寶可夢過度重複（除非卡匣極少）
        if c_name not in seen_names or len(evaluations) <= team_size:
            top_team.append(ev)
            seen_names.add(c_name)
        if len(top_team) >= team_size:
            break

    # 若去重後不足 team_size，補足前幾名
    if len(top_team) < team_size and len(evaluations) >= team_size:
        top_team = evaluations[:team_size]

    # 計算弱點倍率排行
    weaknesses = get_weaknesses(boss_types)
    sorted_weaknesses = sorted(
        [(k, v) for k, v in weaknesses.items() if v > 1.0],
        key=lambda x: x[1],
        reverse=True
    )

    # 生成對戰戰術策略指導
    strategy_lines = []
    if sorted_weaknesses:
        weak_str = "、".join([f"{w[0]} ({w[1]}x)" for w in sorted_weaknesses])
        strategy_lines.append(f"🔍 **目標弱點分析**：{boss_name} 主要弱點屬性為 **{weak_str}**。")
    else:
        strategy_lines.append(f"🔍 **目標弱點分析**：{boss_name} 沒有明顯雙倍弱點，建議使用純高面板數值打手。")

    if top_team:
        first_pick = top_team[0]
        strategy_lines.append(
            f"⚡ **首發先鋒建議**：推薦以 **【{first_pick['card']['name']}】** ({first_pick['card']['move_name']}) 作為主攻！"
            f"其招式具備 **{first_pick['type_mult']}x** 屬性剋制，配合 {first_pick['card'].get('special', '無')} 能打出極限爆發傷害。"
        )
        if len(top_team) > 1:
            second_pick = top_team[1]
            strategy_lines.append(
                f"🛡️ **第二棒/連擊支援**：推薦 **【{second_pick['card']['name']}】** 進行傷害補足與輪轉防守。"
            )

    return {
        "success": True,
        "boss_name": boss_name,
        "boss_types": boss_types,
        "boss_weaknesses": sorted_weaknesses,
        "recommendations": evaluations,
        "top_team": top_team,
        "strategy": "\n\n".join(strategy_lines)
    }
