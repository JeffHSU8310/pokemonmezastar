"""
Pokemon Mezastar Collection Manager
Handles loading, saving, toggling, importing, and exporting user's card collection.
Supports JSON export/import, shareable code generation, CSV export, and merge/overwrite modes.
"""

from typing import Dict, List, Set, Any, Tuple
import json
import os
import io
import csv
import base64
import time
from mezastar_data import load_cards, DATA_DIR, sort_cards_chronological

COLLECTION_FILE = os.path.join(DATA_DIR, "my_collection.json")

def get_card_alias_map() -> Tuple[Dict[str, str], Dict[str, Set[str]]]:
    """
    建立卡匣標準 ID 與別名雙向映射表。
    alias_to_canonical: {'1-001': '1-1-001', '001': '1-1-001', '1-1-001': '1-1-001'}
    canonical_to_aliases: {'1-1-001': {'1-1-001', '1-001', '001'}}
    """
    all_cards = load_cards()
    alias_to_canonical: Dict[str, str] = {}
    canonical_to_aliases: Dict[str, Set[str]] = {}

    for c in all_cards:
        cid = c.get("id", "")
        if not cid:
            continue
        aliases = {cid, cid.strip()}
        parts = cid.split("-")
        if len(parts) >= 2:
            aliases.add(f"{parts[0]}-{parts[-1]}")
            aliases.add(parts[-1])
        
        canonical_to_aliases[cid] = aliases
        for a in aliases:
            if a not in alias_to_canonical:
                alias_to_canonical[a] = cid

    return alias_to_canonical, canonical_to_aliases

def normalize_collection_ids(raw_ids: Set[str]) -> Set[str]:
    """將任意舊格式或別名 ID 自動轉化為標準規範 ID"""
    alias_map, _ = get_card_alias_map()
    normalized: Set[str] = set()
    for rid in raw_ids:
        rid_str = str(rid).strip()
        if rid_str in alias_map:
            normalized.add(alias_map[rid_str])
        else:
            normalized.add(rid_str)
    return normalized

