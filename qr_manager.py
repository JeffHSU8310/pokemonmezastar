import json
import os
import io
import time
import base64
from typing import List, Dict, Any, Optional, Tuple, Set
import qrcode
from PIL import Image

# 安全防禦性載入 cv2 (防止在無 GUI 的 Linux 雲端環境報錯)
try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except Exception as e:
    cv2 = None
    np = None
    HAS_CV2 = False

from mezastar_data import DATA_DIR

TRAINERS_FILE = os.path.join(DATA_DIR, "trainers.json")
SUPPORT_POKEMON_FILE = os.path.join(DATA_DIR, "support_pokemon.json")

# ==============================================================================
# 🗂️ 官方支援寶可夢完整資料庫 (歷代全系列收錄)
# ==============================================================================
DEFAULT_SUPPORT_POKEMON: List[Dict[str, Any]] = [
    {
        "id": "SP-001",
        "name": "噴火龍 (超級噴火龍X)",
        "types": ["火", "龍"],
        "series": "超級第1彈",
        "skill_name": "超級爆炎衝擊",
        "skill_desc": "給予對手極大火屬性傷害，並使我方全隊特攻提升 2 階",
        "star": 6,
        "qr_data": "MEZASTAR-SP:CHARIZARD-X-001",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/6.png"
    },
    {
        "id": "SP-002",
        "name": "甲賀忍蛙 (小智版甲賀忍蛙)",
        "types": ["水", "惡"],
        "series": "第1彈",
        "skill_name": "黃金水手裡劍",
        "skill_desc": "以極高速度連續攻擊對手，造成大量水屬性傷害並提高我方全體命中率",
        "star": 6,
        "qr_data": "MEZASTAR-SP:GRENINJA-ASH-002",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/658.png"
    },
    {
        "id": "SP-003",
        "name": "路卡利歐 (超級路卡利歐)",
        "types": ["格鬥", "鋼"],
        "series": "第2彈",
        "skill_name": "波導極限爆發",
        "skill_desc": "造成格鬥屬性強大傷害，本回合必定造成會心一擊 (Critical Hit)",
        "star": 6,
        "qr_data": "MEZASTAR-SP:LUCARIO-MEGA-003",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/448.png"
    },
    {
        "id": "SP-004",
        "name": "皮卡丘 (戴著帽子的皮卡丘)",
        "types": ["電"],
        "series": "第1彈",
        "skill_name": "千萬伏特",
        "skill_desc": "超高威力電屬性招式，並讓對手陷入麻痺狀態",
        "star": 6,
        "qr_data": "MEZASTAR-SP:PIKACHU-CAP-004",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/25.png"
    },
    {
        "id": "SP-005",
        "name": "烈空坐 (超級烈空坐)",
        "types": ["龍", "飛行"],
        "series": "超級第2彈",
        "skill_name": "畫龍點睛",
        "skill_desc": "從大氣層俯衝造成毀滅性飛行屬性傷害，全隊攻擊力上升 2 階",
        "star": 6,
        "qr_data": "MEZASTAR-SP:RAYQUAZA-MEGA-005",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/384.png"
    },
    {
        "id": "SP-006",
        "name": "耿鬼 (超極巨化耿鬼)",
        "types": ["幽靈", "毒"],
        "series": "第3彈",
        "skill_name": "超極巨幻影幽魂",
        "skill_desc": "製造巨大黑洞造成幽靈屬性重創，封鎖對手下一次反擊",
        "star": 6,
        "qr_data": "MEZASTAR-SP:GENGAR-GMAX-006",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/94.png"
    },
    {
        "id": "SP-007",
        "name": "達克萊伊",
        "types": ["惡"],
        "series": "第4彈",
        "skill_name": "暗黑洞爆破",
        "skill_desc": "將對手拉入惡夢空間，造成惡屬性重傷害並降低對手防禦力 2 階",
        "star": 6,
        "qr_data": "MEZASTAR-SP:DARKRAI-007",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/491.png"
    },
    {
        "id": "SP-008",
        "name": "蒼響 (劍之王)",
        "types": ["妖精", "鋼"],
        "series": "超級第3彈",
        "skill_name": "巨獸斬",
        "skill_desc": "對極巨化與一般對手均能造成 2 倍斬擊鋼屬性超絕傷害",
        "star": 6,
        "qr_data": "MEZASTAR-SP:ZACIAN-CROWNED-008",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/888.png"
    },
    {
        "id": "SP-009",
        "name": "藏瑪然特 (盾之王)",
        "types": ["格鬥", "鋼"],
        "series": "超級第3彈",
        "skill_name": "巨獸彈",
        "skill_desc": "化為鐵壁衝撞造成極大傷害，並使我方全隊防禦與特防大幅提升",
        "star": 6,
        "qr_data": "MEZASTAR-SP:ZAMAZENTA-CROWNED-009",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/889.png"
    },
    {
        "id": "SP-010",
        "name": "故勒頓 (完全形態)",
        "types": ["格鬥", "龍"],
        "series": "雙重衝刺第1彈",
        "skill_name": "全開猛撞",
        "skill_desc": "古代恐龍狂暴衝擊，造成巨量格鬥屬性傷害並引發強烈陽光",
        "star": 6,
        "qr_data": "MEZASTAR-SP:KORAIDON-APEX-010",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/1007.png"
    },
    {
        "id": "SP-011",
        "name": "密勒頓 (完全形態)",
        "types": ["電", "龍"],
        "series": "雙重衝刺第1彈",
        "skill_name": "閃電驅馳",
        "skill_desc": "未來科技高能閃電撞擊，造成巨量電屬性傷害並展開電氣氣場",
        "star": 6,
        "qr_data": "MEZASTAR-SP:MIRAIDON-ULTIMATE-011",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/1008.png"
    },
    {
        "id": "SP-012",
        "name": "超夢 (超級超夢Y)",
        "types": ["超能力"],
        "series": "超級第4彈",
        "skill_name": "精神擊破",
        "skill_desc": "將強大精神波化為實體重創對手，無視對手的特防提升效果",
        "star": 6,
        "qr_data": "MEZASTAR-SP:MEWTWO-MEGAY-012",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/150.png"
    },
    {
        "id": "SP-013",
        "name": "萊希拉姆",
        "types": ["龍", "火"],
        "series": "雙重衝刺第2彈",
        "skill_name": "交錯火焰",
        "skill_desc": "噴射渦輪烈焰，造成火與龍雙重強烈打擊",
        "star": 6,
        "qr_data": "MEZASTAR-SP:RESHIRAM-013",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/643.png"
    },
    {
        "id": "SP-014",
        "name": "捷克羅姆",
        "types": ["龍", "電"],
        "series": "雙重衝刺第2彈",
        "skill_name": "交錯閃電",
        "skill_desc": "釋放高壓雷電反衝重擊對手",
        "star": 6,
        "qr_data": "MEZASTAR-SP:ZEKROM-014",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/644.png"
    },
    {
        "id": "SP-015",
        "name": "基格爾德 (100%完全體)",
        "types": ["龍", "地面"],
        "series": "雙重衝刺第3彈",
        "skill_name": "核心懲罰者",
        "skill_desc": "在地面刻劃巨大 Z 字射線，造成毀滅性龍屬性打擊",
        "star": 6,
        "qr_data": "MEZASTAR-SP:ZYGARDE-COMPLETE-015",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/718.png"
    },
    {
        "id": "SP-016",
        "name": "夢幻",
        "types": ["超能力"],
        "series": "官方限定活動",
        "skill_name": "起源超新星",
        "skill_desc": "召喚宇宙原初能量造成廣域超能力傷害，並恢復我方全體血量",
        "star": 6,
        "qr_data": "MEZASTAR-SP:MEW-EVENT-016",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/151.png"
    },
    {
        "id": "SP-017",
        "name": "拉帝亞斯 & 拉帝歐斯",
        "types": ["龍", "超能力"],
        "series": "雙重衝刺第4彈",
        "skill_name": "雙重光子爆裂",
        "skill_desc": "兄妹雙重高速合體射線衝擊，大幅降低對手特防",
        "star": 6,
        "qr_data": "MEZASTAR-SP:LATIOS-LATIAS-017",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/380.png"
    },
    {
        "id": "SP-018",
        "name": "急凍鳥 / 閃電鳥 / 火焰鳥 (伽勒爾之姿)",
        "types": ["超能力", "格鬥", "惡"],
        "series": "雙重衝刺第5彈",
        "skill_name": "三鳥極限狂瀾",
        "skill_desc": "三大傳說鳥寶可夢連攜必殺，隨機造成雙倍弱點傷害",
        "star": 6,
        "qr_data": "MEZASTAR-SP:GALAR-BIRDS-018",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/144.png"
    },
    {
        "id": "SP-019",
        "name": "烈咬陸鯊 (超級烈咬陸鯊)",
        "types": ["龍", "地面"],
        "series": "GS第1彈",
        "skill_name": "大地狂怒破壞",
        "skill_desc": "引發劇烈地震重創對手，地面屬性威力極大",
        "star": 6,
        "qr_data": "MEZASTAR-SP:GARCHOMP-MEGA-019",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/445.png"
    },
    {
        "id": "SP-020",
        "name": "班基拉斯 (超級班基拉斯)",
        "types": ["岩石", "惡"],
        "series": "GS第1彈",
        "skill_name": "沙暴巨岩崩塌",
        "skill_desc": "引發漫天沙暴重擊對手，並大幅強化自身防禦力",
        "star": 6,
        "qr_data": "MEZASTAR-SP:TYRANITAR-MEGA-020",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/248.png"
    }
]

