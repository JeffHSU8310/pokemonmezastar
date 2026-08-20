"""
GitHub Auto-Sync & Direct REST API Synchronization Engine
支援透過 GitHub REST API 直接將個人卡庫 (my_collection.json) 與 訓練家 ID (trainers.json)
免依賴 git 指令，100% 穩定寫入 GitHub main 分支，實現換電腦、重開伺服器永久保存！
"""

import os
import json
import base64
import hashlib
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

def save_version_info(version_info: Dict[str, Any]) -> bool:
    """安全寫入版本資訊。"""
    try:
        with open(VERSION_FILE, "w", encoding="utf-8") as f:
            json.dump(version_info, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving version file: {e}")
        return False

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

API_ROOT = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
SYNC_PATHS = ("data/my_collection.json", "data/trainers.json")

def _github_headers(token: Optional[str] = None, no_cache: bool = False) -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "PokemonMezastar-SyncBot"
    }
    if token and token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"
    if no_cache:
        headers.update({
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        })
    return headers

def _response_error(response: requests.Response) -> str:
    try:
        return str(response.json().get("message", response.text))
    except Exception:
        return response.text or f"HTTP {response.status_code}"

def _git_blob_sha(content: str) -> str:
    raw = content.encode("utf-8")
    return hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()

def _get_branch_head(token: Optional[str] = None) -> Tuple[bool, str, str]:
    try:
        response = requests.get(
            f"{API_ROOT}/git/ref/heads/{BRANCH}",
            params={"_nocache": int(time.time() * 1000)},
            headers=_github_headers(token, no_cache=True),
            timeout=15
        )
        if response.status_code == 200:
            sha = response.json().get("object", {}).get("sha", "")
            if sha:
                return True, sha, ""
        return False, "", f"無法取得 GitHub {BRANCH} 最新 commit：{_response_error(response)}"
    except Exception as e:
        return False, "", f"連線 GitHub 失敗：{e}"

def _pull_file_at_ref(file_rel_path: str, ref: str, token: Optional[str] = None) -> Tuple[bool, str, str, str]:
    """從指定 commit 下載檔案，並驗證內容與 Git blob SHA。"""
    try:
        response = requests.get(
            f"{API_ROOT}/contents/{file_rel_path}",
            params={"ref": ref, "_nocache": int(time.time() * 1000)},
            headers=_github_headers(token, no_cache=True),
            timeout=15
        )
        if response.status_code != 200:
            return False, "", "", f"下載 {file_rel_path} 失敗：{_response_error(response)}"
        payload = response.json()
        encoded = str(payload.get("content", "")).replace("\n", "")
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        remote_sha = str(payload.get("sha", ""))
        if not remote_sha or remote_sha != _git_blob_sha(decoded):
            return False, "", "", f"{file_rel_path} SHA 完整性驗證失敗"
        return True, decoded, remote_sha, ""
    except Exception as e:
        return False, "", "", f"下載 {file_rel_path} 異常：{e}"