def load_user_collection_ids() -> Set[str]:
    """載入使用者已擁有卡匣的 ID 集合 (自動進行 ID 標準化)"""
    if os.path.exists(COLLECTION_FILE):
        try:
            with open(COLLECTION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                raw_ids: Set[str] = set()
                if isinstance(data, list):
                    raw_ids = set(data)
                elif isinstance(data, dict):
                    if "owned_ids" in data and isinstance(data["owned_ids"], list):
                        raw_ids = set(data["owned_ids"])
                    elif "cards" in data and isinstance(data["cards"], list):
                        raw_ids = {c.get("id") for c in data["cards"] if isinstance(c, dict) and "id" in c}
                if raw_ids:
                    return normalize_collection_ids(raw_ids)
        except Exception as e:
            print(f"Error loading collection: {e}")
    # 預設擁有部分卡匣
    return set()

def save_user_collection_ids(owned_ids: Set[str]) -> bool:
    """儲存使用者已擁有卡匣的 ID 集合至本機/儲存檔 (自動儲存標準 ID)"""
    try:
        norm_ids = normalize_collection_ids(owned_ids)
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(COLLECTION_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(norm_ids)), f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving collection: {e}")
        return False

def get_user_cards(owned_ids: Set[str] | None = None) -> List[Dict[str, Any]]:
    """取得使用者目前所持有的所有卡匣完整資訊 (依照最新發行時間與編號排序)"""
    if owned_ids is None:
        owned_ids = load_user_collection_ids()
    norm_ids = normalize_collection_ids(owned_ids)
    all_cards = load_cards()
    
    id_map = {c.get("id"): c for c in all_cards}
    matched_cards = [id_map[cid] for cid in norm_ids if cid in id_map]
    return sort_cards_chronological(matched_cards)

def toggle_card_ownership(card_id: str, owned_ids: Set[str]) -> Set[str]:
    """
    切換卡匣擁有狀態並自動存檔。
    若該卡匣或其任何別名已存在，則徹底移除所有別名；否則加入標準 ID。
    """
    alias_map, canonical_aliases = get_card_alias_map()
    canonical_id = alias_map.get(card_id.strip(), card_id.strip())
    related_aliases = canonical_aliases.get(canonical_id, {card_id.strip()})

    # 檢查是否已在 owned_ids 中 (包含別名)
    existing_in_owned = related_aliases.intersection(owned_ids)

    if existing_in_owned or canonical_id in owned_ids:
        # 徹底清除該卡的所有別名與標準 ID
        owned_ids.difference_update(related_aliases)
        owned_ids.discard(canonical_id)
    else:
        # 加入標準 ID
        owned_ids.add(canonical_id)

    save_user_collection_ids(owned_ids)
    return owned_ids

def get_collection_stats(owned_ids: Set[str] | None = None) -> Dict[str, Any]:
    """計算收藏庫統計數據（星級分佈、屬性分佈、總收集率）"""
    if owned_ids is None:
        owned_ids = load_user_collection_ids()
    all_cards = load_cards()
    user_cards = [c for c in all_cards if c.get("id") in owned_ids]

    star_counts = {6: 0, 5: 0, 4: 0, 3: 0, 2: 0}
    type_counts: Dict[str, int] = {}

    for c in user_cards:
        star = c.get("star", 5)
        star_counts[star] = star_counts.get(star, 0) + 1
        for t in c.get("types", []):
            type_counts[t] = type_counts.get(t, 0) + 1

    total_available = len(all_cards)
    total_owned = len(user_cards)
    completion_rate = round((total_owned / total_available * 100), 1) if total_available > 0 else 0.0

    return {
        "total_owned": total_owned,
        "total_available": total_available,
        "completion_rate": completion_rate,
        "star_counts": star_counts,
        "type_counts": type_counts
    }

# ==============================================================================
# 📤 匯出功能 (Export Functions)
# ==============================================================================

def export_collection_json(owned_ids: Set[str] | None = None) -> str:
    """匯出結構化 JSON 備份字串（包含時間戳、版本與完整卡匣清單）"""
    if owned_ids is None:
        owned_ids = load_user_collection_ids()
    user_cards = get_user_cards(owned_ids)
    
    payload = {
        "app": "Pokemon Mezastar Battle Optimizer",
        "version": "2.1.0",
        "exported_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "total_count": len(owned_ids),
        "owned_ids": sorted(list(owned_ids)),
        "cards_summary": [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "star": c.get("star"),
                "series": c.get("series"),
                "types": c.get("types"),
                "special": c.get("special", "Normal")
            }
            for c in user_cards
        ]
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)

def export_collection_share_code(owned_ids: Set[str] | None = None) -> str:
    """匯出簡潔的分享代碼（以 Base64 編碼，便於在手機 LINE / 訊息 / 社群快速複製分享）"""
    if owned_ids is None:
        owned_ids = load_user_collection_ids()
    sorted_ids = sorted(list(owned_ids))
    raw_str = ",".join(sorted_ids)
    encoded = base64.b64encode(raw_str.encode("utf-8")).decode("utf-8")
    return f"MEZASTAR-V1:{encoded}"

def export_collection_csv(owned_ids: Set[str] | None = None) -> str:
    """匯出 CSV 格式字串（方便使用 Excel、Google 試算表檢視與列印）"""
    if owned_ids is None:
        owned_ids = load_user_collection_ids()
    user_cards = get_user_cards(owned_ids)
    
    output = io.StringIO()
    writer = csv.writer(output)
    # 寫入繁體中文欄位表頭
    writer.writerow(["卡匣編號", "寶可夢名稱", "星級", "彈別系列", "屬性", "HP", "攻擊", "特攻", "防禦", "特防", "速度", "招式名稱", "招式屬性", "招式威力", "特殊機制"])
    
    for c in user_cards:
        types_str = "/".join(c.get("types", []))
        stats = c.get("stats", {})
        writer.writerow([
            c.get("id", ""),
            c.get("name", ""),
            f"{c.get('star', '')}星",
            c.get("series", ""),
            types_str,
            stats.get("hp", ""),
            stats.get("atk", ""),
            stats.get("sp_atk", ""),
            stats.get("def", ""),
            stats.get("sp_def", ""),
            stats.get("spd", ""),
            c.get("move_name", ""),
            c.get("move_type", ""),
            c.get("move_power", ""),
            c.get("special", "Normal")
        ])
    return output.getvalue()

