"""Official card discovery and append-only Pokédex updates."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import threading
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests

from mezastar_data import CARDS_FILE, TYPES, calculate_type_effectiveness, load_cards


TAIWAN_CASSETTE_URL = "https://www.pokemonmezastar.com.tw/cassette"
INTERNATIONAL_TAG_URL = "https://world.pokemonmezastar.com/sg/tag/"
DEFAULT_UPDATE_STATE_PATH = Path(__file__).resolve().parent / "data" / "official_update_state.json"
CARD_ID_PATTERN = re.compile(r"(?:[A-Z]+-)?\d+-\d+(?:-\d{1,3})?")
_UPDATE_LOCK = threading.Lock()


def calculate_defensive_profile_for_card(types: List[str]):
    from mezastar_data import TYPE_CHART

    weaknesses, resistances, immunities = [], [], []
    for attack_type, multipliers in TYPE_CHART.items():
        total = 1.0
        for defense_type in types:
            total *= multipliers.get(defense_type, 1.0)
        if total >= 2.0:
            weaknesses.append(f"{attack_type} ({total}x)")
        elif total == 0.0:
            immunities.append(f"{attack_type} (0.0x)")
        elif total < 1.0:
            resistances.append(f"{attack_type} ({total}x)")
    return weaknesses, resistances, immunities


def infer_star_and_energy(card_id: str, name: str) -> Tuple[int, int, Dict[str, int]]:
    try:
        number = int(card_id.split("-")[-1])
    except (TypeError, ValueError):
        number = 1
    if number <= 10:
        return 6, 205, {"hp": 200, "atk": 185, "def": 145, "sp_atk": 185, "sp_def": 145, "spd": 165}
    if number <= 25:
        return 5, 135, {"hp": 165, "atk": 140, "def": 120, "sp_atk": 140, "sp_def": 120, "spd": 125}
    if number <= 40:
        return 4, 95, {"hp": 135, "atk": 105, "def": 90, "sp_atk": 105, "sp_def": 90, "spd": 100}
    if number <= 55:
        return 3, 70, {"hp": 115, "atk": 80, "def": 75, "sp_atk": 80, "sp_def": 75, "spd": 80}
    if number <= 65:
        return 2, 50, {"hp": 95, "atk": 65, "def": 65, "sp_atk": 65, "sp_def": 65, "spd": 65}
    return 1, 35, {"hp": 75, "atk": 55, "def": 50, "sp_atk": 50, "sp_def": 50, "spd": 60}


def _normalize_digits(value: str) -> str:
    return value.translate(str.maketrans("０１２３４５６７８９", "0123456789"))


def _series_from_page(soup: BeautifulSoup, cards: List[Dict[str, str]]) -> str:
    text = _normalize_digits(soup.get_text(" ", strip=True))
    match = re.search(r"((?:銀河|星塵|超級)?第\s*\d+\s*彈)", text)
    if match:
        return re.sub(r"\s+", "", match.group(1))
    first_id = cards[0]["id"] if cards else ""
    prefix_map = {
        "2-2": "銀河第2彈", "2-1": "銀河第1彈", "1-4": "星塵第4彈",
        "1-3": "星塵第3彈", "1-2": "星塵第2彈", "1-1": "星塵第1彈",
    }
    return prefix_map.get("-".join(first_id.split("-")[:2]), "官方最新系列")


def parse_taiwan_cards(html: str, page_url: str) -> Tuple[str, List[Dict[str, str]]]:
    soup = BeautifulSoup(html, "html.parser")
    cards = []
    for node in soup.select(".cassette-card"):
        text = _normalize_digits(node.get_text("\n", strip=True))
        match = CARD_ID_PATTERN.search(text)
        if not match:
            continue
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        card_id = match.group(0)
        try:
            name = lines[lines.index(card_id) + 1]
        except (ValueError, IndexError):
            name = ""
        image = node.select_one("img[src]")
        if name and image:
            cards.append({
                "id": card_id,
                "name": name,
                "image": urljoin(page_url, image.get("src", "")),
                "source_url": page_url,
            })
    return _series_from_page(soup, cards), cards


def parse_international_cards(html: str, page_url: str) -> Dict[str, Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    cards = {}
    for node in soup.select(".tag-all_list_child"):
        id_node, name_node, image = node.select_one(".tag-no"), node.select_one(".tag-name"), node.select_one("img[src]")
        if not id_node or not name_node or not image:
            continue
        card_id = _normalize_digits(id_node.get_text(" ", strip=True))
        if not CARD_ID_PATTERN.fullmatch(card_id):
            continue
        cards[card_id] = {
            "id": card_id,
            "name_en": name_node.get_text(" ", strip=True),
            "image_en": urljoin(page_url, image.get("src", "")),
            "source_url": page_url,
        }
    return cards


def _request(session, url: str, timeout: float):
    response = session.get(url, headers={"User-Agent": "PokemonMezastarCatalog/2.7 (+append-only)"}, timeout=timeout)
    response.raise_for_status()
    # Both official sites publish UTF-8; charset guessing misidentifies Traditional
    # Chinese as Big5 on some hosts and would store corrupted Pokémon names.
    response.encoding = "utf-8"
    return response


def _discover_international_cards(session, timeout: float) -> Tuple[Dict[str, Dict[str, str]], List[str]]:
    index = _request(session, INTERNATIONAL_TAG_URL, timeout)
    soup = BeautifulSoup(index.text, "html.parser")
    page_urls = [index.url]
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        if re.fullmatch(r"\./\d+/", href):
            page_urls.append(urljoin(index.url, href))
    cards, scanned = {}, []
    for url in dict.fromkeys(page_urls):
        response = index if url == index.url else _request(session, url, timeout)
        cards.update(parse_international_cards(response.text, response.url))
        scanned.append(response.url)
    return cards, scanned


def _scale_metadata(star: int, metadata: Optional[Dict[str, Any]], fallback: Dict[str, int]) -> Dict[str, int]:
    if not metadata:
        return fallback
    factor = {6: 1.30, 5: 1.15, 4: 1.00, 3: 0.90, 2: 0.82, 1: 0.75}.get(star, 1.0)
    return {
        "hp": round((metadata.get("hp", 100) + 55) * factor),
        "atk": round(metadata.get("attack", 100) * factor),
        "def": round(metadata.get("defense", 100) * factor),
        "sp_atk": round(metadata.get("sp_attack", 100) * factor),
        "sp_def": round(metadata.get("sp_defense", 100) * factor),
        "spd": round(metadata.get("speed", 100) * factor),
    }


def _build_new_card(taiwan: Dict[str, str], international: Dict[str, str], series: str) -> Dict[str, Any]:
    star, energy, fallback_stats = infer_star_and_energy(taiwan["id"], taiwan["name"])
    metadata = fetch_online_pokemon_metadata(international["name_en"])
    types = metadata.get("types", ["一般"]) if metadata else ["一般"]
    stats = _scale_metadata(star, metadata, fallback_stats)
    weaknesses, resistances, immunities = calculate_defensive_profile_for_card(types)
    category = "物理" if stats["atk"] >= stats["sp_atk"] else "特殊"
    power = 120 if star == 6 else 100 if star >= 4 else 80
    attack_stat = stats["atk"] if category == "物理" else stats["sp_atk"]
    move_name = f"{types[0]}屬性招式（待卡面校對）"
    return {
        "id": taiwan["id"], "name": taiwan["name"], "name_en": international["name_en"],
        "series": series, "star": star, "energy": energy, "types": types,
        **stats,
        "move_name": move_name, "move_type": types[0], "move_power": power,
        "move_category": category, "move_accuracy": 100,
        "move_damage": round(power * attack_stat),
        "moves": [{"name": move_name, "type": types[0], "category": category,
                   "power": power, "accuracy": 100, "damage": round(power * attack_stat)}],
        "second_move": {}, "special": "官方新卡匣", "special_mechanics": [],
        "has_mega": False, "has_z_move": False, "has_dynamax": False,
        "has_gigantamax": False, "has_double_attack": False, "has_combo_tag": False,
        "has_chain_attack": False, "has_terastal": False, "has_primal": False,
        "weaknesses": weaknesses, "resistances": resistances, "immunities": immunities,
        "image": taiwan["image"], "official_image_en": international["image_en"],
        "official_sources": {
            "taiwan": taiwan["source_url"], "international": international["source_url"],
        },
        "official_verified_fields": ["id", "name", "name_en", "image", "official_image_en"],
        "data_quality": "台灣與國際官方雙來源確認；戰鬥數值由寶可夢基礎資料推估，待卡面校對",
        "added_at": datetime.now().isoformat(timespec="seconds"),
    }


def append_only_merge(existing_cards: List[Dict[str, Any]], candidates: Iterable[Dict[str, Any]]):
    """Pure append-only merge. Existing dictionaries and their order are never changed."""
    existing_ids = {str(card.get("id")) for card in existing_cards}
    additions, protected = [], []
    seen_new = set()
    for candidate in candidates:
        card_id = str(candidate.get("id", "")).strip()
        if not card_id:
            continue
        if card_id in existing_ids:
            protected.append(card_id)
        elif card_id not in seen_new:
            additions.append(candidate)
            seen_new.add(card_id)
    return list(existing_cards) + additions, additions, protected


def _load_raw_cards(path: Path) -> List[Dict[str, Any]]:
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("圖鑑資料格式必須是陣列")
        return data
    return load_cards()


def append_new_cards_only(candidates: Iterable[Dict[str, Any]], path: Path = Path(CARDS_FILE)):
    with _UPDATE_LOCK:
        existing = _load_raw_cards(path)
        merged, additions, protected = append_only_merge(existing, candidates)
        if additions:
            if merged[:len(existing)] != existing:
                raise RuntimeError("附加式保護檢查失敗：既有圖鑑內容遭變更")
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temporary, path)
        return additions, protected


def fetch_and_sync_official_new_cards(
    start_id: int = 1,
    end_id: int = 20,
    auto_push: bool = True,
    session=None,
    cards_path: Path = Path(CARDS_FILE),
    timeout: float = 12.0,
) -> Dict[str, Any]:
    """Discover the latest official set and append IDs confirmed by both official sites."""
    del start_id, end_id  # Kept for backward-compatible callers.
    http = session or requests.Session()
    try:
        taiwan_response = _request(http, TAIWAN_CASSETTE_URL, timeout)
        series, taiwan_cards = parse_taiwan_cards(taiwan_response.text, taiwan_response.url)
        international_cards, international_pages = _discover_international_cards(http, timeout)
    except requests.RequestException as exc:
        return {"success": False, "new_count": 0, "error": f"官方網站連線失敗：{exc}", "sync_message": "未修改圖鑑"}
    except Exception as exc:
        return {"success": False, "new_count": 0, "error": f"官方資料解析失敗：{exc}", "sync_message": "未修改圖鑑"}

    try:
        existing_ids = {str(card.get("id")) for card in _load_raw_cards(cards_path)}
    except (OSError, ValueError, TypeError) as exc:
        return {"success": False, "new_count": 0, "error": f"既有圖鑑無法安全讀取：{exc}",
                "sync_message": "為保護原始圖鑑，已停止更新"}
    pending = []
    verified_pairs = []
    for taiwan in taiwan_cards:
        if taiwan["id"] in existing_ids:
            continue
        international = international_cards.get(taiwan["id"])
        if not international:
            pending.append((taiwan["id"], taiwan["name"], "等待國際官方同卡號確認"))
            continue
        verified_pairs.append((taiwan, international))

    # A new series can contain 70+ cards. Resolve PokeAPI metadata concurrently
    # so an automatic check does not block the mobile page for several minutes.
    with ThreadPoolExecutor(max_workers=min(10, max(1, len(verified_pairs)))) as executor:
        verified = list(executor.map(
            lambda pair: _build_new_card(pair[0], pair[1], series), verified_pairs
        ))

    additions, protected = append_new_cards_only(verified, cards_path)
    sync_message = "已儲存至本機圖鑑；既有卡匣完全未修改"
    if additions and auto_push and cards_path.resolve() == Path(CARDS_FILE).resolve():
        from github_sync import auto_commit_and_push
        _, sync_message = auto_commit_and_push(
            change_summary=f"官方雙來源自動新增 {len(additions)} 款卡匣（append-only）",
            branch="main",
        )
    return {
        "success": True,
        "new_count": len(additions),
        "new_cards": [(card["id"], card["name"], card["series"]) for card in additions],
        "pending_cards": pending,
        "pending_count": len(pending),
        "protected_existing_count": len(existing_ids) + len(protected),
        "scanned_series": [(series, len(taiwan_cards))],
        "official_sources": [taiwan_response.url, *international_pages],
        "sync_message": sync_message if additions else "雙官方來源掃描完成；沒有可安全新增的卡匣，既有資料未變更",
    }


def scheduled_official_update(
    auto_push: bool = True,
    interval_hours: int = 12,
    state_path: Path = DEFAULT_UPDATE_STATE_PATH,
) -> Dict[str, Any]:
    """Run at most twice daily; failures are retried on the next app session."""
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        last_check = datetime.fromisoformat(state.get("last_successful_check", ""))
        if datetime.now() - last_check < timedelta(hours=interval_hours):
            return {"success": True, "skipped": True, "new_count": 0,
                    "sync_message": f"已於 {last_check:%Y-%m-%d %H:%M} 自動檢查"}
    except (OSError, ValueError, TypeError):
        pass
    result = fetch_and_sync_official_new_cards(auto_push=auto_push)
    if result.get("success"):
        state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = state_path.with_suffix(state_path.suffix + ".tmp")
        temporary.write_text(json.dumps({"last_successful_check": datetime.now().isoformat(timespec="seconds")},
                                        ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, state_path)
    return result


def add_custom_card(card_dict: Dict[str, Any]) -> Tuple[bool, str]:
    card_id = str(card_dict.get("id", "")).strip()
    if not card_id:
        return False, "卡匣編號 (ID) 不得為空！"
    additions, protected = append_new_cards_only([card_dict])
    if protected:
        return False, f"卡匣 {card_id} 已存在；依圖鑑保護規則禁止覆寫"
    return True, f"成功新增卡匣：{additions[0].get('name')} ({card_id})"


def batch_import_cards(cards_list: List[Dict[str, Any]]) -> Tuple[int, int]:
    additions, _ = append_new_cards_only(cards_list)
    return len(additions), 0


def fetch_online_pokemon_metadata(pokemon_name: str) -> Optional[Dict[str, Any]]:
    """Fetch Pokémon types, base stats and artwork from PokeAPI."""
    try:
        clean_name = re.sub(r"\(.*?\)", "", pokemon_name).strip()
        name_map = {
            "妙蛙花": "venusaur", "噴火龍": "charizard", "水箭龜": "blastoise", "超夢": "mewtwo",
            "夢幻": "mew", "蒼響": "zacian", "藏瑪然特": "zamazenta", "達克萊伊": "darkrai",
            "基格爾德": "zygarde", "路卡利歐": "lucario", "水君": "suicune", "雷公": "raikou",
            "炎帝": "entei", "烈空坐": "rayquaza", "固拉多": "groudon", "蓋歐卡": "kyogre",
            "耿鬼": "gengar", "無極汰那": "eternatus", "鐵轍跡": "iron-treads",
            "雄偉牙": "great-tusk", "故勒頓": "koraidon", "密勒頓": "miraidon",
            "皮卡丘": "pikachu", "巨金怪": "metagross", "暴噬龜": "drednaw",
        }
        slug = name_map.get(clean_name, clean_name.lower().replace(" ", "-").replace("'", ""))
        response = requests.get(f"https://pokeapi.co/api/v2/pokemon/{slug}", timeout=6)
        if response.status_code != 200:
            return None
        data = response.json()
        type_names = {
            "normal": "一般", "fire": "火", "water": "水", "grass": "草", "electric": "電", "ice": "冰",
            "fighting": "格鬥", "poison": "毒", "ground": "地面", "flying": "飛行", "psychic": "超能力",
            "bug": "蟲", "rock": "岩石", "ghost": "幽靈", "dragon": "龍", "dark": "惡", "steel": "鋼",
            "fairy": "妖精",
        }
        stats = {item["stat"]["name"]: item["base_stat"] for item in data.get("stats", [])}
        artwork = data.get("sprites", {}).get("other", {}).get("official-artwork", {}).get("front_default")
        return {
            "name": pokemon_name,
            "types": [type_names.get(item["type"]["name"], "一般") for item in data.get("types", [])] or ["一般"],
            "sprite": artwork or data.get("sprites", {}).get("front_default"),
            "hp": stats.get("hp", 100), "attack": stats.get("attack", 100),
            "defense": stats.get("defense", 100), "sp_attack": stats.get("special-attack", 100),
            "sp_defense": stats.get("special-defense", 100), "speed": stats.get("speed", 100),
        }
    except (requests.RequestException, ValueError, KeyError):
        return None


def get_full_type_chart_for_defender(defender_types: List[str]) -> Dict[str, float]:
    return {attack_type: calculate_type_effectiveness(attack_type, defender_types) for attack_type in TYPES}
