# 專案開發與維護核心規則 (Project Core Rules)

## 🚨 鐵律規範 (Ironclad Rules)

### 1. 雲端同步功能絕對保護原則 (Cloud Sync Protected Area)
- **【核心鐵則】**：**雲端同步頁籤內之所有功能**，包括：
  1. 下載備份 (Download JSON Backup)
  2. 還原卡匣庫與訓練家資料 (Restore Collection & Trainer Data)
  3. GitHub REST API 雲端直接推送與雙向同步 (Cloud Direct Push)
  4. 本機資料恢復與 Token 授權管理功能
- **【最高限制】**：**完全維持原狀，完全不准任意更動、修改、替換、簡化或重構**，除非使用者親自下達明確修改該功能的指令。

### 2. 使用者個人資料保護原則 (User Data Integrity)
- 以下檔案在進行圖鑑更新或系統調校時，**絕對禁止覆蓋、清空或破壞**：
  - `data/my_collection.json`（使用者個人擁有的實體卡匣清單）
  - `data/trainers.json`（使用者個人已建立與掃描的訓練家 ID 與 QR Code）
  - `data/support_pokemon.json`（支援寶可夢專屬技能庫）
  - `github_sync.py`（雲端同步核心模組）

### 3. 圖鑑資料庫擴充隔離原則 (Pokedex Data Isolation)
- 更新官方卡匣圖鑑、新增彈別或擴充中英雙語資料時，**僅限於更新 `data/mezastar_cards.json`、`data_generator.py` 與 `mezastar_data.py`**。
- 圖鑑更新程序嚴禁觸碰或重設使用者的收藏狀態與雲端同步程式。

### 4. 台版與國際版雙官方網站同步比對原則 (Dual Official & International Sync Rule)
- **【雙來源比對規則】**：未來凡有新增卡匣圖鑑或推出新彈別時：
  1. 除了讀取 **台灣官方網站 (pokemonmezastar.com.tw)** 資料外，**必須同時連線國際版官方網站 (world.pokemonmezastar.com/sg/tag/)** 讀取最新資料。
  2. 必須進行雙向跨來源資料交叉比對（包含：卡匣編號、中文名稱、英文官方學名、星級、寶可能量、招式威力、六維體質、常規卡匣 R 系列與特殊機制）。
  3. 確認台版與國際版數據精確無誤且無遺漏後，方可正式納入系統圖鑑庫。

### 5. 版本追蹤與雙向同步原則 (Git & Cloud Sync)
- 每次依使用者需求修改完畢並通過單元測試後，必須自動同步更新至本機磁碟與 GitHub `main` 分支。
