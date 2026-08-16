"""
Pokemon Mezastar Data & 18-Type Effectiveness Matrix
Contains type chart, type colors, and default comprehensive Mezastar card data.
"""

from typing import Dict, List, Tuple, Optional
import json
import os

# 18 種寶可夢屬性定義
TYPES: List[str] = [
    "一般", "火", "水", "草", "電", "冰",
    "格鬥", "毒", "地面", "飛行", "超能力", "蟲",
    "岩石", "幽靈", "龍", "惡", "鋼", "妖精"
]

# 屬性代表色（Hex 碼）
TYPE_COLORS: Dict[str, str] = {
    "一般": "#A8A878",
    "火": "#F08030",
    "水": "#6890F0",
    "草": "#78C850",
    "電": "#F8D030",
    "冰": "#98D8D8",
    "格鬥": "#C03028",
    "毒": "#A040A0",
    "地面": "#E0C068",
    "飛行": "#A890F0",
    "超能力": "#F85888",
    "蟲": "#A8B820",
    "岩石": "#B8A038",
    "幽靈": "#705898",
    "龍": "#7038F8",
    "惡": "#705848",
    "鋼": "#B8B8D0",
    "妖精": "#EE99AC",
}

# 18 屬性相剋攻擊倍率矩陣 (攻擊方屬性 -> 防守方屬性 -> 傷害倍率)
# 2.0 = 效果絕佳, 0.5 = 效果不好, 0.0 = 無效 (Mezastar中接近無傷害), 1.0 = 普通
TYPE_CHART: Dict[str, Dict[str, float]] = {
    "一般": {
        "一般": 1.0, "火": 1.0, "水": 1.0, "草": 1.0, "電": 1.0, "冰": 1.0,
        "格鬥": 1.0, "毒": 1.0, "地面": 1.0, "飛行": 1.0, "超能力": 1.0, "蟲": 1.0,
        "岩石": 0.5, "幽靈": 0.0, "龍": 1.0, "惡": 1.0, "鋼": 0.5, "妖精": 1.0
    },
    "火": {
        "一般": 1.0, "火": 0.5, "水": 0.5, "草": 2.0, "電": 1.0, "冰": 2.0,
        "格鬥": 1.0, "毒": 1.0, "地面": 1.0, "飛行": 1.0, "超能力": 1.0, "蟲": 2.0,
        "岩石": 0.5, "幽靈": 1.0, "龍": 0.5, "惡": 1.0, "鋼": 2.0, "妖精": 1.0
    },
    "水": {
        "一般": 1.0, "火": 2.0, "水": 0.5, "草": 0.5, "電": 1.0, "冰": 1.0,
        "格鬥": 1.0, "毒": 1.0, "地面": 2.0, "飛行": 1.0, "超能力": 1.0, "蟲": 1.0,
        "岩石": 2.0, "幽靈": 1.0, "龍": 0.5, "惡": 1.0, "鋼": 1.0, "妖精": 1.0
    },
    "草": {
        "一般": 1.0, "火": 0.5, "水": 2.0, "草": 0.5, "電": 1.0, "冰": 1.0,
        "格鬥": 1.0, "毒": 0.5, "地面": 2.0, "飛行": 0.5, "超能力": 1.0, "蟲": 0.5,
        "岩石": 2.0, "幽靈": 1.0, "龍": 0.5, "惡": 1.0, "鋼": 0.5, "妖精": 1.0
    },
    "電": {
        "一般": 1.0, "火": 1.0, "水": 2.0, "草": 0.5, "電": 0.5, "冰": 1.0,
        "格鬥": 1.0, "毒": 1.0, "地面": 0.0, "飛行": 2.0, "超能力": 1.0, "蟲": 1.0,
        "岩石": 1.0, "幽靈": 1.0, "龍": 0.5, "惡": 1.0, "鋼": 1.0, "妖精": 1.0
    },
    "冰": {
        "一般": 1.0, "火": 0.5, "水": 0.5, "草": 2.0, "電": 1.0, "冰": 0.5,
        "格鬥": 1.0, "毒": 1.0, "地面": 2.0, "飛行": 2.0, "超能力": 1.0, "蟲": 1.0,
        "岩石": 1.0, "幽靈": 1.0, "龍": 2.0, "惡": 1.0, "鋼": 0.5, "妖精": 1.0
    },
    "格鬥": {
        "一般": 2.0, "火": 1.0, "水": 1.0, "草": 1.0, "電": 1.0, "冰": 2.0,
        "格鬥": 1.0, "毒": 0.5, "地面": 1.0, "飛行": 0.5, "超能力": 0.5, "蟲": 0.5,
        "岩石": 2.0, "幽靈": 0.0, "龍": 1.0, "惡": 2.0, "鋼": 2.0, "妖精": 0.5
    },
    "毒": {
        "一般": 1.0, "火": 1.0, "水": 1.0, "草": 2.0, "電": 1.0, "冰": 1.0,
        "格鬥": 1.0, "毒": 0.5, "地面": 0.5, "飛行": 1.0, "超能力": 1.0, "蟲": 1.0,
        "岩石": 0.5, "幽靈": 0.5, "龍": 1.0, "惡": 1.0, "鋼": 0.0, "妖精": 2.0
    },
    "地面": {
        "一般": 1.0, "火": 2.0, "水": 1.0, "草": 0.5, "電": 2.0, "冰": 1.0,
        "格鬥": 1.0, "毒": 2.0, "地面": 1.0, "飛行": 0.0, "超能力": 1.0, "蟲": 0.5,
        "岩石": 2.0, "幽靈": 1.0, "龍": 1.0, "惡": 1.0, "鋼": 2.0, "妖精": 1.0
    },
    "飛行": {
        "一般": 1.0, "火": 1.0, "水": 1.0, "草": 2.0, "電": 0.5, "冰": 1.0,
        "格鬥": 2.0, "毒": 1.0, "地面": 1.0, "飛行": 1.0, "超能力": 1.0, "蟲": 2.0,
        "岩石": 0.5, "幽靈": 1.0, "龍": 1.0, "惡": 1.0, "鋼": 0.5, "妖精": 1.0
    },
    "超能力": {
        "一般": 1.0, "火": 1.0, "水": 1.0, "草": 1.0, "電": 1.0, "冰": 1.0,
        "格鬥": 2.0, "毒": 2.0, "地面": 1.0, "飛行": 1.0, "超能力": 0.5, "蟲": 1.0,
        "岩石": 1.0, "幽靈": 1.0, "龍": 1.0, "惡": 0.0, "鋼": 0.5, "妖精": 1.0
    },
    "蟲": {
        "一般": 1.0, "火": 0.5, "水": 1.0, "草": 2.0, "電": 1.0, "冰": 1.0,
        "格鬥": 0.5, "毒": 0.5, "地面": 1.0, "飛行": 0.5, "超能力": 2.0, "蟲": 1.0,
        "岩石": 1.0, "幽靈": 0.5, "龍": 1.0, "惡": 2.0, "鋼": 0.5, "妖精": 0.5
    },
    "岩石": {
        "一般": 1.0, "火": 2.0, "水": 1.0, "草": 1.0, "電": 1.0, "冰": 2.0,
        "格鬥": 0.5, "毒": 1.0, "地面": 0.5, "飛行": 2.0, "超能力": 1.0, "蟲": 2.0,
        "岩石": 1.0, "幽靈": 1.0, "龍": 1.0, "惡": 1.0, "鋼": 0.5, "妖精": 1.0
    },
    "幽靈": {
        "一般": 0.0, "火": 1.0, "水": 1.0, "草": 1.0, "電": 1.0, "冰": 1.0,
        "格鬥": 1.0, "毒": 1.0, "地面": 1.0, "飛行": 1.0, "超能力": 2.0, "蟲": 1.0,
        "岩石": 1.0, "幽靈": 2.0, "龍": 1.0, "惡": 0.5, "鋼": 1.0, "妖精": 1.0
    },
    "龍": {
        "一般": 1.0, "火": 1.0, "水": 1.0, "草": 1.0, "電": 1.0, "冰": 1.0,
        "格鬥": 1.0, "毒": 1.0, "地面": 1.0, "飛行": 1.0, "超能力": 1.0, "蟲": 1.0,
        "岩石": 1.0, "幽靈": 1.0, "龍": 2.0, "惡": 1.0, "鋼": 0.5, "妖精": 0.0
    },
    "惡": {
        "一般": 1.0, "火": 1.0, "水": 1.0, "草": 1.0, "電": 1.0, "冰": 1.0,
        "格鬥": 0.5, "毒": 1.0, "地面": 1.0, "飛行": 1.0, "超能力": 2.0, "蟲": 1.0,
        "岩石": 1.0, "幽靈": 2.0, "龍": 1.0, "惡": 0.5, "鋼": 1.0, "妖精": 0.5
    },
    "鋼": {
        "一般": 1.0, "火": 0.5, "水": 0.5, "草": 1.0, "電": 0.5, "冰": 2.0,
        "格鬥": 1.0, "毒": 1.0, "地面": 1.0, "飛行": 1.0, "超能力": 1.0, "蟲": 1.0,
        "岩石": 2.0, "幽靈": 1.0, "龍": 1.0, "惡": 1.0, "鋼": 0.5, "妖精": 2.0
    },
    "妖精": {
        "一般": 1.0, "火": 0.5, "水": 1.0, "草": 1.0, "電": 1.0, "冰": 1.0,
        "格鬥": 2.0, "毒": 0.5, "地面": 1.0, "飛行": 1.0, "超能力": 1.0, "蟲": 1.0,
        "岩石": 1.0, "幽靈": 1.0, "龍": 2.0, "惡": 2.0, "鋼": 0.5, "妖精": 1.0
    },
}

