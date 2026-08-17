"""
GitHub Auto-Sync & Direct REST API Synchronization Engine
支援透過 GitHub REST API 直接將個人卡庫 (my_collection.json) 與 訓練家 ID (trainers.json)
免依賴 git 指令，100% 穩定寫入 GitHub main 分支，實現換電腦、重開伺服器永久保存！
"""

import os
import json
import base64
import time
import requests
from typing import Dict, List, Any, Optional, Tuple

REPO_OWNER = "JeffHSU8310"
REPO_NAME = "pokemonmezastar"
BRANCH = "main"

VERSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.json")

def load_version_info() -> Dict[str, Any]:
    """讀取當前版本與修改紀錄"""
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading version file: {e}")
    return {
        "version": "2.2.0",
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "history": []
    }

def increment_version(current_ver: str, part: str = "patch") -> str:
    """遞增版本號 (major.minor.patch)"""
    parts = current_ver.split(".")
    if len(parts) != 3:
        parts = ["1", "0", "0"]
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "user_config.json")

def get_saved_github_token() -> str:
    """從本地設定檔、環境變數或 Streamlit secrets.toml 讀取已儲存的 GitHub Token"""
    # 1. 優先從環境變數讀取
    env_tok = os.environ.get("GITHUB_TOKEN", "").strip()
    if env_tok:
        return env_tok
    # 2. 從本機設定檔讀取
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                tok = str(cfg.get("github_token", "")).strip()
                if tok:
                    return tok
        except Exception:
            pass
    # 3. 嘗試讀取 Streamlit secrets.toml
    secrets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit", "secrets.toml")
    if os.path.exists(secrets_path):
        try:
            with open(secrets_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GITHUB_TOKEN"):
                        tok = line.split("=", 1)[-1].strip().strip('"').strip("'")
                        if tok:
                            return tok
        except Exception:
            pass
    return ""

def save_github_token(token: str) -> bool:
    """將 GitHub Token 同時永久儲存至本地設定檔與 .streamlit/secrets.toml"""
    if not token or not token.strip():
        return False
    token = token.strip()
    success = False
    # 1. 存入 data/user_config.json
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        cfg = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                cfg = {}
        cfg["github_token"] = token
        cfg["token_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        success = True
    except Exception as e:
        print(f"Error saving token to config: {e}")
    # 2. 同步存入 .streamlit/secrets.toml（雙重保險）
    try:
        streamlit_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit")
        os.makedirs(streamlit_dir, exist_ok=True)
        secrets_path = os.path.join(streamlit_dir, "secrets.toml")
        existing_lines = []
        if os.path.exists(secrets_path):
            with open(secrets_path, "r", encoding="utf-8") as f:
                existing_lines = [l for l in f.readlines() if not l.strip().startswith("GITHUB_TOKEN")]
        existing_lines.append(f'GITHUB_TOKEN = "{token}"\n')
        with open(secrets_path, "w", encoding="utf-8") as f:
            f.writelines(existing_lines)
        success = True
    except Exception as e:
        print(f"Error saving token to secrets.toml: {e}")
    return success

def clear_saved_github_token() -> bool:
    """清除已儲存的 GitHub Token"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg.pop("github_token", None)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

# ==============================================================================
# 🌐 GitHub REST API 直接讀寫 (Direct Cloud Sync via GitHub API)
# ==============================================================================

def push_file_to_github_api(
    file_rel_path: str,
    content_str: str,
    commit_message: str,
    token: str
) -> Tuple[bool, str]:
    """
    透過 GitHub REST API 直接更新或建立遠端檔案，不受本機 Git 限制。
    :param file_rel_path: 相對於倉庫根目錄的路徑 (如 'data/my_collection.json')
    :param content_str: 欲寫入的字串內容 (JSON/文字)
    :param commit_message: 提交說明
    :param token: GitHub Personal Access Token (PAT)
    :return: (是否成功, 訊息)
    """
    if not token or not token.strip():
        return False, "未提供 GitHub Token，請在 Streamlit Secrets 或介面填入 Token！"

    clean_token = token.strip()
    headers = {
        "Authorization": f"Bearer {clean_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "PokemonMezastar-SyncBot"
    }

    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_rel_path}"

    # 1. 取得遠端現有檔案的 SHA
    sha = None
    try:
        get_res = requests.get(f"{url}?ref={BRANCH}", headers=headers, timeout=10)
        if get_res.status_code == 200:
            sha = get_res.json().get("sha")
    except Exception as e:
        return False, f"連線 GitHub 失敗: {str(e)}"

    # 2. Base64 編碼內容
    encoded_content = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

    payload: Dict[str, Any] = {
        "message": commit_message,
        "content": encoded_content,
        "branch": BRANCH
    }
    if sha:
        payload["sha"] = sha

    # 3. 發送 PUT 請求寫入
    try:
        put_res = requests.put(url, headers=headers, json=payload, timeout=15)
        if put_res.status_code in [200, 201]:
            return True, f"✅ 成功將 [{file_rel_path}] 寫入 GitHub main 分支！"
        else:
            err_msg = put_res.json().get("message", put_res.text)
            return False, f"GitHub API 寫入失敗 ({put_res.status_code}): {err_msg}"
    except Exception as e:
        return False, f"上傳請求異常: {str(e)}"

def pull_file_from_github_api(file_rel_path: str, token: Optional[str] = None) -> Tuple[bool, str, str]:
    """
    透過 GitHub REST API 從遠端 main 分支下載最新檔案內容。
    加入時間戳破除 CDN 快取，確保 100% 抓到 GitHub 雲端最新 commit！
    :return: (是否成功, 檔案內容字串, 訊息)
    """
    use_token = token
    if not use_token or not use_token.strip():
        use_token = get_saved_github_token()

    timestamp = int(time.time() * 1000)
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": f"PokemonMezastar-SyncBot-{timestamp}",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    if use_token and use_token.strip():
        headers["Authorization"] = f"Bearer {use_token.strip()}"

    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_rel_path}?ref={BRANCH}&_nocache={timestamp}"

    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            content_b64 = data.get("content", "")
            decoded = base64.b64decode(content_b64).decode("utf-8")
            return True, decoded, "成功自 GitHub 雲端讀取最新資料！"
        elif res.status_code in [401, 403, 404]:
            if not use_token:
                return False, "", "⚠️ 您的 GitHub 倉庫為 Private (私人倉庫)，請先在上方填入 GitHub Token 並點擊【💾 永久記住 Token】！"
            else:
                return False, "", f"GitHub API 認證失敗 ({res.status_code})，請確認 Token 具備 repo 權限！"
    except Exception as e:
        return False, "", f"連線 GitHub 雲端伺服器失敗: {str(e)}"

    return False, "", "無法從 GitHub 讀取檔案，請確認網路連線與 Token 設定。"

def sync_all_user_data_to_github(
    owned_ids: List[str],
    trainers: List[Dict[str, Any]],
    token: str,
    summary: str = "更新卡匣庫與訓練家資料"
) -> Tuple[bool, str]:
    """
    一鍵將個人卡匣庫 (my_collection.json) 與 訓練家清單 (trainers.json) 一併同步推送到 GitHub！
    """
    if not token or not token.strip():
        return False, "請先提供 GitHub Token"

    cur_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    
    # 1. 寫入 my_collection.json
    collection_str = json.dumps(sorted(list(set(owned_ids))), ensure_ascii=False, indent=2)
    ok1, msg1 = push_file_to_github_api(
        "data/my_collection.json",
        collection_str,
        f"sync: {summary} (卡匣數: {len(owned_ids)}) @ {cur_time}",
        token
    )
    if not ok1:
        return False, f"卡匣庫同步失敗: {msg1}"

    # 2. 寫入 trainers.json
    trainers_str = json.dumps(trainers, ensure_ascii=False, indent=2)
    ok2, msg2 = push_file_to_github_api(
        "data/trainers.json",
        trainers_str,
        f"sync: 更新訓練家清單 (共 {len(trainers)} 組) @ {cur_time}",
        token
    )
    if not ok2:
        return False, f"訓練家同步失敗: {msg2}"

    return True, f"🎉 太棒了！已將您的卡匣庫 ({len(owned_ids)} 張) 與訓練家清單 ({len(trainers)} 組) 真正永久寫入 GitHub main 倉庫！"

def get_git_status() -> Dict[str, Any]:
    """獲取 Git 當前狀態 (相容非 git 環境與 GitHub API)"""
    ver_info = load_version_info()
    return {
        "is_git": True,
        "branch": BRANCH,
        "commit": "Latest",
        "remote_url": f"https://github.com/{REPO_OWNER}/{REPO_NAME}.git",
        "changed_files": [],
        "has_changes": False,
        "version": ver_info.get("version", "2.2.0"),
        "last_updated": ver_info.get("last_updated", "")
    }

def auto_commit_and_push(change_summary: str = "自動更新卡匣與系統資料", branch: str = "main", github_token: Optional[str] = None) -> Tuple[bool, str]:
    """相容舊版 auto_commit_and_push 介面"""
    if github_token:
        # 若有 Token 則透過 API 進行全量同步
        from collection_manager import load_user_collection_ids
        from qr_manager import load_trainers
        owned = list(load_user_collection_ids())
        tr = load_trainers()
        return sync_all_user_data_to_github(owned, tr, github_token, summary=change_summary)
    
    # 本地備份模式
    ver_info = load_version_info()
    new_ver = increment_version(ver_info.get("version", "2.2.0"), "patch")
    now_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    ver_info["version"] = new_ver
    ver_info["last_updated"] = now_str
    save_version_info(ver_info)
    return True, f"已成功記錄版次 v{new_ver} (變更: {change_summary})"