# ==============================================================================
# 🔍 QR Code 生成與解碼 (高精度適配 Mezastar 機台)
# ==============================================================================

def generate_qr_image(data_text: str, box_size: int = 12, border: int = 2) -> Image.Image:
    """
    生成高清晰度、高對比度的 QR Code 圖片，最適配 Mezastar 機台鏡頭掃描。
    :param data_text: QR Code 字串內容
    :param box_size: 像素點大小 (預設 12，保證高解析度)
    :param border: 白邊寬度
    :return: PIL.Image 物件
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img

def generate_qr_base64(data_text: str, box_size: int = 12) -> str:
    """生成 QR Code 的 Base64 Data URL (供 Web / HTML 直接顯示)"""
    img = generate_qr_image(data_text, box_size=box_size)
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{img_str}"

def generate_qr_bytes(data_text: str, box_size: int = 12) -> bytes:
    """生成 QR Code 的 PNG 原始 Bytes"""
    img = generate_qr_image(data_text, box_size=box_size)
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return buffered.getvalue()

def decode_qr_from_bytes(image_bytes: bytes) -> Tuple[bool, str, str]:
    """
    從圖片二進位數據 (PNG/JPG/WEBP 等) 中自動辨識與解碼 QR Code。
    採用多重影像增強算法 (灰階、對比增強、自適應二值化)，即使手機拍照反光或模糊也能精準解碼。
    :return: (是否成功, 解碼出的內容字串, 提示訊息)
    """
    if not HAS_CV2 or cv2 is None or np is None:
        return False, "", "目前環境未啟用 OpenCV 影像辨識，請直接手動輸入訓練家 ID！"

    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return False, "", "無法解析此圖片檔案格式"

        detector = cv2.QRCodeDetector()

        # 策略 1: 直接原圖辨識
        val, pts, _ = detector.detectAndDecode(img)
        if val and val.strip():
            return True, val.strip(), "成功識別 QR Code！"

        # 策略 2: 轉為灰階 + 直方圖均衡化
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        val, pts, _ = detector.detectAndDecode(gray)
        if val and val.strip():
            return True, val.strip(), "成功識別 QR Code！"

        # 策略 3: 自適應二值化 (去除反光與陰影)
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, 10
        )
        val, pts, _ = detector.detectAndDecode(thresh)
        if val and val.strip():
            return True, val.strip(), "成功識別 QR Code (經濾鏡優化)！"

        # 策略 4: 縮放嘗試 (若圖片過大或過小)
        for scale in [0.5, 1.5, 2.0]:
            resized = cv2.resize(gray, (0, 0), fx=scale, fy=scale)
            val, pts, _ = detector.detectAndDecode(resized)
            if val and val.strip():
                return True, val.strip(), f"成功識別 QR Code (縮放 {scale}x)！"

        return False, "", "未能在此圖片中偵測到有效的 QR Code，請確認圖片清晰度或直接手動輸入代碼！"
    except Exception as e:
        return False, "", f"辨識過程發生異常: {str(e)}"

# ==============================================================================
# 👑 訓練家 ID 庫 (Trainers Manager)
# ==============================================================================

def load_trainers() -> List[Dict[str, Any]]:
    """載入所有已儲存的訓練家清單"""
    if os.path.exists(TRAINERS_FILE):
        try:
            with open(TRAINERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"Error loading trainers: {e}")
    # 預設範例訓練家
    default_trainers = [
        {
            "id": "MZ-TR-8888-001",
            "name": "主要訓練家 (Master)",
            "created_at": "2026-01-01 12:00:00",
            "notes": "主力對戰帳號，已累積 50+ 六星卡",
            "avatar_color": "#FF5722",
            "is_active": True
        },
        {
            "id": "MZ-TR-9999-002",
            "name": "副帳號 (小號)",
            "created_at": "2026-02-15 15:30:00",
            "notes": "活動與替補專用",
            "avatar_color": "#2196F3",
            "is_active": False
        }
    ]
    save_trainers(default_trainers)
    return default_trainers

def save_trainers(trainers: List[Dict[str, Any]]) -> bool:
    """儲存訓練家清單至持久化 JSON 檔案"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(TRAINERS_FILE, "w", encoding="utf-8") as f:
            json.dump(trainers, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving trainers: {e}")
        return False

def add_trainer(qr_id: str, name: str, notes: str = "", avatar_color: str = "#4CAF50") -> Tuple[bool, str, List[Dict[str, Any]]]:
    """新增一組訓練家"""
    clean_id = qr_id.strip()
    clean_name = name.strip()
    if not clean_id:
        return False, "訓練家 QR Code / ID 不得為空！", []
    if not clean_name:
        clean_name = f"訓練家 {clean_id[:8]}"

    trainers = load_trainers()
    for t in trainers:
        if t.get("id") == clean_id:
            # 若已存在則更新名稱
            t["name"] = clean_name
            t["notes"] = notes
            t["avatar_color"] = avatar_color
            save_trainers(trainers)
            return True, f"訓練家 [{clean_name}] 資料已成功更新！", trainers

    new_trainer = {
        "id": clean_id,
        "name": clean_name,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "notes": notes,
        "avatar_color": avatar_color,
        "is_active": len(trainers) == 0
    }
    trainers.append(new_trainer)
    save_trainers(trainers)
    return True, f"成功新增訓練家 [{clean_name}]！", trainers

def delete_trainer(qr_id: str) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """刪除特定訓練家"""
    trainers = load_trainers()
    original_count = len(trainers)
    trainers = [t for t in trainers if t.get("id") != qr_id]
    if len(trainers) < original_count:
        if trainers and not any(t.get("is_active") for t in trainers):
            trainers[0]["is_active"] = True
        save_trainers(trainers)
        return True, "已成功刪除訓練家！", trainers
    return False, "找不到欲刪除的訓練家！", trainers

def set_active_trainer(qr_id: str) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """將特定訓練家設為目前預設/使用中"""
    trainers = load_trainers()
    found = False
    for t in trainers:
        if t.get("id") == qr_id:
            t["is_active"] = True
            found = True
        else:
            t["is_active"] = False
    if found:
        save_trainers(trainers)
        return True, "已成功切換目前訓練家！", trainers
    return False, "找不到指定訓練家！", trainers

# ==============================================================================
# 🤝 支援寶可夢資料庫 (Support Pokemon Manager)
# ==============================================================================

def load_support_pokemon() -> List[Dict[str, Any]]:
    """載入所有支援寶可夢資料"""
    if os.path.exists(SUPPORT_POKEMON_FILE):
        try:
            with open(SUPPORT_POKEMON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception as e:
            print(f"Error loading support pokemon: {e}")
    # 初次載入預設支援寶可夢資料庫並存檔
    save_support_pokemon(DEFAULT_SUPPORT_POKEMON)
    return DEFAULT_SUPPORT_POKEMON

def save_support_pokemon(support_list: List[Dict[str, Any]]) -> bool:
    """儲存支援寶可夢資料庫至檔案"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SUPPORT_POKEMON_FILE, "w", encoding="utf-8") as f:
            json.dump(support_list, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving support pokemon: {e}")
        return False