def calculate_type_effectiveness(attack_type: str, defender_types: List[str]) -> float:
    """
    計算攻擊屬性對守方單或雙屬性的相剋倍率 (例: 4.0, 2.0, 1.0, 0.5, 0.25, 0.0)
    """
    if not attack_type or attack_type not in TYPE_CHART:
        return 1.0
    
    multiplier = 1.0
    for def_t in defender_types:
        if def_t in TYPE_CHART[attack_type]:
            multiplier *= TYPE_CHART[attack_type][def_t]
    return multiplier

def get_weaknesses(defender_types: List[str]) -> Dict[str, float]:
    """
    計算守方受到 18 種屬性攻擊時的倍率列表，並依弱點程度排序
    """
    results = {}
    for atk_t in TYPES:
        mult = calculate_type_effectiveness(atk_t, defender_types)
        results[atk_t] = mult
    return results


# 預設豐富的 Pokemon Mezastar 卡匣資料庫 (包含各彈 6 星超級明星 Superstar、5 星明星、雙重衝刺/極巨/Mega/Z招式/太晶等卡匣)
DEFAULT_MEZASTAR_CARDS = [
    # --- 第1彈 (Set 1) ---
    {
        "id": "1-001",
        "name": "妙蛙花",
        "series": "第1彈",
        "star": 6,
        "types": ["草", "毒"],
        "hp": 182,
        "atk": 132,
        "def": 128,
        "sp_atk": 145,
        "sp_def": 140,
        "spd": 110,
        "move_name": "瘋狂植物",
        "move_type": "草",
        "move_power": 150,
        "special": "極巨化",
        "image": "https://img.pokemondb.net/sprites/home/normal/venusaur.png"
    },
    {
        "id": "1-002",
        "name": "噴火龍",
        "series": "第1彈",
        "star": 6,
        "types": ["火", "飛行"],
        "hp": 178,
        "atk": 120,
        "def": 115,
        "sp_atk": 159,
        "sp_def": 125,
        "spd": 140,
        "move_name": "爆炸烈焰",
        "move_type": "火",
        "move_power": 150,
        "special": "超級進化",
        "image": "https://img.pokemondb.net/sprites/home/normal/charizard.png"
    },
    {
        "id": "1-003",
        "name": "水箭龜",
        "series": "第1彈",
        "star": 6,
        "types": ["水"],
        "hp": 185,
        "atk": 118,
        "def": 145,
        "sp_atk": 135,
        "sp_def": 150,
        "spd": 105,
        "move_name": "加農水砲",
        "move_type": "水",
        "move_power": 150,
        "special": "極巨化",
        "image": "https://img.pokemondb.net/sprites/home/normal/blastoise.png"
    },
    {
        "id": "1-004",
        "name": "超夢",
        "series": "第1彈",
        "star": 6,
        "types": ["超能力"],
        "hp": 195,
        "atk": 145,
        "def": 120,
        "sp_atk": 198,
        "sp_def": 120,
        "spd": 170,
        "move_name": "精神擊破",
        "move_type": "超能力",
        "move_power": 160,
        "special": "超級進化",
        "image": "https://img.pokemondb.net/sprites/home/normal/mewtwo.png"
    },
    {
        "id": "1-005",
        "name": "夢幻",
        "series": "第1彈",
        "star": 6,
        "types": ["超能力"],
        "hp": 180,
        "atk": 140,
        "def": 140,
        "sp_atk": 140,
        "sp_def": 140,
        "spd": 140,
        "move_name": "起源超新星大爆炸",
        "move_type": "超能力",
        "move_power": 185,
        "special": "Z招式",
        "image": "https://img.pokemondb.net/sprites/home/normal/mew.png"
    },
    {
        "id": "1-006",
        "name": "蒼響",
        "series": "第1彈",
        "star": 6,
        "types": ["妖精", "鋼"],
        "hp": 192,
        "atk": 195,
        "def": 145,
        "sp_atk": 110,
        "sp_def": 145,
        "spd": 188,
        "move_name": "巨獸斬",
        "move_type": "鋼",
        "move_power": 170,
        "special": "無",
        "image": "https://img.pokemondb.net/sprites/home/normal/zacian.png"
    },
    {
        "id": "1-007",
        "name": "藏瑪然特",
        "series": "第1彈",
        "star": 6,
        "types": ["格鬥", "鋼"],
        "hp": 192,
        "atk": 160,
        "def": 185,
        "sp_atk": 110,
        "sp_def": 185,
        "spd": 168,
        "move_name": "巨獸彈",
        "move_type": "鋼",
        "move_power": 170,
        "special": "無",
        "image": "https://img.pokemondb.net/sprites/home/normal/zamazenta.png"
    },

    # --- 第2彈 (Set 2) ---
    {
        "id": "2-001",
        "name": "達克萊伊",
        "series": "第2彈",
        "star": 6,
        "types": ["惡"],
        "hp": 175,
        "atk": 125,
        "def": 120,
        "sp_atk": 175,
        "sp_def": 120,
        "spd": 165,
        "move_name": "暗黑洞",
        "move_type": "惡",
        "move_power": 155,
        "special": "無",
        "image": "https://img.pokemondb.net/sprites/home/normal/darkrai.png"
    },
    {
        "id": "2-002",
        "name": "基格爾德",
        "series": "第2彈",
        "star": 6,
        "types": ["龍", "地面"],
        "hp": 230,
        "atk": 140,
        "def": 161,
        "sp_atk": 131,
        "sp_def": 135,
        "spd": 125,
        "move_name": "千箭齊發",
        "move_type": "地面",
        "move_power": 160,
        "special": "無",
        "image": "https://img.pokemondb.net/sprites/home/normal/zygarde-complete.png"
    },
    {
        "id": "2-003",
        "name": "路卡利歐",
        "series": "第2彈",
        "star": 6,
        "types": ["格鬥", "鋼"],
        "hp": 168,
        "atk": 175,
        "def": 118,
        "sp_atk": 160,
        "sp_def": 100,
        "spd": 152,
        "move_name": "波導彈",
        "move_type": "格鬥",
        "move_power": 140,
        "special": "超級進化",
        "image": "https://img.pokemondb.net/sprites/home/normal/lucario.png"
    },
    {
        "id": "2-004",
        "name": "水君",
        "series": "第2彈",
        "star": 6,
        "types": ["水"],
        "hp": 190,
        "atk": 105,
        "def": 155,
        "sp_atk": 120,
        "sp_def": 155,
        "spd": 125,
        "move_name": "水炮",
        "move_type": "水",
        "move_power": 140,
        "special": "無",
        "image": "https://img.pokemondb.net/sprites/home/normal/suicune.png"
    },
    {
        "id": "2-005",
        "name": "雷公",
        "series": "第2彈",
        "star": 6,
        "types": ["電"],
        "hp": 180,
        "atk": 115,
        "def": 105,
        "sp_atk": 155,
        "sp_def": 130,
        "spd": 155,
        "move_name": "打雷",
        "move_type": "電",
        "move_power": 140,
        "special": "無",
        "image": "https://img.pokemondb.net/sprites/home/normal/raikou.png"
    },
    {
        "id": "2-006",
        "name": "炎帝",
        "series": "第2彈",
        "star": 6,
        "types": ["火"],
        "hp": 200,
        "atk": 155,
        "def": 115,
        "sp_atk": 120,
        "sp_def": 105,
        "spd": 140,
        "move_name": "大字爆炎",
        "move_type": "火",
        "move_power": 140,
        "special": "無",
        "image": "https://img.pokemondb.net/sprites/home/normal/entei.png"
    },

    # --- 第3彈 (Set 3) ---
    {
        "id": "3-001",
        "name": "烈空坐",
        "series": "第3彈",
        "star": 6,
        "types": ["龍", "飛行"],
        "hp": 195,
        "atk": 190,
        "def": 130,
        "sp_atk": 190,
        "sp_def": 130,
        "spd": 155,
        "move_name": "畫龍點睛",
        "move_type": "飛行",
        "move_power": 180,
        "special": "超級進化",
        "image": "https://img.pokemondb.net/sprites/home/normal/rayquaza.png"
    },
    {
        "id": "3-002",
        "name": "固拉多",
        "series": "第3彈",
        "star": 6,
        "types": ["地面", "火"],
        "hp": 195,
        "atk": 190,
        "def": 180,
        "sp_atk": 140,
        "sp_def": 120,
        "spd": 120,
        "move_name": "斷崖之劍",
        "move_type": "地面",
        "move_power": 175,
        "special": "原始回歸",
        "image": "https://img.pokemondb.net/sprites/home/normal/groudon.png"
    },
    {
        "id": "3-003",
        "name": "蓋歐卡",
        "series": "第3彈",
        "star": 6,
        "types": ["水"],
        "hp": 195,
        "atk": 140,
        "def": 120,
        "sp_atk": 190,
        "sp_def": 180,
        "spd": 120,
        "move_name": "根源波動",
        "move_type": "水",
        "move_power": 175,
        "special": "原始回歸",
        "image": "https://img.pokemondb.net/sprites/home/normal/kyogre.png"
    },
    {
        "id": "3-004",
        "name": "耿鬼",
        "series": "第3彈",
        "star": 6,
        "types": ["幽靈", "毒"],
        "hp": 160,
        "atk": 95,
        "def": 105,
        "sp_atk": 175,
        "sp_def": 115,
        "spd": 150,
        "move_name": "暗影球",
        "move_type": "幽靈",
        "move_power": 135,
        "special": "極巨化",
        "image": "https://img.pokemondb.net/sprites/home/normal/gengar.png"
    },

    # --- 第4彈 (Set 4) ---
    {
        "id": "4-001",
        "name": "無極汰那",
        "series": "第4彈",
        "star": 6,
        "types": ["毒", "龍"],
        "hp": 235,
        "atk": 115,
        "def": 125,
        "sp_atk": 185,
        "sp_def": 125,
        "spd": 170,
        "move_name": "極巨砲",
        "move_type": "龍",
        "move_power": 180,
        "special": "極巨化",
        "image": "https://img.pokemondb.net/sprites/home/normal/eternatus.png"
    },
    {
        "id": "4-002",
        "name": "急凍鳥 (伽勒爾)",
        "series": "第4彈",
        "star": 6,
        "types": ["超能力", "飛行"],
        "hp": 180,
        "atk": 115,
        "def": 120,
        "sp_atk": 165,
        "sp_def": 135,
        "spd": 135,
        "move_name": "冰冷視線",
        "move_type": "超能力",
        "move_power": 140,
        "special": "無",
        "image": "https://img.pokemondb.net/sprites/home/normal/articuno-galar.png"
    },
    {
        "id": "4-003",
        "name": "閃電鳥 (伽勒爾)",
        "series": "第4彈",
        "star": 6,
        "types": ["格鬥", "飛行"],
        "hp": 180,
        "atk": 165,
        "def": 120,
        "sp_atk": 115,
        "sp_def": 120,
        "spd": 140,
        "move_name": "雷鳴蹴擊",
        "move_type": "格鬥",
        "move_power": 140,
        "special": "無",
        "image": "https://img.pokemondb.net/sprites/home/normal/zapdos-galar.png"
    },
    {
        "id": "4-004",
        "name": "火焰鳥 (伽勒爾)",
        "series": "第4彈",
        "star": 6,
        "types": ["惡", "飛行"],
        "hp": 180,
        "atk": 115,
        "def": 120,
        "sp_atk": 145,
        "sp_def": 165,
        "spd": 130,
        "move_name": "怒火中燒",
        "move_type": "惡",
        "move_power": 140,
        "special": "無",
        "image": "https://img.pokemondb.net/sprites/home/normal/moltres-galar.png"
    },

    # --- 超級第1~2彈 (Super Series) ---
    {
        "id": "ST1-001",
        "name": "騎拉帝納",
        "series": "超級第1彈",
        "star": 6,
        "types": ["幽靈", "龍"],
        "hp": 240,
        "atk": 150,
        "def": 150,
        "sp_atk": 150,
        "sp_def": 150,
        "spd": 120,
        "move_name": "暗影潛襲",
        "move_type": "幽靈",
        "move_power": 170,
        "special": "雙重衝刺",
        "image": "https://img.pokemondb.net/sprites/home/normal/giratina-altered.png"
    },
    {
        "id": "ST1-002",
        "name": "帝牙盧卡",
        "series": "超級第1彈",
        "star": 6,
        "types": ["鋼", "龍"],
        "hp": 190,
        "atk": 150,
        "def": 150,
        "sp_atk": 180,
        "sp_def": 130,
        "spd": 120,
        "move_name": "時光咆哮",
        "move_type": "龍",
        "move_power": 175,
        "special": "雙重衝刺",
        "image": "https://img.pokemondb.net/sprites/home/normal/dialga.png"
    },
    {
        "id": "ST1-003",
        "name": "帕路奇亞",
        "series": "超級第1彈",
        "star": 6,
        "types": ["水", "龍"],
        "hp": 180,
        "atk": 150,
        "def": 130,
        "sp_atk": 180,
        "sp_def": 150,
        "spd": 130,
        "move_name": "亞空裂斬",
        "move_type": "龍",
        "move_power": 175,
        "special": "雙重衝刺",
        "image": "https://img.pokemondb.net/sprites/home/normal/palkia.png"
    },

    # --- 雙重衝刺第1~4彈 (Double Series) ---
    {
        "id": "DC1-001",
        "name": "蕾冠王 (白馬騎士)",
        "series": "雙重衝刺第1彈",
        "star": 6,
        "types": ["超能力", "冰"],
        "hp": 190,
        "atk": 185,
        "def": 165,
        "sp_atk": 115,
        "sp_def": 145,
        "spd": 80,
        "move_name": "雪矛",
        "move_type": "冰",
        "move_power": 180,
        "special": "極巨化",
        "image": "https://img.pokemondb.net/sprites/home/normal/calyrex-ice.png"
    },
    {
        "id": "DC1-002",
        "name": "蕾冠王 (黑馬騎士)",
        "series": "雙重衝刺第1彈",
        "star": 6,
        "types": ["超能力", "幽靈"],
        "hp": 190,
        "atk": 115,
        "def": 110,
        "sp_atk": 195,
        "sp_def": 130,
        "spd": 190,
        "move_name": "星碎",
        "move_type": "幽靈",
        "move_power": 180,
        "special": "極巨化",
        "image": "https://img.pokemondb.net/sprites/home/normal/calyrex-shadow.png"
    },
    {
        "id": "DC2-001",
        "name": "阿爾宙斯",
        "series": "雙重衝刺第2彈",
        "star": 6,
        "types": ["一般"],
        "hp": 210,
        "atk": 160,
        "def": 160,
        "sp_atk": 160,
        "sp_def": 160,
        "spd": 160,
        "move_name": "制裁光礫",
        "move_type": "一般",
        "move_power": 185,
        "special": "雙重招式",
        "image": "https://img.pokemondb.net/sprites/home/normal/arceus.png"
    },
    {
        "id": "DC2-002",
        "name": "索爾迦雷歐",
        "series": "雙重衝刺第2彈",
        "star": 6,
        "types": ["超能力", "鋼"],
        "hp": 227,
        "atk": 177,
        "def": 147,
        "sp_atk": 143,
        "sp_def": 119,
        "spd": 127,
        "move_name": "流星閃衝",
        "move_type": "鋼",
        "move_power": 165,
        "special": "Z招式",
        "image": "https://img.pokemondb.net/sprites/home/normal/solgaleo.png"
    },
    {
        "id": "DC2-003",
        "name": "露奈雅拉",
        "series": "雙重衝刺第2彈",
        "star": 6,
        "types": ["超能力", "幽靈"],
        "hp": 227,
        "atk": 143,
        "def": 119,
        "sp_atk": 177,
        "sp_def": 147,
        "spd": 127,
        "move_name": "暗影之光",
        "move_type": "幽靈",
        "move_power": 165,
        "special": "Z招式",
        "image": "https://img.pokemondb.net/sprites/home/normal/lunala.png"
    },

    # --- GS / 太晶彈 (Gorgeous Star & Terastal Series) ---
    {
        "id": "GS1-001",
        "name": "故勒頓",
        "series": "GS第1彈",
        "star": 6,
        "types": ["格鬥", "龍"],
        "hp": 190,
        "atk": 185,
        "def": 150,
        "sp_atk": 115,
        "sp_def": 130,
        "spd": 175,
        "move_name": "全開猛撞",
        "move_type": "格鬥",
        "move_power": 180,
        "special": "太晶化",
        "image": "https://img.pokemondb.net/sprites/home/normal/koraidon.png"
    },
    {
        "id": "GS1-002",
        "name": "密勒頓",
        "series": "GS第1彈",
        "star": 6,
        "types": ["電", "龍"],
        "hp": 190,
        "atk": 115,
        "def": 130,
        "sp_atk": 185,
        "sp_def": 150,
        "spd": 175,
        "move_name": "閃電猛衝",
        "move_type": "電",
        "move_power": 180,
        "special": "太晶化",
        "image": "https://img.pokemondb.net/sprites/home/normal/miraidon.png"
    },
    {
        "id": "GS2-001",
        "name": "太樂巴戈斯",
        "series": "GS第2彈",
        "star": 6,
        "types": ["一般"],
        "hp": 220,
        "atk": 135,
        "def": 150,
        "sp_atk": 170,
        "sp_def": 150,
        "spd": 115,
        "move_name": "太晶晶光",
        "move_type": "一般",
        "move_power": 185,
        "special": "太晶化",
        "image": "https://img.pokemondb.net/sprites/home/normal/terapagos-stellar.png"
    },
    {
        "id": "GS2-002",
        "name": "厄鬼椪 (碧草面具)",
        "series": "GS第2彈",
        "star": 6,
        "types": ["草"],
        "hp": 170,
        "atk": 160,
        "def": 114,
        "sp_atk": 90,
        "sp_def": 126,
        "spd": 150,
        "move_name": "棘藤棒",
        "move_type": "草",
        "move_power": 150,
        "special": "太晶化",
        "image": "https://img.pokemondb.net/sprites/home/normal/ogerpon.png"
    },

    # --- 5星 常用強力明星卡 (5-Star Stars) ---
    {
        "id": "5-001",
        "name": "皮卡丘",
        "series": "第1彈",
        "star": 5,
        "types": ["電"],
        "hp": 140,
        "atk": 120,
        "def": 90,
        "sp_atk": 110,
        "sp_def": 100,
        "spd": 130,
        "move_name": "十萬伏特",
        "move_type": "電",
        "move_power": 120,
        "special": "極巨化",
        "image": "https://img.pokemondb.net/sprites/home/normal/pikachu.png"
    },
    {
        "id": "5-002",
        "name": "巨金怪",
        "series": "第2彈",
        "star": 5,
        "types": ["鋼", "超能力"],
        "hp": 165,
        "atk": 155,
        "def": 150,
        "sp_atk": 115,
        "sp_def": 110,
        "spd": 100,
        "move_name": "彗星拳",
        "move_type": "鋼",
        "move_power": 130,
        "special": "超級進化",
        "image": "https://img.pokemondb.net/sprites/home/normal/metagross.png"
    },
    {
        "id": "5-003",
        "name": "烈咬陸鯊",
        "series": "第3彈",
        "star": 5,
        "types": ["龍", "地面"],
        "hp": 178,
        "atk": 160,
        "def": 125,
        "sp_atk": 100,
        "sp_def": 115,
        "spd": 132,
        "move_name": "龍爪",
        "move_type": "龍",
        "move_power": 130,
        "special": "超級進化",
        "image": "https://img.pokemondb.net/sprites/home/normal/garchomp.png"
    },
    {
        "id": "5-004",
        "name": "甲賀忍蛙",
        "series": "超級第1彈",
        "star": 5,
        "types": ["水", "惡"],
        "hp": 155,
        "atk": 130,
        "def": 97,
        "sp_atk": 143,
        "sp_def": 101,
        "spd": 162,
        "move_name": "飛水手裏劍",
        "move_type": "水",
        "move_power": 125,
        "special": "無",
        "image": "https://img.pokemondb.net/sprites/home/normal/greninja.png"
    },
    {
        "id": "5-005",
        "name": "班基拉斯",
        "series": "超級第2彈",
        "star": 5,
        "types": ["岩石", "惡"],
        "hp": 180,
        "atk": 164,
        "def": 140,
        "sp_atk": 115,
        "sp_def": 130,
        "spd": 91,
        "move_name": "尖石攻擊",
        "move_type": "岩石",
        "move_power": 130,
        "special": "超級進化",
        "image": "https://img.pokemondb.net/sprites/home/normal/tyranitar.png"
    }
]

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CARDS_FILE = os.path.join(DATA_DIR, "mezastar_cards.json")

def load_cards() -> List[Dict]:
    """載入所有卡匣資料"""
    if os.path.exists(CARDS_FILE):
        try:
            with open(CARDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading cards file: {e}")
    # 若檔案不存在或損壞，回傳預設卡匣
    return DEFAULT_MEZASTAR_CARDS

def save_cards(cards: List[Dict]) -> bool:
    """儲存卡匣資料至 JSON 檔案"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CARDS_FILE, "w", encoding="utf-8") as f:
            json.dump(cards, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving cards file: {e}")
        return False
