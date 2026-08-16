"""
Pokemon Mezastar Web Scraper & Card Data Importer
Enables fetching, parsing, and expanding card datasets from web sources or adding custom cards.
"""

from typing import Dict, List, Any, Optional, Tuple
import requests
from bs4 import BeautifulSoup
import json
import re
from mezastar_data import load_cards, save_cards, TYPES

def add_custom_card(card_dict: Dict[str, Any]) -> Tuple[bool, str]:
    """
    手動或透過網路新增一張卡匣資料
    """
    cards = load_cards()
    # 檢查 ID 是否重複
    c_id = card_dict.get("id", "").strip()
    if not c_id:
        return False, "卡匣編號 (ID) 不得為空！"
    
    # 尋找現有卡匣
    for i, c in enumerate(cards):
        if c.get("id") == c_id:
            cards[i] = card_dict
            save_cards(cards)
            return True, f"成功更新現有卡匣：{card_dict.get('name')} ({c_id})"
    
    cards.append(card_dict)
    save_cards(cards)
    return True, f"成功新增卡匣：{card_dict.get('name')} ({c_id})"

def batch_import_cards(cards_list: List[Dict[str, Any]]) -> Tuple[int, int]:
    """
    批次匯入卡匣清單
    回傳: (新增數量, 更新數量)
    """
    existing_cards = {c["id"]: c for c in load_cards()}
    added_count = 0
    updated_count = 0

    for new_c in cards_list:
        c_id = new_c.get("id")
        if not c_id:
            continue
        if c_id in existing_cards:
            existing_cards[c_id] = new_c
            updated_count += 1
        else:
            existing_cards[c_id] = new_c
            added_count += 1

    save_cards(list(existing_cards.values()))
    return added_count, updated_count

def fetch_online_pokemon_metadata(pokemon_name: str) -> Optional[Dict[str, Any]]:
    """
    從公開網路 PokeAPI 或開放百科獲取寶可夢基本數值、屬性與圖片
    """
    try:
        # 清理名稱（去除括號等特殊備註，提取純寶可夢名）
        clean_name = re.sub(r"\(.*?\)", "", pokemon_name).strip()
        
        # 中英寶可夢名稱快速字典或直接對應
        name_map = {
            "妙蛙花": "venusaur", "噴火龍": "charizard", "水箭龜": "blastoise",
            "超夢": "mewtwo", "夢幻": "mew", "蒼響": "zacian", "藏瑪然特": "zamazenta",
            "達克萊伊": "darkrai", "基格爾德": "zygarde", "路卡利歐": "lucario",
            "水君": "suicune", "雷公": "raikou", "炎帝": "entei",
            "烈空坐": "rayquaza", "固拉多": "groudon", "蓋歐卡": "kyogre",
            "耿鬼": "gengar", "無極汰那": "eternatus", "急凍鳥": "articuno",
            "閃電鳥": "zapdos", "火焰鳥": "moltres", "騎拉帝納": "giratina-altered",
            "帝牙盧卡": "dialga", "帕路奇亞": "palkia", "蕾冠王": "calyrex",
            "阿爾宙斯": "arceus", "索爾迦雷歐": "solgaleo", "露奈雅拉": "lunala",
            "故勒頓": "koraidon", "密勒頓": "miraidon", "太樂巴戈斯": "terapagos",
            "厄鬼椪": "ogerpon", "皮卡丘": "pikachu", "巨金怪": "metagross",
            "烈咬陸鯊": "garchomp", "甲賀忍蛙": "greninja", "班基拉斯": "tyranitar",
            "四顎針龍": "naganadel", "捷克羅姆": "zekrom", "雷希拉姆": "reshiram",
            "酋雷姆": "kyurem", "卡璞・鳴鳴": "tapu-koko", "伊裴爾塔爾": "yveltal",
            "哲爾尼亞斯": "xerneas", "拉帝歐斯": "latios", "拉帝亞斯": "latias"
        }

        eng_name = name_map.get(clean_name, clean_name.lower())
        url = f"https://pokeapi.co/api/v2/pokemon/{eng_name}"
        resp = requests.get(url, timeout=5)
        
        if resp.status_code == 200:
            data = resp.json()
            type_translations = {
                "normal": "一般", "fire": "火", "water": "水", "grass": "草",
                "electric": "電", "ice": "冰", "fighting": "格鬥", "poison": "毒",
                "ground": "地面", "flying": "飛行", "psychic": "超能力", "bug": "蟲",
                "rock": "岩石", "ghost": "幽靈", "dragon": "龍", "dark": "惡",
                "steel": "鋼", "fairy": "妖精"
            }
            types = [type_translations.get(t["type"]["name"], "一般") for t in data.get("types", [])]
            sprite_url = data.get("sprites", {}).get("other", {}).get("official-artwork", {}).get("front_default") or data.get("sprites", {}).get("front_default")
            
            stats = {s["stat"]["name"]: s["base_stat"] for s in data.get("stats", [])}
            return {
                "name": pokemon_name,
                "types": types,
                "hp": stats.get("hp", 150),
                "atk": stats.get("attack", 130),
                "def": stats.get("defense", 120),
                "sp_atk": stats.get("special-attack", 130),
                "sp_def": stats.get("special-defense", 120),
                "spd": stats.get("speed", 120),
                "image": sprite_url
            }
    except Exception as e:
        print(f"Fetch metadata error for {pokemon_name}: {e}")
    return None
