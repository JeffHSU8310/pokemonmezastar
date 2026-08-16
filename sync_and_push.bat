@echo off
chcp 65001 > nul
echo ==========================================
echo   Pokemon Mezastar GitHub 自動同步工具
echo ==========================================

python -c "import sys; from github_sync import auto_commit_and_push; ok, msg = auto_commit_and_push('更新寶可夢 Mezastar 卡匣與對戰設定'); print(msg); sys.exit(0 if ok else 1)"

pause
