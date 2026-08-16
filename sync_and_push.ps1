# Pokemon Mezastar 自動版次記錄與同步推送到 GitHub 工具
Param(
    [string]$Message = "更新寶可夢 Mezastar 卡匣與對戰設定"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Pokemon Mezastar GitHub 自動同步工具   " -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan

python -c "import sys; from github_sync import auto_commit_and_push; ok, msg = auto_commit_and_push('$Message'); print(msg); sys.exit(0 if ok else 1)"

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ 同步完成！" -ForegroundColor Green
} else {
    Write-Host "`n⚠️ 同步過程中遇到問題，請確認網路連線或 Git 設定。" -ForegroundColor Red
}
