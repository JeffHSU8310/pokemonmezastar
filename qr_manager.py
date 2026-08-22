import json
import os
import io
import time
import base64
from typing import List, Dict, Any, Optional, Tuple, Set
import qrcode
from PIL import Image
import numpy as np

from mezastar_data import DATA_DIR
from vision_runtime import cv2, opencv_available

HAS_CV2 = opencv_available()

TRAINERS_FILE = os.path.join(DATA_DIR, "trainers.json")
SUPPORT_POKEMON_FILE = os.path.join(DATA_DIR, "support_pokemon.json")

# ==============================================================================
# 🗂️ 台灣官方目前公告的支援寶可夢券
# ==============================================================================
DEFAULT_SUPPORT_POKEMON: List[Dict[str, Any]] = [
    {
        "id": "TW-SP-001", "name": "拉普拉斯", "types": ["水", "冰"],
        "series": "台灣官方支援寶可夢券", "skill_name": "冷凍光束",
        "skill_desc": "掃描官方支援寶可夢券後，有機會在對戰中支援攻擊。",
        "qr_payload_base64": "FmfKZd3aBMqwIUFhUb0Zq1BPS0VNT04wMt0=",
        "ticket_image_url": "https://www.pokemonmezastar.com.tw/uploads/images/9fff641d4a31b139b959689b5504674825b448574af8189e46a43ce28a74d1a9.jpg",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/131.png"
    },
    {
        "id": "TW-SP-002", "name": "暴噬龜", "types": ["水", "岩石"],
        "series": "台灣官方支援寶可夢券", "skill_name": "雙刃頭錘",
        "skill_desc": "掃描官方支援寶可夢券後，有機會在對戰中支援攻擊。",
        "qr_payload_base64": "fsAS0IvGRqR6u2E6DVVe0FBPS0VNT04wMt0=",
        "ticket_image_url": "https://www.pokemonmezastar.com.tw/uploads/images/25715967753f169c2fc5917d501309815d75f0c3a752546aea2708989b0dbea5.png",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/834.png"
    },
    {
        "id": "TW-SP-003", "name": "沙漠蜻蜓", "types": ["地面", "龍"],
        "series": "台灣官方支援寶可夢券", "skill_name": "地震",
        "skill_desc": "掃描官方支援寶可夢券後，有機會在對戰中支援攻擊。",
        "qr_payload_base64": "mGQW/SxEReLdtCxIl9fGxFBPS0VNT04wMt0=",
        "ticket_image_url": "https://www.pokemonmezastar.com.tw/uploads/images/6d9afcaa5df87f0e60db9332cccc78f36d88336c43bf5565b42f81672e2995c2.png",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/330.png"
    },
    {
        "id": "TW-SP-004", "name": "烈咬陸鯊", "types": ["龍", "地面"],
        "series": "台灣官方支援寶可夢券", "skill_name": "地震",
        "skill_desc": "掃描官方支援寶可夢券後，有機會在對戰中支援攻擊。",
        "qr_payload_base64": "G0FNFLBE5wPJioLvly17w1BPS0VNT04wMt0=",
        "ticket_image_url": "https://www.pokemonmezastar.com.tw/uploads/images/0f3ebce4f03e0c8ea2906197038c6f86fc9bcc760cbd230d67189fb2220733d3.png",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/445.png"
    },
    {
        "id": "TW-SP-005", "name": "蔥遊兵", "types": ["格鬥"],
        "series": "台灣官方支援寶可夢券", "skill_name": "流星突擊",
        "skill_desc": "掃描官方支援寶可夢券後，有機會在對戰中支援攻擊。",
        "qr_payload_base64": "dhBJI+YnYnKDEdGaYEl01VBPS0VNT04wMt0=",
        "ticket_image_url": "https://www.pokemonmezastar.com.tw/uploads/images/be5581d0d3c6965b741a5c6a7576b3b4a0b4f21a71f833846d9ded4edfe11db7.jpg",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/865.png"
    },
    {
        "id": "TW-SP-006", "name": "謎擬Q", "types": ["幽靈", "妖精"],
        "series": "台灣官方支援寶可夢券", "skill_name": "暗影爪",
        "skill_desc": "掃描官方支援寶可夢券後，有機會在對戰中支援攻擊。",
        "qr_payload_base64": "zE5szsIGPcuZqmEdv12NbFBPS0VNT04wMt0=",
        "ticket_image_url": "https://www.pokemonmezastar.com.tw/uploads/images/3e770293fcbb4250af4e7b7292a3a363cfbcd69c2fdb8e657a4241ca04dcba51.jpg",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/778.png"
    },
    {
        "id": "TW-SP-007", "name": "鋁鋼龍", "types": ["鋼", "龍"],
        "series": "台灣官方支援寶可夢券", "skill_name": "加農光炮",
        "skill_desc": "掃描官方支援寶可夢券後，有機會在對戰中支援攻擊。",
        "qr_payload_base64": "fWPx0F+Et4ruXhVoga3WD1BPS0VNT04wMt0=",
        "ticket_image_url": "https://www.pokemonmezastar.com.tw/uploads/images/02280fc2188e82d64f2ce0c5df03cef7d9aca9d13c7ea24cd1c20f472214b533.png",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/884.png"
    },
    {
        "id": "TW-SP-008", "name": "鋼鎧鴉", "types": ["飛行", "鋼"],
        "series": "台灣官方支援寶可夢券", "skill_name": "勇鳥猛攻",
        "skill_desc": "掃描官方支援寶可夢券後，有機會在對戰中支援攻擊。",
        "qr_payload_base64": "khfaUOtoL+cnw2RfFeC+rVBPS0VNT04wMt0=",
        "ticket_image_url": "https://www.pokemonmezastar.com.tw/uploads/images/71167ad9ef70befe000d763121afc90606b4ae86170ff870bb9b2c4dde83a2de.png",
        "icon_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/823.png"
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


def generate_support_qr_bytes(payload_base64: str, box_size: int = 12) -> bytes:
    """由官方票券的原始二進位內容產生高對比 QR，不做文字轉碼。"""
    payload = base64.b64decode(payload_base64, validate=True)
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=4,
        mask_pattern=0,
    )
    qr.add_data(payload, optimize=0)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return buffered.getvalue()


def generate_support_qr_base64(payload_base64: str, box_size: int = 12) -> str:
    """產生可直接顯示的官方支援寶可夢 QR Data URL。"""
    encoded = base64.b64encode(generate_support_qr_bytes(payload_base64, box_size)).decode("ascii")
    return f"data:image/png;base64,{encoded}"

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
    """以原子取代方式儲存訓練家資料，避免中途中斷破壞 JSON。"""
    temp_path = f"{TRAINERS_FILE}.tmp.{os.getpid()}.{time.time_ns()}"
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(trainers, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, TRAINERS_FILE)
        return True
    except Exception as e:
        print(f"Error saving trainers: {e}")
        return False
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

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