def _commit_files_atomically(files: Dict[str, str], commit_message: str, token: str, max_attempts: int = 3) -> Tuple[bool, str, str]:
    """用單一 Git commit 原子更新多檔，並從該 commit 逐檔讀回驗證。"""
    if not token or not token.strip():
        return False, "", "未提供 GitHub Token"
    headers = _github_headers(token)

    for attempt in range(1, max_attempts + 1):
        ok, parent_sha, error = _get_branch_head(token)
        if not ok:
            return False, "", error
        try:
            commit_res = requests.get(f"{API_ROOT}/git/commits/{parent_sha}", headers=headers, timeout=15)
            if commit_res.status_code != 200:
                return False, "", f"讀取基準 commit 失敗：{_response_error(commit_res)}"
            base_tree = commit_res.json().get("tree", {}).get("sha", "")
            entries = []
            expected_shas: Dict[str, str] = {}
            for path, content in files.items():
                blob_res = requests.post(
                    f"{API_ROOT}/git/blobs", headers=headers,
                    json={"content": content, "encoding": "utf-8"}, timeout=15
                )
                if blob_res.status_code != 201:
                    return False, "", f"建立 {path} blob 失敗：{_response_error(blob_res)}"
                blob_sha = str(blob_res.json().get("sha", ""))
                expected_sha = _git_blob_sha(content)
                if blob_sha != expected_sha:
                    return False, "", f"{path} 上傳 SHA 驗證失敗"
                expected_shas[path] = expected_sha
                entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob_sha})

            tree_res = requests.post(
                f"{API_ROOT}/git/trees", headers=headers,
                json={"base_tree": base_tree, "tree": entries}, timeout=15
            )
            if tree_res.status_code != 201:
                return False, "", f"建立同步 tree 失敗：{_response_error(tree_res)}"
            new_commit_res = requests.post(
                f"{API_ROOT}/git/commits", headers=headers,
                json={"message": commit_message, "tree": tree_res.json().get("sha"), "parents": [parent_sha]},
                timeout=15
            )
            if new_commit_res.status_code != 201:
                return False, "", f"建立同步 commit 失敗：{_response_error(new_commit_res)}"
            new_commit_sha = str(new_commit_res.json().get("sha", ""))
            ref_res = requests.patch(
                f"{API_ROOT}/git/refs/heads/{BRANCH}", headers=headers,
                json={"sha": new_commit_sha, "force": False}, timeout=15
            )
            if ref_res.status_code != 200:
                if ref_res.status_code in (409, 422) and attempt < max_attempts:
                    continue
                return False, "", f"更新 {BRANCH} 失敗：{_response_error(ref_res)}"

            for path, expected_content in files.items():
                pulled, actual_content, actual_sha, pull_error = _pull_file_at_ref(path, new_commit_sha, token)
                if not pulled:
                    return False, "", f"提交成功但讀回失敗：{pull_error}"
                if actual_content != expected_content or actual_sha != expected_shas[path]:
                    return False, "", f"提交成功但 {path} 讀回內容不一致"
            return True, new_commit_sha, ""
        except Exception as e:
            return False, "", f"GitHub 原子同步異常：{e}"
    return False, "", "遠端資料持續被其他裝置更新，安全重試後仍無法提交"

def push_file_to_github_api(
    file_rel_path: str,
    content_str: str,
    commit_message: str,
    token: str
) -> Tuple[bool, str]:
    """以單一 commit 更新檔案，成功前會從該 commit 讀回驗證。"""
    ok, commit_sha, error = _commit_files_atomically(
        {file_rel_path: content_str}, commit_message, token
    )
    if not ok:
        return False, error
    return True, f"✅ [{file_rel_path}] 已寫入並驗證 GitHub commit {commit_sha[:7]}"

def pull_file_from_github_api(file_rel_path: str, token: Optional[str] = None) -> Tuple[bool, str, str]:
    """先取得 main 最新 commit，再從該 commit 下載並驗證檔案。"""
    use_token = token or get_saved_github_token()
    ok, head_sha, error = _get_branch_head(use_token)
    if not ok:
        return False, "", error
    pulled, content, _, pull_error = _pull_file_at_ref(file_rel_path, head_sha, use_token)
    if not pulled:
        return False, "", pull_error
    return True, content, f"已從最新 commit {head_sha[:7]} 下載並完成 SHA 驗證"

def pull_all_user_data_from_github(token: Optional[str] = None) -> Tuple[bool, str, str, str, str]:
    """從同一個 main commit 下載並驗證收藏及訓練家資料。"""
    use_token = token or get_saved_github_token()
    ok, head_sha, error = _get_branch_head(use_token)
    if not ok:
        return False, "", "", "", error
    pulled_c, collection_content, _, error_c = _pull_file_at_ref(SYNC_PATHS[0], head_sha, use_token)
    if not pulled_c:
        return False, "", "", head_sha, error_c
    pulled_t, trainers_content, _, error_t = _pull_file_at_ref(SYNC_PATHS[1], head_sha, use_token)
    if not pulled_t:
        return False, "", "", head_sha, error_t
    try:
        collection_data = json.loads(collection_content)
        trainers_data = json.loads(trainers_content)
        if not isinstance(collection_data, list) or not all(isinstance(x, (str, int)) for x in collection_data):
            raise ValueError("收藏資料格式不是 ID 清單")
        if not isinstance(trainers_data, list) or not all(isinstance(x, dict) for x in trainers_data):
            raise ValueError("訓練家資料格式不是物件清單")
    except Exception as e:
        return False, "", "", head_sha, f"雲端資料格式驗證失敗：{e}"
    return True, collection_content, trainers_content, head_sha, f"已從 commit {head_sha[:7]} 完整下載並驗證兩份資料"

