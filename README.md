# ⚡ 寶可夢 Mezastar 智慧對戰推薦系統與雲端卡匣庫 (Pokemon Mezastar Battle Optimizer)

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/)
[![CI Verification](https://github.com/JeffHSU8310/pokemonmezastar/actions/workflows/deploy.yml/badge.svg)](https://github.com/JeffHSU8310/pokemonmezastar/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

專為《寶可夢 Mezastar (Pokémon MEZASTAR)》設計的**智慧對戰陣容推薦引擎、個人雲端卡匣管理平台與自動資料抓取系統**。

### 📷 手機相機卡匣辨識

- 在「⚔️ 陣容推薦」展開相機功能，點一次「開啟相機」並允許權限，即可持續使用同一個預覽視窗。
- 先在預覽視窗對準卡匣，再按「掃描目前畫面」才會執行辨識；不會在背景自動重複掃描。
- 辨識完成後相機保持開啟，可直接對準下一張卡匣再次掃描，或手動按「關閉相機」。
- 相機會要求連續自動對焦，按下掃描時從最近約一秒影格中挑選最清楚的一張；模糊、太暗或過曝會提示重試。
- 手機預覽採用不經伺服器回傳壓縮的低延遲模式，顯示框限制在 340×255px 內；辨識仍使用相機原始高解析度影格。
- 最近影格取樣提升至每秒約 12 張；OCR 或星數有可信線索時會縮小卡面比對範圍，加快首次掃描。
- 系統會在本機綜合 OCR 文字／編號、星數與卡面圖案，列出最接近的三張卡匣。
- 點選正確候選後會記住不可還原成照片的卡面特徵；下次遇到相似畫面會提高正確卡匣排名。
- 如果前三個都不正確，可手動搜尋正確卡匣並回饋學習，再自動套用 Boss 與產生最佳 Top 3 陣容。
- 建議讓卡匣正面填滿畫面、保持對焦並避開燈光反射；低信心結果必須人工確認。

---

## 🌟 核心特色

1. **🎯 智慧相剋與傷害最佳化演算法 (Recommender Engine)**
   - 完整計算 18 種屬性相剋倍率（含雙屬性 4x 極限弱點、抵抗與無效）。
   - 支援 Mezastar 特殊機制加乘：**極巨化 (Dynamax)、超級進化 (Mega Evolution)、Z招式 (Z-Move)、太晶化 (Terastal)、雙重衝刺 (Double Rush)**。
   - 計算本系招式一致加成 (STAB) 與攻防綜合能力，自動推薦傷害最高、防守最穩的 TOP 3 出戰隊伍與出招戰術！
   - 先以 Boss 的 2 倍／4 倍相剋弱點招式決定出戰候選，再於相同剋制層級比較期望傷害、生存、命中、速度與特殊機制。
   - 擊退回合以三張卡每輪各攻擊一次的合計期望傷害估算，不再用單張卡推論整場戰鬥。
   - Streamlit 熱部署會主動重載推薦、辨識與相機模組，避免新版畫面沿用伺服器記憶體中的舊公式。
   - 可回報實戰勝敗與最佳表現卡匣；系統會針對相同 Boss 屬性學習卡匣及搭配效果，並以保守上限調整後續推薦。

2. **🎒 個人卡匣庫雲端管理 (My Collection)**
   - 一鍵勾選/標記您實際持有的實體卡匣。
   - 支援按彈別（第1~4彈、超級彈、雙重衝刺、GS/太晶彈等）、星級（6⭐、5⭐）、屬性進行精準篩選。
   - 陣容推薦可直接指定「只從我的收藏中挑選」，完美匹配您手中的卡匣！

3. **🌐 網路資料抓取與擴充 (Web Scraper & PokeAPI)**
   - 支援聯網查詢寶可夢官方資料庫 (PokeAPI)，自動取得屬性、各項能力值與官方立繪圖片。
   - 每 12 小時自動交叉比對台灣與國際版 Mezastar 官方網站；只有雙方同卡號確認的新卡才會加入。
   - 採嚴格 append-only 寫入：既有卡號、內容及順序永遠不覆寫，單一來源新卡會留待下次確認。

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
├── recommendation_learning.py  # 推薦勝敗回饋與保守權重學習
├── camera_recognizer.py        # 相機 OCR、星數與卡面影像混合辨識
├── collection_manager.py       # 個人收藏庫管理模組
├── scraper.py                  # 雙官方來源、append-only 更新與 PokeAPI 模組
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
