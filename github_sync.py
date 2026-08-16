"""
GitHub Auto-Sync & Versioning Module for Pokemon Mezastar
Handles local disk auto-commit, version incrementing, and pushing/merging to GitHub main.
"""

from typing import Dict, List, Any, Optional, Tuple
import os
import subprocess
import json
from datetime import datetime

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
        "version": "1.0.0",
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "history": [
            {
                "version": "1.0.0",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message": "系統初始化與初版發布"
            }
        ]
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

def save_version_info(ver_data: Dict[str, Any]) -> bool:
    """儲存版本與紀錄"""
    try:
        with open(VERSION_FILE, "w", encoding="utf-8") as f:
            json.dump(ver_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving version file: {e}")
        return False

def run_git_cmd(args: List[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
    """執行 Git 指令"""
    if cwd is None:
        cwd = os.path.dirname(os.path.abspath(__file__))
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return -1, "", str(e)

def get_git_status() -> Dict[str, Any]:
    """獲取 Git 當前分支、狀態與未提交變更"""
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    code, stdout, stderr = run_git_cmd(["status", "--porcelain"], repo_dir)
    changed_files = [line.strip() for line in stdout.splitlines() if line.strip()] if code == 0 else []

    _, branch, _ = run_git_cmd(["branch", "--show-current"], repo_dir)
    _, commit_id, _ = run_git_cmd(["rev-parse", "--short", "HEAD"], repo_dir)
    _, remote_url, _ = run_git_cmd(["remote", "get-url", "origin"], repo_dir)

    ver_info = load_version_info()

    return {
        "is_git": code == 0,
        "branch": branch or "main",
        "commit": commit_id or "Initial",
        "remote_url": remote_url or "https://github.com/JeffHSU8310/pokemonmezastar.git",
        "changed_files": changed_files,
        "has_changes": len(changed_files) > 0,
        "version": ver_info.get("version", "1.0.0"),
        "last_updated": ver_info.get("last_updated", "")
    }

def auto_commit_and_push(change_summary: str = "自動更新卡匣與系統資料", branch: str = "main") -> Tuple[bool, str]:
    """
    自動記錄版次、Commit、並同步推送到 GitHub main 分支
    """
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. 遞增版次
    ver_info = load_version_info()
    new_ver = increment_version(ver_info.get("version", "1.0.0"), "patch")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ver_info["version"] = new_ver
    ver_info["last_updated"] = now_str
    if "history" not in ver_info:
        ver_info["history"] = []
    ver_info["history"].insert(0, {
        "version": new_ver,
        "timestamp": now_str,
        "message": change_summary
    })
    save_version_info(ver_info)

    # 2. Git Add
    code, out, err = run_git_cmd(["add", "-A"], repo_dir)
    if code != 0:
        return False, f"Git Add 失敗: {err}"

    # 3. Git Commit
    commit_msg = f"[v{new_ver}] {now_str} - {change_summary}"
    code, out, err = run_git_cmd(["commit", "-m", commit_msg], repo_dir)
    # 如果沒有檔案變更但版次更新，也視為已完成
    if code != 0 and "nothing to commit" not in (out + err):
        return False, f"Git Commit 失敗: {err}"

    # 4. Git Push
    # 先確保 branch 設為 main
    run_git_cmd(["branch", "-M", branch], repo_dir)
    
    # 嘗試 Push
    code, out, err = run_git_cmd(["push", "-u", "origin", branch], repo_dir)
    if code != 0:
        # 如果因為 remote 有新 commit，嘗試 pull rebase 後再 push
        pull_code, _, _ = run_git_cmd(["pull", "--rebase", "origin", branch], repo_dir)
        if pull_code == 0:
            code, out, err = run_git_cmd(["push", "-u", "origin", branch], repo_dir)

    if code == 0:
        return True, f"✅ 成功記錄版次 v{new_ver} 並自動同步推送至 GitHub ({branch}) 分支！"
    else:
        # 即使 GitHub Push 需要授權，本地也已完成 Commit 與版本記錄
        return True, f"💾 本地已成功記錄版次 v{new_ver} 並完成 Commit！(遠端推送提示: {err or out}，若為首次推送請確認 GitHub 憑證授權)"