def restore_user_data_snapshot_locally(
    collection_content: str,
    trainers_content: str
) -> Tuple[bool, set, List[Dict[str, Any]], str]:
    """驗證後原子寫入本機；第二份寫入失敗時回滾第一份。"""
    from collection_manager import load_user_collection_ids, save_user_collection_ids
    from qr_manager import load_trainers, save_trainers

    try:
        collection_data = json.loads(collection_content)
        trainers_data = json.loads(trainers_content)
        if not isinstance(collection_data, list) or not all(isinstance(x, (str, int)) for x in collection_data):
            raise ValueError("收藏資料格式不是 ID 清單")
        if not isinstance(trainers_data, list) or not all(isinstance(x, dict) for x in trainers_data):
            raise ValueError("訓練家資料格式不是物件清單")
        new_ids = {str(item).strip() for item in collection_data}
    except Exception as e:
        return False, set(), [], f"資料格式驗證失敗：{e}"

    previous_ids = load_user_collection_ids()
    previous_trainers = load_trainers()
    if not save_user_collection_ids(new_ids):
        return False, set(), [], "收藏資料寫入本機失敗，原資料未變更"
    if not save_trainers(trainers_data):
        collection_rolled_back = save_user_collection_ids(previous_ids)
        trainers_rolled_back = save_trainers(previous_trainers)
        if collection_rolled_back and trainers_rolled_back:
            return False, set(), [], "訓練家資料寫入失敗，已還原原本資料"
        return False, set(), [], "訓練家資料寫入失敗，且本機回滾未完整完成；請勿關閉頁面並重新下載"
    return True, new_ids, trainers_data, "本機資料已原子寫入"

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
    collection_str = json.dumps(sorted(list(set(owned_ids))), ensure_ascii=False, indent=2)
    trainers_str = json.dumps(trainers, ensure_ascii=False, indent=2)
    ok, commit_sha, error = _commit_files_atomically(
        {SYNC_PATHS[0]: collection_str, SYNC_PATHS[1]: trainers_str},
        f"sync: {summary} (卡匣 {len(owned_ids)} 張 / 訓練家 {len(trainers)} 組) @ {cur_time}",
        token
    )
    if not ok:
        return False, error
    return True, f"✅ 已原子寫入並讀回驗證 GitHub commit {commit_sha[:7]}（卡匣 {len(owned_ids)} 張／訓練家 {len(trainers)} 組）"

def get_git_status() -> Dict[str, Any]:
    """獲取 Git 當前狀態 (相容非 git 環境與 GitHub API)"""
    ver_info = load_version_info()
    ok, commit_sha, error = _get_branch_head(get_saved_github_token())
    return {
        "is_git": True,
        "branch": BRANCH,
        "commit": commit_sha[:7] if ok else "Unavailable",
        "remote_url": f"https://github.com/{REPO_OWNER}/{REPO_NAME}.git",
        "changed_files": [],
        "has_changes": not ok,
        "verified": ok,
        "error": error,
        "version": ver_info.get("version", "2.2.0"),
        "last_updated": ver_info.get("last_updated", "")
    }

def auto_commit_and_push(change_summary: str = "自動更新卡匣與系統資料", branch: str = "main", github_token: Optional[str] = None) -> Tuple[bool, str]:
    """將核心資料以單一 commit 上傳；沒有 Token 時明確回報失敗。"""
    token = github_token or get_saved_github_token()
    if not token:
        return False, "未提供 GitHub Token，沒有執行上傳"

    ver_info = load_version_info()
    new_ver = increment_version(ver_info.get("version", "2.2.0"), "patch")
    now_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    ver_info["version"] = new_ver
    ver_info["last_updated"] = now_str
    ver_info.setdefault("history", []).insert(0, {
        "version": new_ver,
        "timestamp": now_str,
        "message": change_summary
    })

    root = os.path.dirname(os.path.abspath(__file__))
    files: Dict[str, str] = {"version.json": json.dumps(ver_info, ensure_ascii=False, indent=2)}
    for rel_path in ("data/mezastar_cards.json",) + SYNC_PATHS:
        abs_path = os.path.join(root, *rel_path.split("/"))
        if not os.path.exists(abs_path):
            return False, f"找不到必要同步檔案：{rel_path}"
        with open(abs_path, "r", encoding="utf-8") as f:
            files[rel_path] = f.read()

    ok, commit_sha, error = _commit_files_atomically(
        files, f"sync: {change_summary} (v{new_ver})", token
    )
    if not ok:
        return False, error
    if not save_version_info(ver_info):
        return False, f"GitHub commit {commit_sha[:7]} 已完成，但本機版號寫入失敗"
    return True, f"已同步核心資料至 GitHub commit {commit_sha[:7]}，版次 v{new_ver}"

