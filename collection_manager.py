"""
Pokemon Mezastar Collection Manager
Handles loading, saving, toggling, importing, and exporting user's card collection.
"""

from typing import Dict, List, Set, Any
import json
import os
from mezastar_data import load_cards, DATA_DIR

COLLECTION_FILE = os.path.join(DATA_DIR, "my_collection.json")

def load_user_collection_ids() -> Set[str]:
    """載入使用者已擁有卡匣的 ID 集合"""
    if os.path.exists(COLLECTION_FILE):
        try:
            with open(COLLECTION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
                elif isinstance(data, dict) and "owned_ids" in data:
                    return set(data["owned_ids"])
        except Exception as e:
            print(f"Error loading collection: {e}")
    # 預設擁有部分 6 星與 5 星卡方便初次體驗
    default_ids = {"1-002", "1-004", "3-001", "DC1-001", "GS1-001", "5-001"}
    return default_ids

def save_user_collection_ids(owned_ids: Set[str]) -> bool:
    """儲存使用者已擁有卡匣的 ID 集合"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(COLLECTION_FILE, "w", encoding="utf-8") as f:
            json.dump(list(owned_ids), f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving collection: {e}")
        return False

def get_user_cards(owned_ids: Set[str] = None) -> List[Dict[str, Any]]:
    """取得使用者目前所持有的所有卡匣完整資訊"""
    if owned_ids is None:
        owned_ids = load_user_collection_ids()
    all_cards = load_cards()
    return [card for card in all_cards if card.get("id") in owned_ids]

def toggle_card_ownership(card_id: str, owned_ids: Set[str]) -> Set[str]:
    """切換卡匣擁有狀態"""
    if card_id in owned_ids:
        owned_ids.remove(card_id)
    else:
        owned_ids.add(card_id)
    save_user_collection_ids(owned_ids)
    return owned_ids

def get_collection_stats(owned_ids: Set[str] = None) -> Dict[str, Any]:
    """計算收藏庫統計數據"""
    if owned_ids is None:
        owned_ids = load_user_collection_ids()
    all_cards = load_cards()
    user_cards = [c for c in all_cards if c.get("id") in owned_ids]

    star_counts = {6: 0, 5: 0, 4: 0, 3: 0, 2: 0}
    type_counts = {}

    for c in user_cards:
        star = c.get("star", 5)
        star_counts[star] = star_counts.get(star, 0) + 1
        for t in c.get("types", []):
            type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "total_owned": len(user_cards),
        "total_available": len(all_cards),
        "star_counts": star_counts,
        "type_counts": type_counts
    }
