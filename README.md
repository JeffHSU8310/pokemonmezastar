# ⚡ 寶可夢 Mezastar 智慧對戰推薦系統與雲端卡匣庫 (Pokemon Mezastar Battle Optimizer)

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/)
[![CI Verification](https://github.com/JeffHSU8310/pokemonmezastar/actions/workflows/deploy.yml/badge.svg)](https://github.com/JeffHSU8310/pokemonmezastar/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

專為《寶可夢 Mezastar (Pokémon MEZASTAR)》設計的**智慧對戰陣容推薦引擎、個人雲端卡匣管理平台與自動資料抓取系統**。

---

## 🌟 核心特色

1. **🎯 智慧相剋與傷害最佳化演算法 (Recommender Engine)**
   - 完整計算 18 種屬性相剋倍率（含雙屬性 4x 極限弱點、抵抗與無效）。
   - 支援 Mezastar 特殊機制加乘：**極巨化 (Dynamax)、超級進化 (Mega Evolution)、Z招式 (Z-Move)、太晶化 (Terastal)、雙重衝刺 (Double Rush)**。
   - 計算本系招式一致加成 (STAB) 與攻防綜合能力，自動推薦傷害最高、防守最穩的 TOP 3 出戰隊伍與出招戰術！

2. **🎒 個人卡匣庫雲端管理 (My Collection)**
   - 一鍵勾選/標記您實際持有的實體卡匣。
   - 支援按彈別（第1~4彈、超級彈、雙重衝刺、GS/太晶彈等）、星級（6⭐、5⭐）、屬性進行精準篩選。
   - 陣容推薦可直接指定「只從我的收藏中挑選」，完美匹配您手中的卡匣！

3. **🌐 網路資料抓取與擴充 (Web Scraper & PokeAPI)**
   - 支援聯網查詢寶可夢官方資料庫 (PokeAPI)，自動取得屬性、各項能力值與官方立繪圖片。
   - 支援隨時自訂與擴充最新彈別卡匣資料。

4. **🔄 本機與 GitHub 自動版本記錄與同步 (Git Auto-Sync)**
   - 每次修改資料或更新卡匣，自動記錄新版次 (Semantic Versioning) 與變更說明。
   - 支援在網頁上一鍵或透過腳本自動 commit 並同步回併到 GitHub `main` 分支。

5. **☁️ 免費雲端部署 (隨開即用)**
   - 支援直接透過 **Streamlit Community Cloud** 免費部署，手機、平板、電腦打開瀏覽器即可使用。

---

## 🚀 快速開始

### 1. 本機運行

```bash
# 1. 複製專案庫
git clone https://github.com/JeffHSU8310/pokemonmezastar.git
cd pokemonmezastar

# 2. 安裝依賴套件
pip install -r requirements.txt

# 3. 啟動網頁應用程式
streamlit run app.py
```

瀏覽器將自動開啟 `http://localhost:8501`。

---

### 2. ☁️ 雲端免費部署 (手機隨開即用)

1. 登入 [Streamlit Community Cloud](https://share.streamlit.io/)（以 GitHub 帳號登入）。
2. 點選 **「New app」**。
3. 設定：
   - **Repository**: `JeffHSU8310/pokemonmezastar`
   - **Branch**: `main`
   - **Main file path**: `app.py`
4. 點選 **「Deploy!」**，幾秒內即可獲得專屬網址，隨時隨地用手機遊玩與查卡！

---

## 📁 專案架構

```
pokemonmezastar/
├── .github/
│   └── workflows/
│       └── deploy.yml          # GitHub Actions 自動測試工作流
├── .streamlit/
│   └── config.toml             # Streamlit 主題與風格配置
├── data/
│   ├── mezastar_cards.json     # 卡匣資料庫儲存檔
│   └── my_collection.json      # 個人收藏卡匣儲存檔
├── app.py                      # Streamlit 網頁主程式 (UI 介面)
├── mezastar_data.py            # 18 屬性相剋矩陣與核心卡匣資料
├── recommender.py              # 智慧對戰陣容推薦核心演算法
├── collection_manager.py       # 個人收藏庫管理模組
├── scraper.py                  # 網路資料抓取與 PokeAPI 連線模組
├── github_sync.py              # GitHub 自動同步與版本控制模組
├── sync_and_push.ps1           # PowerShell 一鍵同步腳本
├── sync_and_push.bat           # Windows CMD 一鍵同步腳本
├── test_mezastar.py            # 單元測試程式
├── version.json                # 版本號與歷史修改紀錄
├── requirements.txt            # Python 依賴清單
└── README.md                   # 專案說明文件
```

---

## 🧪 執行測試

```bash
python -m unittest test_mezastar.py
```

---

## 📜 授權

本專案採用 MIT 授權條款。寶可夢相關商標與圖案版權屬於 Nintendo / Creatures Inc. / GAME FREAK inc. / Takara Tomy Arts。