# ==============================================================================
# 📥 匯入功能 (Import Functions)
# ==============================================================================

def import_collection_from_json(json_str: str, mode: str = "merge") -> Tuple[bool, str, Set[str]]:
    """
    從 JSON 字串匯入卡匣清單。
    :param json_str: JSON 字串內容
    :param mode: 'merge' (合併到現有收藏) 或 'overwrite' (完全覆蓋現有收藏)
    :return: (是否成功, 提示訊息, 更新後的 ID 集合)
    """
    try:
        data = json.loads(json_str)
        incoming_ids: Set[str] = set()
        
        if isinstance(data, list):
            incoming_ids = {str(item).strip() for item in data if isinstance(item, (str, int))}
        elif isinstance(data, dict):
            if "owned_ids" in data and isinstance(data["owned_ids"], list):
                incoming_ids = {str(item).strip() for item in data["owned_ids"]}
            elif "cards_summary" in data and isinstance(data["cards_summary"], list):
                incoming_ids = {str(c.get("id")).strip() for c in data["cards_summary"] if isinstance(c, dict) and "id" in c}
            elif "cards" in data and isinstance(data["cards"], list):
                incoming_ids = {str(c.get("id")).strip() for c in data["cards"] if isinstance(c, dict) and "id" in c}
        
        if not incoming_ids:
            return False, "未能從檔案中解析出有效的卡匣編號清單", set()

        all_cards = load_cards()
        valid_system_ids = {c.get("id") for c in all_cards}
        system_match_count = sum(1 for cid in incoming_ids if cid in valid_system_ids)

        current_ids = load_user_collection_ids()
        if mode == "overwrite":
            final_ids = incoming_ids
        else:
            final_ids = current_ids.union(incoming_ids)

        save_user_collection_ids(final_ids)
        
        msg = f"成功匯入 {len(incoming_ids)} 張卡匣（包含 {system_match_count} 款圖鑑卡匣）！目前收藏總數：{len(final_ids)} 張。"
        return True, msg, final_ids
    except Exception as e:
        return False, f"JSON 解析失敗: {str(e)}", set()

def import_collection_from_share_code(code_str: str, mode: str = "merge") -> Tuple[bool, str, Set[str]]:
    """
    從分享代碼字串匯入卡匣清單。
    :param code_str: 分享代碼字串（例如 'MEZASTAR-V1:...' 或逗號分隔編號）
    :param mode: 'merge' (合併) 或 'overwrite' (覆蓋)
    :return: (是否成功, 提示訊息, 更新後的 ID 集合)
    """
    try:
        clean_code = code_str.strip()
        if clean_code.startswith("MEZASTAR-V1:"):
            base64_content = clean_code.replace("MEZASTAR-V1:", "").strip()
            decoded_str = base64.b64decode(base64_content).decode("utf-8")
            raw_ids = [x.strip() for x in decoded_str.split(",") if x.strip()]
        else:
            # 支援直接貼上逗號、換行、空白分隔的卡匣 ID
            raw_ids = [x.strip().strip("\"'").strip() for x in clean_code.replace("\n", ",").replace(" ", ",").split(",") if x.strip()]
        
        incoming_ids = set(raw_ids)
        if not incoming_ids:
            return False, "分享代碼為空或格式無效", set()

        all_cards = load_cards()
        valid_system_ids = {c.get("id") for c in all_cards}
        system_match_count = sum(1 for cid in incoming_ids if cid in valid_system_ids)
        
        current_ids = load_user_collection_ids()
        if mode == "overwrite":
            final_ids = incoming_ids
        else:
            final_ids = current_ids.union(incoming_ids)

        save_user_collection_ids(final_ids)
        msg = f"代碼解析成功！匯入 {len(incoming_ids)} 張卡匣（包含 {system_match_count} 款圖鑑卡匣），目前收藏總數：{len(final_ids)} 張。"
        return True, msg, final_ids
    except Exception as e:
        return False, f"代碼解析失敗: {str(e)}", set()
