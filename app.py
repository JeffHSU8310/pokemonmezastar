"""
Pokemon Mezastar Battle Optimizer & Cloud Card Deck System
寶可夢 Mezastar 智慧對戰推薦系統與雲端卡匣庫 (針對 6.1 吋手機直立螢幕深度優化版)
"""

import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Set
import os
import json
import textwrap
import importlib
import github_sync as github_sync_module
import recommender as recommender_module
import camera_recognizer as camera_recognizer_module
import live_scanner as live_scanner_module
from streamlit_webrtc import WebRtcMode, webrtc_streamer

from mezastar_data import (
    TYPES,
    TYPE_COLORS,
    ALL_SERIES_LIST,
    calculate_type_effectiveness,
    get_weaknesses,
    get_full_type_chart_for_defender,
    load_cards,
    save_cards,
    DEFAULT_MEZASTAR_CARDS,
    sort_cards_chronological
)
# Streamlit Cloud 熱部署會重跑 app.py，但 Python 可能保留已匯入的舊模組。
# 主動重載這三個本次會直接影響畫面結果的模組，避免新版 UI 搭配舊版
# 回合公式、辨識池或相機取樣器。相機 key 也會隨版本更新以重建 processor。
recommender_module = importlib.reload(recommender_module)
camera_recognizer_module = importlib.reload(camera_recognizer_module)
live_scanner_module = importlib.reload(live_scanner_module)
recommend_best_lineup = recommender_module.recommend_best_lineup
evaluate_card_performance = recommender_module.evaluate_card_performance
recognize_card = camera_recognizer_module.recognize_card
LiveCardScanner = live_scanner_module.LiveCardScanner
from vision_runtime import opencv_available, opencv_error_message
from recognition_learning import learning_example_count, record_confirmation
from recommendation_learning import recommendation_feedback_count, record_recommendation_feedback
from collection_manager import (
    load_user_collection_ids,
    save_user_collection_ids,
    get_user_cards,
    toggle_card_ownership,
    get_collection_stats,
    export_collection_json,
    export_collection_share_code,
    export_collection_csv,
    import_collection_from_json,
    import_collection_from_share_code
)
from scraper import (
    add_custom_card,
    fetch_online_pokemon_metadata,
    batch_import_cards,
    scheduled_official_update,
)
from github_sync import (
    get_git_status,
    load_version_info,
    sync_all_user_data_to_github,
    get_saved_github_token,
    save_github_token,
    clear_saved_github_token
)
from qr_manager import (
    load_trainers,
    save_trainers,
    add_trainer,
    delete_trainer,
    set_active_trainer,
    load_support_pokemon,
    generate_qr_base64,
    decode_qr_from_bytes
)

# Streamlit Cloud 可能在部署切換時保留舊版模組快取；先重載，再安全取得新版同步 API。
if not all(hasattr(github_sync_module, name) for name in (
    "pull_all_user_data_from_github",
    "restore_user_data_snapshot_locally"
)):
    importlib.invalidate_caches()
    github_sync_module = importlib.reload(github_sync_module)

pull_all_user_data_from_github = getattr(github_sync_module, "pull_all_user_data_from_github", None)
restore_user_data_snapshot_locally = getattr(github_sync_module, "restore_user_data_snapshot_locally", None)

if pull_all_user_data_from_github is None:
    def pull_all_user_data_from_github(token=None):
        return False, "", "", "", "同步模組正在更新，請稍候重新整理頁面"

if restore_user_data_snapshot_locally is None:
    def restore_user_data_snapshot_locally(collection_content, trainers_content):
        return False, set(), [], "同步模組正在更新，請稍候重新整理頁面"

# 設定頁面資訊
st.set_page_config(
    page_title="寶可夢 Mezastar 對戰推薦",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def render_html(html_str: str):
    """安全輸出純 HTML，壓平所有縮排與換行，徹底防止 Streamlit Markdown 解析為程式碼區塊"""
    clean_html = " ".join(line.strip() for line in html_str.splitlines() if line.strip())
    if hasattr(st, "html"):
        st.html(clean_html)
    else:
        st.markdown(clean_html, unsafe_allow_html=True)

# 全域 CSS 樣式
st.markdown("""
<style>
    /* 頁面整體邊距：預留頂部 header + Tab 列空間 */
    .block-container {
        padding-top: 6rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
        max-width: 100% !important;
    }
    
    .mobile-title {
        font-size: 1.45rem;
        font-weight: 800;
        color: #E53935;
        margin-bottom: 0.1rem;
        line-height: 1.2;
    }
    .mobile-subtitle {
        font-size: 0.8rem;
        color: #666;
        margin-bottom: 0.6rem;
    }
    .card-box {
        border-radius: 10px;
        padding: 10px;
        background: #ffffff;
        border: 1.5px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        margin-bottom: 8px;
    }
    .type-badge {
        display: inline-block;
        padding: 2px 6px;
        border-radius: 8px;
        color: white;
        font-weight: bold;
        font-size: 0.75rem;
        margin-right: 2px;
        margin-bottom: 2px;
    }
    .energy-badge {
        background: linear-gradient(135deg, #FF6B6B, #FF8E53);
        color: white;
        font-weight: bold;
        padding: 2px 6px;
        border-radius: 6px;
        font-size: 0.75rem;
    }
    .star-badge {
        color: #FFB300;
        font-weight: bold;
        font-size: 0.95rem;
    }
    .tag-badge {
        display: inline-block;
        padding: 1px 5px;
        border-radius: 5px;
        background-color: #f1f3f5;
        color: #333;
        font-size: 0.7rem;
        margin-right: 2px;
        margin-bottom: 2px;
        border: 1px solid #dee2e6;
    }
    .stat-compact {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 2px;
        font-size: 0.75rem;
        color: #495057;
        background: #f8f9fa;
        padding: 4px 6px;
        border-radius: 6px;
        margin: 4px 0;
    }
    .stButton > button {
        border-radius: 8px !important;
        font-weight: bold !important;
        font-size: 0.82rem !important;
        padding: 0.3rem 0.5rem !important;
        min-height: 38px !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px !important;
        overflow-x: auto !important;
        white-space: nowrap !important;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 6px 10px !important;
        font-size: 0.85rem !important;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 🚀 JS 穿透父層 DOM：強制 fixed 吸頂分頁列 + 回頂部懸浮按鈕
# ==============================================================================
import streamlit.components.v1 as components

components.html("""
<script>
(function() {
    var HEADER_H = 46; // Streamlit header 高度 (px)

    function applyFixedTab(tabEl) {
        tabEl.style.cssText = [
            "position: fixed !important",
            "top: " + HEADER_H + "px !important",
            "left: 0 !important",
            "right: 0 !important",
            "width: 100% !important",
            "z-index: 99998 !important",
            "background: #FFFFFF !important",
            "box-shadow: 0 3px 8px rgba(0,0,0,0.12) !important",
            "padding: 4px 12px !important",
            "box-sizing: border-box !important"
        ].join(";");
    }

    function setupFixedTabs(doc) {
        // Streamlit 的 Tab 清單容器（試多種 selector）
        var selectors = [
            '[data-baseweb="tab-list"]',
            '.stTabs [data-testid="stTabsNav"]',
            '[role="tablist"]'
        ];
        var tabList = null;
        for (var i = 0; i < selectors.length; i++) {
            tabList = doc.querySelector(selectors[i]);
            if (tabList) break;
        }
        if (!tabList) return false;
        applyFixedTab(tabList);
        return true;
    }

    function init() {
        try {
            var parentDoc = window.parent.document;
            var parentWin = window.parent;

            // --- 注入樣式 ---
            var styleId = "meza-fixed-style";
            if (!parentDoc.getElementById(styleId)) {
                var s = parentDoc.createElement("style");
                s.id = styleId;
                s.innerHTML =
                    "#meza-btt{position:fixed!important;bottom:22px!important;right:22px!important;" +
                    "width:46px!important;height:46px!important;border-radius:50%!important;" +
                    "background:#E53935!important;color:#fff!important;display:flex!important;" +
                    "align-items:center!important;justify-content:center!important;" +
                    "font-size:21px!important;box-shadow:0 3px 10px rgba(0,0,0,.3)!important;" +
                    "cursor:pointer!important;z-index:999999!important;border:2px solid #fff!important;" +
                    "transition:transform .2s!important;}" +
                    "#meza-btt:hover{transform:scale(1.12)!important;}";
                parentDoc.head.appendChild(s);
            }

            // --- 回頂部按鈕 ---
            if (!parentDoc.getElementById("meza-btt")) {
                var btn = parentDoc.createElement("div");
                btn.id = "meza-btt";
                btn.title = "回到最頂端";
                btn.innerHTML = "🔝";
                btn.onclick = function() {
                    var main = parentDoc.querySelector('[data-testid="stMain"]') ||
                               parentDoc.querySelector("section.main");
                    if (main) main.scrollTo({top:0, behavior:"smooth"});
                    parentWin.scrollTo({top:0, behavior:"smooth"});
                };
                parentDoc.body.appendChild(btn);
            }

            // --- 強制 fixed 吸頂：立即執行 + 重試機制 ---
            var attempts = 0;
            function tryFix() {
                if (setupFixedTabs(parentDoc)) return; // 成功就停
                if (++attempts < 30) setTimeout(tryFix, 300); // 最多重試 9 秒
            }
            tryFix();

            // --- 每次 Streamlit rerun 後重新執行 ---
            var observer = new MutationObserver(function() { tryFix(); });
            observer.observe(parentDoc.body, {childList: true, subtree: true});

            // --- Header 雙擊回頂部 ---
            var lastTap = 0;
            function onTap() {
                var now = Date.now();
                if (now - lastTap < 400) {
                    var main = parentDoc.querySelector('[data-testid="stMain"]') ||
                               parentDoc.querySelector("section.main");
                    if (main) main.scrollTo({top:0, behavior:"smooth"});
                    parentWin.scrollTo({top:0, behavior:"smooth"});
                }
                lastTap = now;
            }
            var header = parentDoc.querySelector('header[data-testid="stHeader"]');
            if (header) {
                header.addEventListener("dblclick", onTap);
                header.addEventListener("click", onTap);
                header.addEventListener("touchend", onTap);
            }
            parentWin.addEventListener("keydown", function(e) {
                if (e.key === "Home") {
                    var main = parentDoc.querySelector('[data-testid="stMain"]') ||
                               parentDoc.querySelector("section.main");
                    if (main) main.scrollTo({top:0, behavior:"smooth"});
                }
            });

        } catch(e) { console.warn("meza-fix:", e); }
    }

    // 等 parent DOM 就緒
    if (document.readyState === "complete") {
        init();
    } else {
        window.addEventListener("load", init);
    }
    // 也在 iframe 載入後嘗試
    setTimeout(init, 500);
})();
</script>
""", height=0)

def render_type_badge(t_name: str) -> str:
    color = TYPE_COLORS.get(t_name, "#888888")
    return f'<span class="type-badge" style="background-color: {color};">{t_name}</span>'

def render_types_html(types: List[str]) -> str:
    return "".join([render_type_badge(t) for t in types])

# ==============================================================================
# 🚀 每次新 Session 開啟：強制自 GitHub 雲端拉取最新卡匣庫與訓練家資料
# 規則：永遠優先從 GitHub 讀取，不依賴本機磁碟，確保所有裝置永遠同步
# ==============================================================================
if "github_auto_synced" not in st.session_state:
    st.session_state.github_auto_synced = True

    # 三重 Token 讀取機制：磁碟設定 → Streamlit Secrets → 環境變數
    auto_token = get_saved_github_token()
    if not auto_token:
        try:
            auto_token = st.secrets.get("GITHUB_TOKEN", "")
        except Exception:
            pass
    if not auto_token:
        auto_token = os.environ.get("GITHUB_TOKEN", "")

    # 記入 session state 備用
    if auto_token:
        st.session_state["github_token"] = auto_token

    github_loaded = False
    try:
        # 從同一個 GitHub commit 拉取並驗證卡匣庫與訓練家資料
        sync_ok, content_c, content_t, sync_commit, _ = pull_all_user_data_from_github(token=auto_token)
        if sync_ok:
            restore_ok, new_ids, parsed_trainers, _ = restore_user_data_snapshot_locally(content_c, content_t)
            if restore_ok:
                st.session_state.owned_ids = new_ids
                github_loaded = True
                st.session_state["github_sync_commit"] = sync_commit
    except Exception:
        pass

    # 若 GitHub 載入成功，session state 已有最新資料，否則讀本機備份
    if not github_loaded:
        if "owned_ids" not in st.session_state:
            st.session_state.owned_ids = load_user_collection_ids()
    
    st.session_state["github_startup_loaded"] = github_loaded

elif "owned_ids" not in st.session_state:
    # 同一 session 中若 owned_ids 被清除，重新從本機讀取
    st.session_state.owned_ids = load_user_collection_ids()

# 載入卡匣資料
all_cards = load_cards()

# ==============================================================================
# 🔍 卡匣詳細資訊與高清大圖彈跳視窗 (Card Detail Modal)
# ==============================================================================
def render_card_detail_content(c: Dict[str, Any]):
    c_id = c["id"]
    is_owned = c_id in st.session_state.owned_ids
    
    # 頂部星級與能量
    render_html(f"""
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <span class="star-badge" style="font-size:1.15rem;">{'⭐'*c.get('star', 5)}</span>
        <span class="energy-badge" style="font-size:0.85rem; padding:3px 8px;">⚡ 寶可能量 {c.get('energy', 100)}</span>
    </div>
    """)
    
    # 高清大圖展示 (置中且自適應大小)
    if c.get("image"):
        st.image(c.get("image"), caption=f"官方實體卡匣立繪 • {c.get('name')}", use_container_width=True)
        
    name_en_str = f"<div style='font-size: 0.9rem; color: #555; font-weight: bold;'>{c.get('name_en')}</div>" if c.get('name_en') and c.get('name_en') != c.get('name') else ""
    render_html(f"""
    <div style="text-align:center; margin: 8px 0 12px 0;">
        <div style="font-weight: 800; font-size: 1.35rem; color:#1A237E;">{c.get('name')}</div>
        {name_en_str}
        <div style="font-size: 0.85rem; color: #555; margin-top:2px;">
            <b>{c.get('series')}</b> • 官方編號: <code style="font-weight:bold; color:#D32F2F;">{c.get('id')}</code>
        </div>
        <div style="margin-top:6px;">{render_types_html(c.get('types', []))}</div>
    </div>
    """)
    
    # 招式系統
    st.markdown("##### ⚔️ 戰鬥招式")
    
    def render_move_card_html(m_name, m_type, m_cat, m_pwr, m_acc, m_dmg, is_secondary=False):
        if not m_name:
            return ""
        t_col = TYPE_COLORS.get(m_type, "#455A64")
        cat_str = m_cat or ("物理" if m_pwr >= 100 else "特殊")
        cat_badge_col = "#D32F2F" if cat_str == "物理" else "#1976D2"
        acc_str = f"{m_acc}" if m_acc is not None else "100"
        dmg_val = f"{m_dmg:,}" if m_dmg else "-"
        pfx = "🗡️ 副招式" if is_secondary else "⚔️ 主招式"
        bg_col = "#F3E5F5" if is_secondary else "#E8EAF6"
        border_col = "#CE93D8" if is_secondary else "#C5CAE9"
        
        return f"""
        <div style="background:{bg_col}; border:1.5px solid {border_col}; border-radius:10px; padding:10px 12px; margin-bottom:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <div style="font-size:1.05rem; font-weight:800; color:#1A237E;">
                    <span style="font-size:0.8rem; color:#5C6BC0; margin-right:4px;">{pfx}:</span>{m_name}
                </div>
                <span style="background:{t_col}; color:white; padding:2px 8px; border-radius:6px; font-size:0.75rem; font-weight:bold;">{m_type}</span>
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:8px 16px; font-size:0.82rem; color:#37474F;">
                <div>屬性: <b>{m_type}</b></div>
                <div>攻擊類型: <span style="font-weight:bold; color:{cat_badge_col};">{cat_str}</span></div>
                <div>招式威力: <b style="color:#D84315;">{m_pwr}</b></div>
                <div>命中: <b>{acc_str}</b></div>
                <div>傷害: <b style="color:#2E7D32; font-size:0.9rem;">{dmg_val}</b></div>
            </div>
        </div>
        """
        
    m1_html = render_move_card_html(
        c.get("move_name"),
        c.get("move_type"),
        c.get("move_category", "物理"),
        c.get("move_power", 100),
        c.get("move_accuracy", 100),
        c.get("move_damage", 0),
        is_secondary=False
    )
    
    sec_m = c.get("second_move", {})
    sec_html = ""
    if sec_m and sec_m.get("name"):
        sec_html = render_move_card_html(
            sec_m.get("name"),
            sec_m.get("type"),
            sec_m.get("category", "特殊"),
            sec_m.get("power", 100),
            sec_m.get("accuracy", 100),
            sec_m.get("damage", 0),
            is_secondary=True
        )
        
    render_html(f"{m1_html}{sec_html}")
    
    # 六維體質能力值
    st.markdown("##### 📊 六維體質能力值")
    stat_c1, stat_c2, stat_c3 = st.columns(3)
    stat_c1.metric("HP (生命)", c.get("hp", 150))
    stat_c2.metric("攻擊 (Atk)", c.get("atk", 130))
    stat_c3.metric("特攻 (Sp.A)", c.get("sp_atk", 130))
    
    stat_c4, stat_c5, stat_c6 = st.columns(3)
    stat_c4.metric("防禦 (Def)", c.get("def", 120))
    stat_c5.metric("特防 (Sp.D)", c.get("sp_def", 120))
    stat_c6.metric("速度 (Spd)", c.get("spd", 120))
    
    # 相剋屬性防禦分析表
    st.markdown("##### 🎯 弱點與抵抗屬性")
    weak_str = ", ".join(c.get("weaknesses", [])) or "無特定弱點"
    resist_str = ", ".join(c.get("resistances", [])) or "無特定抵抗"
    immune_str = ", ".join(c.get("immunities", []))
    
    render_html(f"""
    <div style="background:#F5F5F5; border-radius:8px; padding:8px 10px; font-size:0.8rem; margin-bottom:10px;">
        <div style="color:#D32F2F; margin-bottom:4px;"><b>🎯 弱點 (受到傷害 2x / 4x):</b><br>{weak_str}</div>
        <div style="color:#2E7D32; margin-bottom:4px;"><b>🛡️ 抵抗 (減免傷害 0.5x / 0.25x):</b><br>{resist_str}</div>
        {f"<div style='color:#7B1FA2;'><b>🚫 免疫 (無效 0.0x):</b><br>{immune_str}</div>" if immune_str else ""}
    </div>
    """)
    
    # 特殊機制
    mechs = c.get("special_mechanics", [])
    if mechs:
        st.markdown("##### ✨ 特殊機制")
        tags_str = " ".join([f'<span class="tag-badge" style="background:#EDE7F6; color:#4A148C; font-weight:bold; font-size:0.8rem; padding:3px 8px;">{m}</span>' for m in mechs])
        render_html(f"<div style='margin-bottom:12px;'>{tags_str}</div>")
        
    # 底部收藏切換按鈕
    st.markdown("---")
    btn_lbl = "✅ 已在我的收藏庫中 (點擊取消持有)" if is_owned else "➕ 加入我的收藏庫"
    btn_tp = "primary" if is_owned else "secondary"
    if st.button(btn_lbl, key=f"dlg_toggle_{c_id}", use_container_width=True, type=btn_tp):
        st.session_state.owned_ids = toggle_card_ownership(c_id, st.session_state.owned_ids)
        st.rerun()

if hasattr(st, "dialog"):
    @st.dialog("🔍 寶可夢 Mezastar 卡匣詳細資料")
    def show_card_details_modal(c: Dict[str, Any]):
        render_card_detail_content(c)

    @st.dialog("⚠️ 確認移出卡匣")
    def confirm_remove_card_dialog(c: Dict[str, Any]):
        st.warning(f"確定要將 **【{c.get('name')}】** ({c.get('series')} • `{c.get('id')}`) 從您的卡匣庫存中移出嗎？")
        c_left, c_right = st.columns(2)
        with c_left:
            if st.button("❌ 取消", key=f"dlg_cancel_rem_{c.get('id')}", use_container_width=True):
                st.rerun()
        with c_right:
            if st.button("🗑️ 確認移出", key=f"dlg_confirm_rem_{c.get('id')}", type="primary", use_container_width=True):
                st.session_state.owned_ids = toggle_card_ownership(c["id"], st.session_state.owned_ids)
                st.rerun()

    @st.dialog("⚠️ 確認刪除訓練家")
    def confirm_delete_trainer_dialog(tr: Dict[str, Any]):
        st.warning(f"確定要刪除訓練家 **【{tr.get('name')}】** (ID: `{tr.get('id')}`) 嗎？此操作無法復原。")
        c_left, c_right = st.columns(2)
        with c_left:
            if st.button("❌ 取消", key=f"dlg_cancel_del_tr_{tr.get('id')}", use_container_width=True):
                st.rerun()
        with c_right:
            if st.button("🗑️ 確認刪除", key=f"dlg_confirm_del_tr_{tr.get('id')}", type="primary", use_container_width=True):
                delete_trainer(tr["id"])
                st.rerun()
else:
    def show_card_details_modal(c: Dict[str, Any]):
        with st.expander(f"🔍 【詳細數據】{c.get('name')} ({c.get('id')})", expanded=True):
            render_card_detail_content(c)

    def confirm_remove_card_dialog(c: Dict[str, Any]):
        st.session_state.owned_ids = toggle_card_ownership(c["id"], st.session_state.owned_ids)
        st.rerun()

    def confirm_delete_trainer_dialog(tr: Dict[str, Any]):
        delete_trainer(tr["id"])
        st.rerun()

# 側邊欄：手機選單抽屜
with st.sidebar:
    st.markdown("### 📱 Mezastar 手機對戰小助手")
    ver_info = load_version_info()
    st.caption(f"📌 系統版本: **v{ver_info.get('version', '1.0.0')}**")
    
    stats = get_collection_stats(st.session_state.owned_ids)
    st.markdown("#### 📊 我的收藏庫")
    c1, c2 = st.columns(2)
    c1.metric("已持有", f"{stats['total_owned']} 張")
    c2.metric("6星傳說", f"{stats['star_counts'].get(6, 0)} 張")
    
    st.markdown("---")
    st.markdown("#### ⚡ 快速全選/清空")
    all_card_ids = {c["id"] for c in all_cards}
    
    col_sel1, col_sel2 = st.columns(2)
    if col_sel1.button("全選持有", use_container_width=True):
        st.session_state.owned_ids = set(all_card_ids)
        save_user_collection_ids(st.session_state.owned_ids)
        st.rerun()
        
    if col_sel2.button("清空收藏", use_container_width=True):
        st.session_state.owned_ids = set()
        save_user_collection_ids(st.session_state.owned_ids)
        st.rerun()

    st.markdown("---")
    st.markdown("#### 🌐 雲端連線狀態")
    git_info = get_git_status()
    st.write(f"🌿 分支: `{git_info['branch']}`")
    st.markdown("[🔗 開啟 GitHub 雲端資料庫檔案](https://github.com/JeffHSU8310/pokemonmezastar/blob/main/data/my_collection.json)")
    if git_info["has_changes"]:
        st.warning(f"⚠️ GitHub 連線驗證失敗：{git_info.get('error', '未知錯誤')}")
    else:
        st.success(f"✅ GitHub 已連線並驗證最新 commit `{git_info['commit']}`")

# 主標題 (手機適配)
render_html("""
<div class="mobile-title">⚡ Pokémon MEZASTAR 對戰助手</div>
<div class="mobile-subtitle">6.1" 手機介面優化 • 能量/體質/弱點/機制最佳隊伍推薦</div>
""")

# 頁籤導覽 (精簡 Emoji 標籤適合手機單手滑動)
tabs = st.tabs([
    "⚔️ 陣容推薦",
    "🎒 我的卡匣",
    "👑 訓練家 ID",
    "🤝 支援寶可夢",
    "📖 圖鑑庫",
    "🌐 網路擴充",
    "🔄 雲端同步"
])

# ==============================================================================
# TAB 1: ⚔️ 智慧對戰推薦 (Battle Lineup Optimizer) - 手機直立版
# ==============================================================================
with tabs[0]:
    camera_enabled = bool(st.session_state.get("scan_camera_enabled", False))
    camera_runtime_ready = opencv_available()
    if camera_enabled and not camera_runtime_ready:
        st.session_state.scan_camera_enabled = False
        camera_enabled = False
    with st.expander("📷 開始相機辨識寶可夢", expanded=camera_enabled):
        st.caption("先開啟相機並對準卡匣；只有按下掃描按鈕才會執行辨識，相機權限於同一工作階段只確認一次。")
        st.caption(f"🧠 已累積 {learning_example_count()} 筆確認學習特徵（不保存原始照片）")
        if not camera_runtime_ready:
            st.error(opencv_error_message() or "相機影像引擎目前無法使用，其他功能仍可正常操作。")
        open_col, close_col = st.columns(2)
        if open_col.button("📷 開啟相機", type="primary", use_container_width=True, key="open_scan_camera", disabled=camera_enabled or not camera_runtime_ready):
            st.session_state.scan_camera_enabled = True
            st.session_state.pop("scan_camera_message", None)
            st.rerun()
        if close_col.button("⏹️ 關閉相機", use_container_width=True, key="close_scan_camera", disabled=not camera_enabled):
            st.session_state.scan_camera_enabled = False
            st.rerun()

        if not camera_runtime_ready:
            st.info("部署環境修復後即可重新開啟相機；圖鑑、收藏與推薦功能不受影響。")
        elif not camera_enabled:
            st.info("相機目前關閉。點一次「開啟相機」並允許權限後，即可連續對準、掃描多張卡匣。")
        else:
            live_context = webrtc_streamer(
                key="mezastar_persistent_card_camera_v281",
                # SENDONLY 直接顯示手機本機預覽；不再把影像經伺服器壓縮後回傳，
                # 可明顯減少方格、延遲與對焦時的拖影。
                mode=WebRtcMode.SENDONLY,
                rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
                media_stream_constraints={
                    "video": {
                        "facingMode": {"ideal": "environment"},
                        "width": {"min": 960, "ideal": 1280},
                        "height": {"min": 540, "ideal": 720},
                        "frameRate": {"min": 20, "ideal": 30, "max": 30},
                        "resizeMode": {"ideal": "none"},
                        "advanced": [
                            {"focusMode": "continuous"},
                            {"exposureMode": "continuous"},
                            {"whiteBalanceMode": "continuous"},
                        ],
                    },
                    "audio": False,
                },
                desired_playing_state=True,
                video_processor_factory=LiveCardScanner,
                async_processing=True,
                media_toggle_controls=False,
                video_html_attrs={
                    "autoPlay": True,
                    "controls": False,
                    "muted": True,
                    "playsInline": True,
                    "style": {
                        "display": "block",
                        "width": "100%",
                        "maxWidth": "340px",
                        "maxHeight": "255px",
                        "objectFit": "contain",
                        "margin": "0 auto",
                        "borderRadius": "10px",
                        "background": "#111111",
                    },
                },
            )
            if not live_context.state.playing:
                st.info("正在取得相機權限並啟動後鏡頭…")
            elif not live_context.video_processor:
                st.info("相機已啟動，正在準備預覽畫面…")
            else:
                preview_width, preview_height = live_context.video_processor.latest_resolution
                resolution_label = f"（擷取 {preview_width}×{preview_height}）" if preview_width else ""
                st.success(f"低延遲相機已就緒並要求連續自動對焦{resolution_label}。讓卡匣填滿畫面、文字清楚後再按掃描。")
                if st.button("🔎 掃描目前畫面", type="primary", use_container_width=True, key="scan_current_camera_frame"):
                    frame_bytes, frame_error, focus_score = live_context.video_processor.capture_current()
                    if frame_error:
                        st.session_state.scan_camera_message = frame_error
                    else:
                        st.session_state.pop("scan_camera_message", None)
                        st.session_state.pop("recognition_learning_message", None)
                        with st.spinner("正在辨識目前畫面…相機會保持開啟"):
                            st.session_state.camera_recognition = recognize_card(frame_bytes, all_cards, top_n=3)
                        st.session_state.camera_recognition_source = "camera"
                        st.session_state.camera_last_frame_bytes = frame_bytes
                        st.session_state.camera_focus_score = focus_score
                        st.session_state.camera_capture_resolution = live_context.video_processor.latest_resolution

        if st.session_state.get("scan_camera_message"):
            st.warning(st.session_state.scan_camera_message)

        camera_result = st.session_state.get("camera_recognition")
        if camera_result:
            if camera_result.get("warning"):
                st.warning(camera_result["warning"])
            info_parts = [f"整體信心：{camera_result.get('confidence', '低')}"]
            if camera_result.get("detected_star"):
                info_parts.append(f"偵測星數：{camera_result['detected_star']}★")
            if camera_result.get("ocr_text"):
                info_parts.append(f"文字：{camera_result['ocr_text']}")
            if st.session_state.get("camera_focus_score"):
                info_parts.append(f"對焦清晰度：{st.session_state.camera_focus_score:.0f}")
            capture_resolution = st.session_state.get("camera_capture_resolution")
            if capture_resolution and capture_resolution[0]:
                info_parts.append(f"掃描解析度：{capture_resolution[0]}×{capture_resolution[1]}")
            st.info("｜".join(info_parts))

            if st.session_state.get("recognition_learning_message"):
                st.success(st.session_state.recognition_learning_message)

            if camera_result.get("confidence") == "低":
                st.warning("辨識信心偏低，請確認候選；可將卡匣靠近、對焦並避開反光後重拍。")
            st.markdown("##### 最接近的 3 張卡匣")
            candidate_columns = st.columns(len(camera_result.get("candidates", [])) or 1)
            for index, candidate in enumerate(camera_result.get("candidates", [])):
                card = candidate["card"]
                with candidate_columns[index]:
                    if card.get("image"):
                        st.image(card["image"], use_container_width=True)
                    st.markdown(f"**{card.get('name', '未知')}**  ")
                    learned_label = "｜🧠 學習加權" if candidate.get("learned_score", 0.0) > 0.58 else ""
                    st.caption(f"{card.get('id', '')}｜{card.get('star', '?')}★｜相符 {candidate['score'] * 100:.0f}%{learned_label}")
                    if st.button("確認並套用", key=f"camera_pick_{card.get('id')}", use_container_width=True):
                        learned_frame = st.session_state.get("camera_last_frame_bytes")
                        if learned_frame:
                            predicted_id = str(camera_result.get("candidates", [{}])[0].get("card", {}).get("id", ""))
                            try:
                                learned_count = record_confirmation(
                                    learned_frame,
                                    correct_card_id=str(card.get("id")),
                                    rejected_card_id=predicted_id,
                                )
                                st.session_state.recognition_learning_message = f"已學習這次確認，目前共 {learned_count} 筆特徵"
                            except Exception as exc:
                                st.session_state.recognition_learning_message = f"已套用卡匣，但學習資料暫時無法保存：{exc}"
                        st.session_state.camera_selected_boss_id = str(card.get("id"))
                        st.rerun()

            with st.expander("前三個都不正確？手動指定並讓系統學習", expanded=False):
                correction_query = st.text_input(
                    "搜尋正確的寶可夢名稱或卡匣編號",
                    key="recognition_correction_query",
                    placeholder="例如：超夢、2-2-001",
                ).strip().lower()
                correction_cards = all_cards
                if correction_query:
                    correction_cards = [
                        item for item in all_cards
                        if correction_query in str(item.get("name", "")).lower()
                        or correction_query in str(item.get("name_en", "")).lower()
                        or correction_query in str(item.get("id", "")).lower()
                    ]
                correction_cards = correction_cards[:80]
                if correction_cards:
                    correction_index = st.selectbox(
                        "正確卡匣",
                        options=range(len(correction_cards)),
                        format_func=lambda value: f"{correction_cards[value]['name']}（{correction_cards[value]['id']}｜{correction_cards[value].get('star', '?')}★）",
                        key=f"recognition_correction_select_{correction_query}",
                    )
                    corrected_card = correction_cards[correction_index]
                    if st.button("🧠 記住正確答案並套用", type="primary", use_container_width=True, key="save_recognition_correction"):
                        learned_frame = st.session_state.get("camera_last_frame_bytes")
                        if learned_frame:
                            predicted_id = str(camera_result.get("candidates", [{}])[0].get("card", {}).get("id", ""))
                            try:
                                learned_count = record_confirmation(
                                    learned_frame,
                                    correct_card_id=str(corrected_card.get("id")),
                                    rejected_card_id=predicted_id,
                                )
                                st.session_state.recognition_learning_message = f"已修正並學習，目前共 {learned_count} 筆特徵"
                            except Exception as exc:
                                st.session_state.recognition_learning_message = f"已套用卡匣，但學習資料暫時無法保存：{exc}"
                        st.session_state.camera_selected_boss_id = str(corrected_card.get("id"))
                        st.rerun()
                else:
                    st.warning("找不到符合條件的卡匣，請調整名稱或編號。")

        selected_camera_id = st.session_state.get("camera_selected_boss_id")
        if selected_camera_id:
            selected_camera_card = next((card for card in all_cards if str(card.get("id")) == selected_camera_id), None)
            if selected_camera_card:
                action_col, clear_col = st.columns([3, 1])
                action_col.success(f"已套用：{selected_camera_card['name']}（{selected_camera_card['id']}）")
                if clear_col.button("清除", key="clear_camera_boss", use_container_width=True):
                    st.session_state.pop("camera_selected_boss_id", None)
                    st.rerun()

    # 手機上採用卡片式下拉選單
    with st.container():
        # 1. 快速星數切換按鈕
        star_filter = st.radio(
            "🎯 選擇對手 Boss ⭐ 星級快選:",
            options=["全部", "6★", "5★", "4★", "3★", "2★", "特別"],
            horizontal=True,
            key="battle_boss_star_filter"
        )
        
        # 2. 搜尋關鍵字輸入框
        search_query = st.text_input("🔍 搜尋 Boss 名稱 / 編號 (輸入關鍵字即時篩選):", placeholder="例如: 雙、超夢、噴火龍、2-2-001...", key="battle_boss_search_input")
        
        # 3. 根據星級與關鍵字即時篩選卡匣
        filtered_boss_cards = all_cards
        if star_filter == "6★":
            filtered_boss_cards = [c for c in filtered_boss_cards if c.get("star") == 6]
        elif star_filter == "5★":
            filtered_boss_cards = [c for c in filtered_boss_cards if c.get("star") == 5]
        elif star_filter == "4★":
            filtered_boss_cards = [c for c in filtered_boss_cards if c.get("star") == 4]
        elif star_filter == "3★":
            filtered_boss_cards = [c for c in filtered_boss_cards if c.get("star") == 3]
        elif star_filter == "2★":
            filtered_boss_cards = [c for c in filtered_boss_cards if c.get("star") == 2]
        elif star_filter == "特別":
            filtered_boss_cards = [c for c in filtered_boss_cards if "特別" in c.get("series", "") or c.get("star") == 1 or "特別" in str(c.get("special", "")) or c.get("id", "").startswith("SP-") or c.get("id", "").startswith("R-") or c.get("id", "").startswith("1-P-")]
            
        if search_query.strip():
            sq = search_query.strip().lower()
            filtered_boss_cards = [c for c in filtered_boss_cards if sq in c.get("name", "").lower() or sq in c.get("id", "").lower()]
            
        # 4. Boss 候選下拉選單 (第一項始終為「自訂」)
        boss_options = ["自訂"] + [f"{c['name']} ({c['series']} - {c['id']}) ⚡{c.get('energy', 100)}" for c in filtered_boss_cards]
        
        # 下拉選單
        count_label = f" (符合條件 {len(filtered_boss_cards)} 隻)" if (star_filter != "全部" or search_query.strip()) else ""
        selected_boss_idx = st.selectbox(
            f"📋 對手 Boss 下拉選單{count_label}:",
            options=range(len(boss_options)),
            format_func=lambda x: boss_options[x],
            key=f"battle_boss_select_{star_filter}_{search_query}"
        )
        
        camera_boss_id = st.session_state.get("camera_selected_boss_id")
        camera_boss = next((card for card in all_cards if str(card.get("id")) == camera_boss_id), None)
        boss_card = None
        if camera_boss:
            picked_c = camera_boss
            boss_card = picked_c
            boss_name = picked_c["name"]
            default_t1 = picked_c["types"][0] if len(picked_c["types"]) > 0 else "一般"
            default_t2 = picked_c["types"][1] if len(picked_c["types"]) > 1 else "無"
        elif selected_boss_idx == 0:
            boss_name = st.text_input("輸入 Boss 名稱:", value=search_query.strip() if search_query.strip() else "超夢")
            default_t1 = "超能力"
            default_t2 = "無"
        else:
            picked_c = filtered_boss_cards[selected_boss_idx - 1]
            boss_card = picked_c
            boss_name = picked_c["name"]
            default_t1 = picked_c["types"][0] if len(picked_c["types"]) > 0 else "一般"
            default_t2 = picked_c["types"][1] if len(picked_c["types"]) > 1 else "無"

    # 正式 Boss 以卡匣 ID 隔離屬性選單狀態；否則先搜尋同名自訂 Boss
    # 再選正式卡匣時，Streamlit 會沿用自訂 Boss 的舊屬性。
    boss_type_state_key = str(boss_card.get("id")) if boss_card else f"custom_{boss_name}"
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        type_options = ["無"] + TYPES
        t1_idx = TYPES.index(default_t1) if default_t1 in TYPES else 0
        boss_type1 = st.selectbox("第一屬性:", options=TYPES, index=t1_idx,
                                  key=f"battle_type1_{boss_type_state_key}")
    with col_t2:
        t2_idx = type_options.index(default_t2) if default_t2 in type_options else 0
        boss_type2 = st.selectbox("第二屬性:", options=type_options, index=t2_idx,
                                  key=f"battle_type2_{boss_type_state_key}")

    # 候選卡匣來源選擇 (手機單選按鈕)
    search_scope = st.radio("出戰卡匣來源:", options=["從我的卡匣庫 (實體卡)", "從全卡匣圖鑑庫 (全卡)"], horizontal=True)

    # 組合 Boss 屬性
    boss_types = [boss_type1]
    if boss_type2 != "無" and boss_type2 != boss_type1:
        boss_types.append(boss_type2)

    # 顯示 Boss 屬性與弱點分析卡
    full_chart = get_full_type_chart_for_defender(boss_types)
    weak_4x = [k for k, v in full_chart.items() if v >= 4.0]
    weak_2x = [k for k, v in full_chart.items() if v == 2.0]
    resist = [k for k, v in full_chart.items() if 0.0 < v <= 0.5]
    immune = [k for k, v in full_chart.items() if v == 0.0]
    
    w4_html = f"<b>💥 4倍弱點:</b> {''.join([render_type_badge(t) for t in weak_4x])} " if weak_4x else ""
    w2_html = f"<b>🎯 2倍弱點:</b> {''.join([render_type_badge(t) for t in weak_2x])} " if weak_2x else ""
    rst_html = f"<br><b>🛡️ 抵抗:</b> {''.join([render_type_badge(t) for t in resist[:4]])}" if resist else ""

    render_html(f"""
    <div style="background:#FFF3E0; border:1px solid #FFE0B2; border-radius:8px; padding:8px; margin: 6px 0;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <b>👾 對手：{boss_name}</b>
            <span>{render_types_html(boss_types)}</span>
        </div>
        <div style="font-size:0.8rem; margin-top:4px;">
            {w4_html} {w2_html} {rst_html}
        </div>
    </div>
    """)

    # 決定候選卡匣
    if "我的卡匣庫" in search_scope:
        candidates = get_user_cards(st.session_state.owned_ids)
        source_label = f"我的收藏 ({len(candidates)}張)"
    else:
        candidates = all_cards
        source_label = f"全圖鑑 ({len(candidates)}張)"

    # 執行推薦
    result = recommend_best_lineup(
        user_cards=candidates,
        boss_types=boss_types,
        boss_name=boss_name,
        team_size=3,
        boss_card={**boss_card, "types": boss_types} if boss_card else None
    )

    if not result.get("recommended_team"):
        st.warning(f"⚠️ {result.get('message', '未找到合適的推薦卡匣！')}")
    else:
        st.markdown(f"#### 🏆 最佳黃金出戰陣容 (Top 3) — *{source_label}*")
        st.caption(
            f"陣容總評 {result.get('team_score', 0):g} 分｜"
            f"組合加成 {result.get('team_synergy', 0):+g}｜"
            f"🧠 相同屬性實戰回饋 {result.get('matching_feedback_count', 0)} 筆"
        )
        st.markdown(
            f"**⚔️ 整隊合計期望傷害 {result.get('team_expected_damage', 0):g}｜"
            f"預估 {result.get('team_expected_ko_turns', 0)} 輪"
            f"（約 {result.get('team_expected_ko_attacks', 0)} 次出招）擊倒 Boss**"
        )
        st.caption(
            "相剋倍率直接乘入傷害，並綜合星數、物攻／特攻、招式威力、命中、STAB、能量與特殊機制；"
            "整隊評分以實際輸出 78% 為主，弱點剋制 14%、角色能力 8%，組合相性僅小幅調整。"
            "整隊擊退回合以三張卡每輪各完成一次攻擊計算。"
        )
        
        # 針對 6.1" 手機直立螢幕：每張推薦卡片垂直排列，資訊高度整合且好讀
        role_badges = ["👑 主攻手 (第1棒)", "⚡ 爆發手 (第2棒)", "🛡️ 收尾手 (第3棒)"]
        
        for idx, rec in enumerate(result["recommended_team"]):
            c = rec["card"]
            c_id = c["id"]
            sec_move = c.get("second_move", {})
            sec_move_html = f"<div style='font-size:0.75rem; color:#666;'>副招: {sec_move.get('name')} ({sec_move.get('type')}) [威力:{sec_move.get('power')}]</div>" if sec_move else ""
            tags_html = ' '.join([f'<span class="tag-badge">{t}</span>' for t in rec['tags']])
            survival_label = "免疫" if rec["incoming_damage"] <= 0.1 else f"{rec['survival_hits']} 擊"
            attack_stat_label = "物攻" if rec["best_move_category"] == "物理" else "特攻"
            
            render_html(f"""
            <div class="card-box" style="border-left: 5px solid {TYPE_COLORS.get(rec['best_move_type'], '#E53935')};">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-weight:bold; font-size:0.85rem; color:#D32F2F;">{role_badges[idx]}</span>
                    <span class="energy-badge">⚡ 能量 {c.get('energy', 100)}</span>
                </div>
                
                <div style="display:flex; align-items:center; margin: 6px 0;">
                    <img src="{c.get('image', '')}" style="width: 65px; height: 65px; object-fit: contain; margin-right: 8px;">
                    <div style="flex:1;">
                        <div style="font-weight: bold; font-size: 1.05rem;">{c.get('name')} <span class="star-badge">{'⭐'*c.get('star', 5)}</span></div>
                        <div style="font-size: 0.75rem; color: #777;">{c.get('series', '')} • {c.get('id', '')}</div>
                        <div>{render_types_html(c.get('types', []))}</div>
                    </div>
                </div>

                <div style="background:#F1F8E9; border-radius:6px; padding:6px; font-size:0.8rem; margin-bottom:4px;">
                    <div style="display:flex; justify-content:space-between;">
                        <span>⚔️ <b>出戰招式:</b> {rec['best_move_name']} ({rec['best_move_type']}／{rec['best_move_category']})</span>
                        <span style="color:#D32F2F; font-weight:bold; font-size:0.95rem;">💥 {rec['type_mult']}x 倍率</span>
                    </div>
                    {sec_move_html}
                    <div style="display:flex; justify-content:space-between; margin-top:2px;">
                        <span>⚡ <b>期望傷害:</b> <b style="color:#1E88E5;">{rec['expected_damage']}</b>（命中 {rec['move_accuracy']:g}%）</span>
                        <span style="color:#555;">🛡️ 可承受: {survival_label}</span>
                    </div>
                    <div style="font-size:0.75rem; color:#555; margin-top:2px;">角色評分 {rec['role_score']}｜本卡每輪傷害貢獻 {rec['expected_damage']}</div>
                    <div style="font-size:0.7rem; color:#777;">輸出依據：{attack_stat_label} {rec['attack_stat']:g}｜星級 ×{rec['star_mult']:g}｜STAB ×{rec['stab_mult']:g}</div>
                </div>

                <div class="stat-compact">
                    <div>HP: <b>{c.get('hp')}</b> | 速: <b>{c.get('spd')}</b></div>
                    <div>攻: <b>{c.get('atk')}</b> | 特攻: <b>{c.get('sp_atk')}</b></div>
                    <div>防: <b>{c.get('def')}</b> | 特防: <b>{c.get('sp_def')}</b></div>
                    <div>機制: <b style="color:#0288D1;">{c.get('special', '無')}</b></div>
                </div>

                <div style="margin-top: 3px;">
                    {tags_html}
                </div>
            </div>
            """)
            
            if st.button(f"🔍 查看 {c.get('name')} 詳細數據與大圖", key=f"btn_rec_detail_{idx}_{c_id}", use_container_width=True):
                show_card_details_modal(c)

        st.markdown("##### 🧠 推薦結果學習")
        st.caption(
            f"完成實戰後回報勝敗，系統會學習相同 Boss 屬性下的卡匣與搭配效果。"
            f"目前累積 {recommendation_feedback_count()} 場；加權有上限，避免少量結果造成誤判。"
        )
        if st.session_state.get("recommendation_learning_message"):
            st.success(st.session_state.pop("recommendation_learning_message"))
        feedback_team = result["recommended_team"]
        feedback_options = {"沒有特別突出": ""}
        feedback_options.update({item["card"]["name"]: item["card"]["id"] for item in feedback_team})
        best_performer_name = st.selectbox(
            "本場表現最佳（可不選）:",
            options=list(feedback_options),
            key=f"recommend_best_{boss_name}_{'_'.join(boss_types)}",
        )
        feedback_win_col, feedback_loss_col = st.columns(2)
        feedback_args = {
            "boss_name": boss_name,
            "boss_types": boss_types,
            "team_card_ids": [item["card"]["id"] for item in feedback_team],
            "best_card_id": feedback_options[best_performer_name] or None,
        }
        if feedback_win_col.button("👍 勝利／推薦有效", type="primary", use_container_width=True,
                                   key=f"recommend_win_{boss_name}_{'_'.join(boss_types)}"):
            count = record_recommendation_feedback(won=True, **feedback_args)
            st.session_state.recommendation_learning_message = f"已記錄勝利並更新推薦權重，目前共 {count} 場"
            st.rerun()
        if feedback_loss_col.button("👎 失敗／需要調整", use_container_width=True,
                                    key=f"recommend_loss_{boss_name}_{'_'.join(boss_types)}"):
            count = record_recommendation_feedback(won=False, **feedback_args)
            st.session_state.recommendation_learning_message = f"已記錄失敗並降低本組合權重，目前共 {count} 場"
            st.rerun()

        with st.expander("💡 展開查看實戰策略指引"):
            for t_msg in result.get("tactics", []):
                st.info(t_msg)

        with st.expander("📊 查看所有候選打手戰力排行表"):
            rank_data = []
            for r_idx, rec in enumerate(result.get("all_ranked", [])):
                c = rec["card"]
                rank_data.append({
                    "排名": r_idx + 1,
                    "卡匣": c.get("name"),
                    "星級": f"{c.get('star')}⭐",
                    "能量": c.get("energy", 100),
                    "編號": f"{c.get('series')} {c.get('id')}",
                    "招式": f"{rec['best_move_name']} ({rec['best_move_type']}／{rec['best_move_category']})",
                    "命中": f"{rec['move_accuracy']:g}%",
                    "剋制": f"{rec['type_mult']}x",
                    "機制": c.get("special", "無"),
                    "期望傷害": rec["expected_damage"],
                    "綜合評分": rec["overall_score"]
                })
            st.dataframe(pd.DataFrame(rank_data), use_container_width=True)

# ==============================================================================
# TAB 2: 🎒 我的卡匣庫 (My Collection) - 專注卡匣檢視與篩選
# ==============================================================================
with tabs[1]:
    st.markdown("#### 🎒 我的卡匣庫存標記")
    
    # 取得使用者目前擁有的卡匣 (依照最新發行彈別與編號排序)
    my_owned_cards = sort_cards_chronological(get_user_cards(st.session_state.owned_ids))

    if not my_owned_cards:
        st.info("🎒 **您目前收藏庫中尚無卡匣！**\n\n請點擊下方 **【➕ 展開全圖鑑快速勾選卡匣】** 或至 **【📖 圖鑑庫】** 點擊「➕ 標記持有」加入您的實體卡匣！")
    else:
        # 已擁有卡匣的搜尋與星級篩選
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            my_star_filter = st.multiselect("⭐ 星級篩選:", options=[6, 5, 4, 3, 2, 1], default=[6, 5, 4, 3, 2, 1], key="my_star_flt")
        with col_f2:
            my_search = st.text_input("🔍 搜尋我擁有的卡匣:", value="", placeholder="名稱/編號/招式", key="my_search_kw")

        # 篩選已持有卡匣
        filtered_my_cards = []
        for c in my_owned_cards:
            if c.get("star", 5) not in my_star_filter:
                continue
            if my_search:
                k_low = my_search.lower()
                name_match = k_low in c.get("name", "").lower()
                name_en_match = k_low in c.get("name_en", "").lower()
                id_match = k_low in c.get("id", "").lower()
                move_match = k_low in c.get("move_name", "").lower() or k_low in c.get("move_type", "").lower()
                if not (name_match or name_en_match or id_match or move_match):
                    continue
            filtered_my_cards.append(c)

        st.caption(f"🎒 目前顯示已擁有卡匣共 **{len(filtered_my_cards)}** 款：")

        # 針對手機與電腦：採用標準橫向逐行網格 (嚴格依照 1 ➔ 2 ➔ 3 ➔ 4 橫向順序排列)
        for row_idx in range(0, len(filtered_my_cards), 2):
            row_cards = filtered_my_cards[row_idx:row_idx+2]
            cols = st.columns(2)
            for j, c in enumerate(row_cards):
                c_id = c["id"]
                with cols[j]:
                    render_html(f"""
                    <div class="card-box" style="border: 2px solid #E53935; background-color: #FFF8F8; min-height: 220px; padding: 8px; margin-bottom: 8px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span class="star-badge">{'⭐'*c.get('star', 5)}</span>
                            <span class="energy-badge">⚡{c.get('energy', 100)}</span>
                        </div>
                        <div style="text-align:center; margin: 4px 0;">
                            <img src="{c.get('image', '')}" style="width: 60px; height: 60px; object-fit: contain;">
                            <div style="font-weight: bold; font-size: 0.95rem; line-height:1.2;">{c.get('name')}</div>
                            <div style="font-size: 0.7rem; color: #777;">{c.get('series')} • {c.get('id')}</div>
                        </div>
                        <div style="margin: 2px 0;">{render_types_html(c.get('types', []))}</div>
                        <div style="font-size: 0.75rem; color:#333;">⚔️ {c.get('move_name')} [{c.get('move_power')}]</div>
                        <div style="font-size: 0.7rem; color:#0288D1;">✨ {c.get('special', '無')}</div>
                    </div>
                    """)
                    
                    sub_c1, sub_c2 = st.columns(2)
                    with sub_c1:
                        if st.button("🔍 詳情", key=f"btn_my_det_{c_id}", use_container_width=True):
                            show_card_details_modal(c)
                    with sub_c2:
                        if st.button("🗑️ 移出", key=f"btn_my_del_{c_id}", use_container_width=True, type="secondary"):
                            confirm_remove_card_dialog(c)

    # 展開從全圖鑑快速勾選卡匣
    with st.expander("➕ 展開全圖鑑快速勾選/新增持有卡匣", expanded=False):
        st.markdown("從全圖鑑點擊 **「➕ 加入」** 即可將卡匣加入到您的卡匣庫中：")
        add_series_options = ["🌟 全部系列"] + ALL_SERIES_LIST
        add_series_pick = st.selectbox("彈別篩選:", options=add_series_options, index=0, key="add_series_pick")
        add_keyword = st.text_input("搜尋卡匣名稱/編號:", value="", placeholder="例如: 蒼響, 鐵轍跡...", key="add_kw_pick")
        
        cand_to_add = []
        for c in all_cards:
            if add_series_pick != "🌟 全部系列" and c.get("series") != add_series_pick:
                continue
            if add_keyword:
                ak_low = add_keyword.lower()
                if ak_low not in c.get("name", "").lower() and ak_low not in c.get("name_en", "").lower() and ak_low not in c.get("id", "").lower():
                    continue
            cand_to_add.append(c)
            
        cand_to_add = sort_cards_chronological(cand_to_add)
        for row_idx in range(0, min(len(cand_to_add), 60), 2):
            row_items = cand_to_add[row_idx:row_idx+2]
            cols = st.columns(2)
            for j, c in enumerate(row_items):
                c_id = c["id"]
                is_owned = c_id in st.session_state.owned_ids
                with cols[j]:
                    border_color = "#E53935" if is_owned else "#E0E0E0"
                    bg_color = "#FFF8F8" if is_owned else "#FFFFFF"
                    render_html(f"""
                    <div class="card-box" style="border: 1.5px solid {border_color}; background-color: {bg_color}; padding: 6px; margin-bottom: 6px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-size:0.8rem;">{'⭐'*c.get('star', 5)}</span>
                            <span style="font-size:0.7rem; color:#777;">{c.get('id')}</span>
                        </div>
                        <div style="font-weight:bold; font-size:0.85rem; margin:2px 0;">{c.get('name')} <span style="font-size:0.7rem; color:#888;">({c.get('series')})</span></div>
                    </div>
                    """)
                    btn_lbl = "✅ 已擁有" if is_owned else "➕ 加入收藏"
                    btn_tp = "primary" if is_owned else "secondary"
                    if st.button(btn_lbl, key=f"btn_add_tab_{c_id}", use_container_width=True, type=btn_tp):
                        st.session_state.owned_ids = toggle_card_ownership(c_id, st.session_state.owned_ids)
                        st.rerun()

# ==============================================================================
# TAB 3: 👑 訓練家 ID 庫 (Trainer ID Manager & Machine QR Code Scanner)
# ==============================================================================
with tabs[2]:
    st.markdown("#### 👑 訓練家 ID 管理與機台專用 QR Code")
    st.caption("支援上傳相片自動辨識 QR Code、自訂多組訓練家名稱與放大高亮掃描模式！")

    trainers_list = load_trainers()

    # 頂部：目前使用中的訓練家橫幅與超大掃描快速按鈕
    active_trainer = next((t for t in trainers_list if t.get("is_active")), trainers_list[0] if trainers_list else None)

    if active_trainer:
        t_id = active_trainer.get("id", "")
        t_name = active_trainer.get("name", "未命名訓練家")
        t_notes = active_trainer.get("notes", "")
        qr_b64 = generate_qr_base64(t_id, box_size=14)

        render_html(f"""
        <div style="background: linear-gradient(135deg, #FFF8E1, #FFECB3); border: 2px solid #FFA000; border-radius: 12px; padding: 12px; margin-bottom: 12px; text-align:center;">
            <div style="font-size:0.85rem; color:#E65100; font-weight:bold;">👑 目前選用訓練家</div>
            <div style="font-size:1.2rem; font-weight:800; color:#212121; margin:2px 0;">{t_name}</div>
            <div style="font-size:0.8rem; color:#616161; font-family:monospace; word-break:break-all; overflow-wrap:anywhere; line-height:1.4; padding:0 4px;">ID: {t_id}</div>
            {f"<div style='font-size:0.75rem; color:#757575; margin-top:2px;'>{t_notes}</div>" if t_notes else ""}
        </div>
        """)

        # 快速放大掃描視窗抽屜
        with st.expander("⚡ 點此開啟【機台鏡頭專用 • 超大亮屏掃描 QR Code】", expanded=True):
            st.markdown("""
            <div style="background:#000000; padding:15px; border-radius:12px; text-align:center; margin:auto; max-width:380px;">
                <div style="color:#FFF; font-weight:bold; font-size:0.95rem; margin-bottom:8px;">📱 請將此二維碼對準 Mezastar 機台讀取鏡頭</div>
                <div style="background:#FFFFFF; padding:12px; border-radius:10px; display:inline-block;">
            """ + f'<img src="{qr_b64}" style="width:260px; height:260px; display:block; margin:auto;" />' + """
                </div>
                <div style="color:#FFD54F; font-size:0.75rem; margin-top:8px;">💡 提示：掃描時請將手機螢幕亮度調高，保持距離機台鏡頭約 5~10 公分。</div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # 新增/讀取訓練家區塊
    st.markdown("##### ➕ 新增或讀取訓練家 ID")
    add_mode = st.radio("新增方式:", ["📷 上傳 QR Code 照片/截圖自動辨識", "✍️ 手動輸入訓練家 ID/代碼"], horizontal=True)

    detected_id = ""
    if "📷" in add_mode:
        qr_file = st.file_uploader("上傳含有訓練家 QR Code 的照片或截圖 (JPG/PNG/WEBP):", type=["png", "jpg", "jpeg", "webp"], key="upload_trainer_qr")
        if qr_file is not None:
            with st.spinner("正在以多重濾鏡自動辨識 QR Code..."):
                img_bytes = qr_file.getvalue()
                success, val, msg = decode_qr_from_bytes(img_bytes)
                if success:
                    st.success(f"✅ {msg} 辨識結果: `{val}`")
                    detected_id = val
                else:
                    st.error(f"❌ {msg}")
    
    with st.form("add_trainer_form"):
        form_id = st.text_input("訓練家 ID / QR Code 內容:", value=detected_id, placeholder="例如: MZ-TR-8888-001 或辨識出的字串")
        form_name = st.text_input("訓練家名稱 (自訂暱稱):", placeholder="例如: 哥哥的主號 / 寶可夢大師")
        form_notes = st.text_input("備註說明 (可選):", placeholder="例如: 常用於台北站前大卡機")
        
        submitted = st.form_submit_button("💾 儲存訓練家至本機", use_container_width=True, type="primary")
        if submitted:
            if not form_id.strip():
                st.warning("請先填寫或辨識出訓練家 ID！")
            else:
                ok, res_msg, updated_list = add_trainer(form_id, form_name, form_notes)
                if ok:
                    st.success(f"✅ {res_msg}")
                    st.rerun()
                else:
                    st.error(f"❌ {res_msg}")

    st.divider()

    # 多組訓練家清單與切換
    st.markdown("##### 🗂️ 已儲存的訓練家清單")
    if not trainers_list:
        st.info("目前尚無儲存的訓練家資料。")
    else:
        for idx, tr in enumerate(trainers_list):
            tr_id = tr.get("id", "")
            tr_name = tr.get("name", "未命名")
            tr_active = tr.get("is_active", False)
            tr_notes = tr.get("notes", "")

            with st.container():
                col_t1, col_t2, col_t3 = st.columns([3, 1.2, 1])
                with col_t1:
                    status_badge = "👑 **[目前使用中]** " if tr_active else ""
                    st.markdown(f"{status_badge}**{tr_name}**<div style='font-size:0.75rem; color:#757575; word-break:break-all; font-family:monospace;'>ID: {tr_id}</div>", unsafe_allow_html=True)
                    if tr_notes:
                        st.caption(f"備註: {tr_notes}")
                with col_t2:
                    if not tr_active:
                        if st.button("👑 設為目前", key=f"btn_set_act_{idx}_{tr_id}", use_container_width=True):
                            set_active_trainer(tr_id)
                            st.rerun()
                    else:
                        st.button("✅ 使用中", key=f"btn_act_dis_{idx}_{tr_id}", disabled=True, use_container_width=True)
                with col_t3:
                    if st.button("🗑️ 刪除", key=f"btn_del_tr_{idx}_{tr_id}", use_container_width=True):
                        confirm_delete_trainer_dialog(tr)
                
                # 單一訓練家 QR Code 展開
                with st.expander(f"🔍 查看【{tr_name}】專屬 QR Code", expanded=False):
                    q_b64 = generate_qr_base64(tr_id, box_size=12)
                    st.markdown(f'<div style="text-align:center; padding:10px; background:#F5F5F5; border-radius:8px;"><img src="{q_b64}" style="width:200px; height:200px;" /></div>', unsafe_allow_html=True)


# ==============================================================================
# TAB 4: 🤝 支援寶可夢 (Support Pokemon & Machine QR Code Library)
# ==============================================================================
with tabs[3]:
    st.markdown("#### 🤝 官方支援寶可夢圖鑑與機台專用 QR Code")
    st.caption("收錄歷代官方全系列支援寶可夢！在機台對戰掃描時，可直接點擊放大 QR Code 召喚神獸支援助戰！")

    all_support_pokemon = load_support_pokemon()

    # 篩選控制項
    sp_series_list = ["🌟 全部系列"] + sorted(list(set(sp.get("series", "") for sp in all_support_pokemon)))
    sp_col1, sp_col2 = st.columns([1, 1])
    with sp_col1:
        sp_sel_series = st.selectbox("📂 彈別系列篩選:", options=sp_series_list, index=0, key="sp_series_filter")
    with sp_col2:
        sp_kw = st.text_input("🔍 搜尋寶可夢名稱或技能:", value="", placeholder="例如: 噴火龍, 蒼響, 閃電...", key="sp_search_kw")

    # 過濾
    filtered_sp = []
    for sp in all_support_pokemon:
        if sp_sel_series != "🌟 全部系列" and sp.get("series") != sp_sel_series:
            continue
        if sp_kw:
            kw_low = sp_kw.lower()
            if kw_low not in sp.get("name", "").lower() and kw_low not in sp.get("skill_name", "").lower() and kw_low not in sp.get("skill_desc", "").lower():
                continue
        filtered_sp.append(sp)

    st.caption(f"共找到 **{len(filtered_sp)}** 款支援寶可夢：")

    # 支援寶可夢卡片式列表 (逐行排列)
    for sp_idx in range(0, len(filtered_sp), 2):
        row_sp = filtered_sp[sp_idx:sp_idx+2]
        sp_cols = st.columns(2)
        for j, sp in enumerate(row_sp):
            sp_id = sp.get("id", "")
            sp_name = sp.get("name", "")
            sp_types = sp.get("types", [])
            sp_skill = sp.get("skill_name", "")
            sp_desc = sp.get("skill_desc", "")
            sp_series = sp.get("series", "")
            sp_qr_data = sp.get("qr_data", f"MEZASTAR-SP:{sp_id}")
            sp_icon = sp.get("icon_url", "")

            with sp_cols[j]:
                primary_type = sp_types[0] if sp_types else "一般"
                type_bg = TYPE_COLORS.get(primary_type, "#E53935")

                render_html(f"""
                <div class="card-box" style="border-top: 4px solid {type_bg}; padding:10px; margin-bottom:8px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="background:{type_bg}; color:#FFF; font-size:0.7rem; font-weight:bold; padding:2px 6px; border-radius:4px;">{sp_series}</span>
                        <span style="font-size:0.75rem; color:#666; font-family:monospace;">{sp_id}</span>
                    </div>
                    <div style="display:flex; align-items:center; margin:8px 0;">
                        <img src="{sp_icon}" style="width:55px; height:55px; object-fit:contain; margin-right:8px;" />
                        <div>
                            <div style="font-weight:bold; font-size:0.95rem; color:#111;">{sp_name}</div>
                            <div style="font-size:0.75rem;">{render_types_html(sp_types)}</div>
                        </div>
                    </div>
                    <div style="background:#FFFDE7; border-left:3px solid #FBC02D; padding:6px; border-radius:4px; font-size:0.75rem; margin-bottom:6px;">
                        <div style="font-weight:bold; color:#F57F17;">⚡ 支援招式：{sp_skill}</div>
                        <div style="color:#555; font-size:0.7rem; margin-top:2px;">{sp_desc}</div>
                    </div>
                </div>
                """)

                # 點擊放大 QR Code 抽屜
                with st.expander(f"📱 點此放大【{sp_name}】機台掃描 QR Code", expanded=False):
                    sp_qr_b64 = generate_qr_base64(sp_qr_data, box_size=12)
                    st.markdown(f"""
                    <div style="background:#000000; padding:12px; border-radius:10px; text-align:center;">
                        <div style="color:#FFF; font-weight:bold; font-size:0.85rem; margin-bottom:6px;">⚡ {sp_name} 支援召喚碼</div>
                        <div style="background:#FFFFFF; padding:10px; border-radius:8px; display:inline-block;">
                            <img src="{sp_qr_b64}" style="width:220px; height:220px; display:block; margin:auto;" />
                        </div>
                        <div style="color:#B0BEC5; font-size:0.7rem; margin-top:6px; font-family:monospace;">代碼: {sp_qr_data}</div>
                    </div>
                    """, unsafe_allow_html=True)


# ==============================================================================
# TAB 5: 📖 全卡匣圖鑑庫 (Pokedex) - 依彈別完整分類與數據檢視
# ==============================================================================
with tabs[4]:
    st.markdown("#### 📖 寶可夢 Mezastar 全卡匣圖鑑庫")
    
    # 彈別快速分類選單
    series_tab_options = ["🌟 全部系列"] + ALL_SERIES_LIST
    selected_series = st.selectbox("📂 選擇分類彈別系列:", options=series_tab_options, index=0)
    
    col_pk1, col_pk2 = st.columns([1, 1])
    with col_pk1:
        pokedex_star_filter = st.multiselect("⭐ 星級篩選:", options=[6, 5, 4, 3, 2, 1], default=[6, 5, 4, 3, 2, 1], key="pk_star_filter")
    with col_pk2:
        pokedex_search = st.text_input("🔍 搜尋名稱/編號/屬性/招式:", value="", placeholder="例如: 蒼響, 2-2-001, 鋼...", key="pk_search")

    # 檢視模式切換 (手機優化：圖鑑卡片模式 vs 數據表格模式)
    view_mode = st.radio("檢視呈現方式:", options=["🗂️ 圖鑑卡片模式 (手機好讀)", "📊 完整數據表格模式"], horizontal=True)

    # 篩選資料
    pokedex_cards = []
    for c in all_cards:
        if selected_series != "🌟 全部系列" and c.get("series") != selected_series:
            continue
        if c.get("star", 5) not in pokedex_star_filter:
            continue
        if pokedex_search:
            s_low = pokedex_search.lower()
            n_match = s_low in c.get("name", "").lower()
            n_en_match = s_low in c.get("name_en", "").lower()
            id_match = s_low in c.get("id", "").lower()
            type_match = any(s_low in t.lower() for t in c.get("types", []))
            move_match = s_low in c.get("move_name", "").lower() or s_low in c.get("move_type", "").lower()
            mech_match = any(s_low in m.lower() for m in c.get("special_mechanics", []))
            if not (n_match or n_en_match or id_match or type_match or move_match or mech_match):
                continue
        pokedex_cards.append(c)

    # 確保圖鑑庫依照【最新發行時間 (銀河二彈在最前) ➔ 卡匣編號】排列
    pokedex_cards = sort_cards_chronological(pokedex_cards)

    # 系列統計摘要橫幅
    cur_series_cards = [c for c in all_cards if selected_series == "🌟 全部系列" or c.get("series") == selected_series]
    s_star_6 = sum(1 for c in cur_series_cards if c.get("star") == 6)
    s_star_5 = sum(1 for c in cur_series_cards if c.get("star") == 5)
    s_star_4 = sum(1 for c in cur_series_cards if c.get("star") == 4)
    s_star_3 = sum(1 for c in cur_series_cards if c.get("star") == 3)
    s_star_2 = sum(1 for c in cur_series_cards if c.get("star") == 2)
    s_star_1 = sum(1 for c in cur_series_cards if c.get("star") == 1)

    render_html(f"""
    <div style="background:#ECEFF1; border-radius:8px; padding:6px 10px; margin: 4px 0 10px 0; font-size:0.8rem;">
        <b>📌 【{selected_series}】收錄統計：</b> 共 <b>{len(cur_series_cards)}</b> 款卡匣
        <div style="margin-top:2px; color:#37474F;">
            6星: <b>{s_star_6}</b> | 5星: <b>{s_star_5}</b> | 4星: <b>{s_star_4}</b> | 3星: <b>{s_star_3}</b> | 2星: <b>{s_star_2}</b> | 1星: <b>{s_star_1}</b>
        </div>
    </div>
    """)

    st.caption(f"目前顯示共 **{len(pokedex_cards)}** 款卡匣：")

    if view_mode == "🗂️ 圖鑑卡片模式 (手機好讀)":
        # 6.1 吋手機標準橫向逐行卡片網格 (保證 1 ➔ 2 ➔ 3 ➔ 4 橫向嚴格順序)
        for row_idx in range(0, len(pokedex_cards), 2):
            row_cards = pokedex_cards[row_idx:row_idx+2]
            pk_cols = st.columns(2)
            for j, c in enumerate(row_cards):
                c_id = c["id"]
                with pk_cols[j]:
                    weak_str = ", ".join(c.get("weaknesses", []))
                    sec_m = c.get("second_move", {})
                    sec_text = f"<div style='font-size:0.7rem; color:#666;'>副招: {sec_m.get('name')} [{sec_m.get('power')}]</div>" if sec_m else ""
                    
                    render_html(f"""
                    <div class="card-box" style="border-top: 4px solid {TYPE_COLORS.get(c.get('move_type', '一般'), '#E53935')}; min-height: 250px; padding:8px; margin-bottom:8px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span class="star-badge">{'⭐'*c.get('star', 5)}</span>
                            <span class="energy-badge">⚡{c.get('energy', 100)}</span>
                        </div>
                        <div style="text-align:center; margin: 4px 0;">
                            <img src="{c.get('image', '')}" style="width: 60px; height: 60px; object-fit: contain;">
                            <div style="font-weight: bold; font-size: 0.95rem; line-height:1.2;">{c.get('name')}</div>
                            <div style="font-size: 0.7rem; color: #777;">{c.get('series')} • {c.get('id')}</div>
                        </div>
                        <div style="margin: 2px 0;">{render_types_html(c.get('types', []))}</div>
                        <div style="font-size: 0.75rem;">⚔️ <b>{c.get('move_name')}</b> ({c.get('move_type')}) [威力: {c.get('move_power')}]</div>
                        {sec_text}
                        <div style="font-size: 0.7rem; color:#555; background:#F8F9FA; padding:3px; border-radius:4px; margin:3px 0;">
                            HP {c.get('hp')} | 攻 {c.get('atk')} | 防 {c.get('def')} | 速 {c.get('spd')}
                        </div>
                        <div style="font-size: 0.7rem; color:#D32F2F;">🎯 弱點: {weak_str[:25] + ('...' if len(weak_str)>25 else '')}</div>
                        <div style="font-size: 0.7rem; color:#0288D1;">✨ {c.get('special', '無')}</div>
                    </div>
                    """)
                    
                    pk_btn_c1, pk_btn_c2 = st.columns(2)
                    with pk_btn_c1:
                        if st.button("🔍 詳情", key=f"btn_pk_det_{row_idx}_{j}_{c_id}", use_container_width=True):
                            show_card_details_modal(c)
                    with pk_btn_c2:
                        is_owned = c_id in st.session_state.owned_ids
                        pk_lbl = "✅ 擁有" if is_owned else "➕ 加入"
                        pk_tp = "primary" if is_owned else "secondary"
                        if st.button(pk_lbl, key=f"btn_pk_own_{row_idx}_{j}_{c_id}", use_container_width=True, type=pk_tp):
                            st.session_state.owned_ids = toggle_card_ownership(c_id, st.session_state.owned_ids)
                            st.rerun()
    else:
        df_all = pd.DataFrame([{
            "編號": c.get("id"),
            "名稱": c.get("name"),
            "英文名稱": c.get("name_en", c.get("name")),
            "彈別": c.get("series"),
            "星級": f"{c.get('star')}⭐",
            "能量": c.get("energy", 100),
            "屬性": "/".join(c.get("types", [])),
            "招式": c.get("move_name"),
            "招式屬性": c.get("move_type"),
            "威力": c.get("move_power"),
            "HP": c.get("hp"),
            "物攻": c.get("atk"),
            "物防": c.get("def"),
            "特攻": c.get("sp_atk"),
            "特防": c.get("sp_def"),
            "速度": c.get("spd"),
            "弱點屬性": ", ".join(c.get("weaknesses", [])),
            "抵抗屬性": ", ".join(c.get("resistances", [])),
            "特殊機制": ", ".join(c.get("special_mechanics", [c.get("special", "無")]))
        } for c in pokedex_cards])
        
        st.dataframe(df_all, use_container_width=True)

# ==============================================================================
# TAB 6: 🌐 網路資料擴充與一鍵自動更新
# ==============================================================================
with tabs[5]:
    st.markdown("#### 🌐 官方卡匣一鍵自動更新與網路擴充")
    
    from scraper import fetch_and_sync_official_new_cards

    if "official_auto_update_result" not in st.session_state:
        with st.spinner("正在執行每日官方新卡安全檢查..."):
            st.session_state.official_auto_update_result = scheduled_official_update(auto_push=True)
    auto_update_result = st.session_state.official_auto_update_result
    if auto_update_result.get("new_count", 0) and not st.session_state.get("official_auto_update_applied"):
        st.session_state.official_auto_update_applied = True
        st.rerun()
    if auto_update_result.get("success"):
        if auto_update_result.get("new_count", 0):
            st.success(f"🤖 自動新增 {auto_update_result['new_count']} 款雙官方確認的新卡匣")
        else:
            st.caption(f"🤖 自動檢查：{auto_update_result.get('sync_message', '已完成')} ")
    else:
        st.warning(f"🤖 自動檢查暫時失敗：{auto_update_result.get('error', '未知錯誤')}；圖鑑未修改")
    
    render_html("""
    <div style="background: linear-gradient(135deg, #E8F5E9, #C8E6C9); border: 1.5px solid #81C784; border-radius: 10px; padding: 12px; margin-bottom: 12px;">
        <div style="font-weight: 800; font-size: 1.05rem; color: #1B5E20; margin-bottom: 4px;">
            🚀 官方最新彈別一鍵自動聯網抓取 (免人工輸入)
        </div>
        <div style="font-size: 0.8rem; color: #2E7D32; line-height: 1.4;">
            系統每 12 小時自動比對<b>台灣官方網站</b>與<b>國際官方網站</b>。只有兩邊都有相同新卡號時才新增資料與官方圖片；既有卡號永遠跳過，不覆寫、不重排。
        </div>
    </div>
    """)
    
    if st.button("🚀 立即一鍵自動掃描並抓取官方最新卡匣", use_container_width=True, type="primary"):
        with st.spinner("正在比對台灣與國際版寶可夢官方網站..."):
            crawl_res = fetch_and_sync_official_new_cards(auto_push=True)
            if not crawl_res.get("success"):
                st.error(f"❌ {crawl_res.get('error', '官方資料更新失敗')}；為保護原始圖鑑，本次沒有寫入任何資料。")
            elif crawl_res.get("new_count", 0) > 0:
                st.balloons()
                st.success(f"🎉 太棒了！成功發現並自動收錄 **{crawl_res['new_count']}** 款官方全新卡匣！")
                st.info(f"☁️ 雲端狀態：{crawl_res['sync_message']}")
                with st.expander("📋 查看本次自動新增的官方新卡匣清單", expanded=True):
                    for cid, cname, sname in crawl_res.get("new_cards", []):
                        st.write(f"• **{sname}** | 編號 `{cid}` | **{cname}**")
                st.rerun()
            else:
                st.success(f"✅ 雙官方網站掃描完成！目前圖鑑共 {len(load_cards())} 款，既有資料完全未變更。")
                if crawl_res.get("pending_count", 0):
                    st.warning(f"有 {crawl_res['pending_count']} 款僅在台灣官網出現，等待國際官網確認後才會安全加入。")
                st.info(f"📌 掃描範圍包含：{', '.join([f'{s[0]} ({s[1]}款)' for s in crawl_res.get('scanned_series', [])])}")

    st.markdown("---")
    
    with st.expander("🔍 1. 線上查詢官方寶可夢百科 (PokeAPI)", expanded=False):
        poke_query = st.text_input("輸入寶可夢名稱:", value="超夢")
        if st.button("🌐 聯網抓取屬性與數值", use_container_width=True):
            meta = fetch_online_pokemon_metadata(poke_query)
            if meta:
                st.success(f"✅ 抓取到 {meta['name']}！")
                st.json(meta)
            else:
                st.error("❌ 查無資料")

    with st.expander("➕ 2. 自訂新增單張特殊卡匣至資料庫", expanded=False):
        with st.form("add_card_form"):
            f_id = st.text_input("卡匣編號 (例: 2-2-001):", value="2-2-001")
            f_name = st.text_input("寶可夢名稱:", value="蒼響")
            f_series = st.selectbox("彈別:", options=ALL_SERIES_LIST, index=0)
            f_star = st.slider("星級:", min_value=1, max_value=6, value=6)
            f_energy = st.number_input("寶可能量:", min_value=30, max_value=300, value=210)
            f_t1 = st.selectbox("第一屬性:", options=TYPES, index=17)
            f_t2 = st.selectbox("第二屬性 (若無選無):", options=["無"] + TYPES, index=17)
            f_move = st.text_input("招式名稱:", value="巨獸斬")
            f_mtype = st.selectbox("招式屬性:", options=TYPES, index=16)
            f_mpower = st.number_input("招式威力:", min_value=50, max_value=250, value=175)
            f_special = st.multiselect("特殊機制 (可複選):", options=["超極巨化", "極巨化", "超級進化", "Mega進化", "Z招式", "太晶化", "雙重攻擊", "雙重招式", "連擊", "連擊卡匣", "組合招式", "原始回歸"], default=["雙重招式", "雙重攻擊"])
            f_img = st.text_input("圖片 URL:", value="https://img.pokemondb.net/sprites/home/normal/zacian.png")
            
            if st.form_submit_button("💾 儲存卡匣", use_container_width=True):
                types_list = [f_t1]
                if f_t2 != "無" and f_t2 != f_t1:
                    types_list.append(f_t2)
                
                new_card_dict = {
                    "id": f_id.strip(), "name": f_name.strip(), "series": f_series, "star": f_star,
                    "energy": f_energy, "types": types_list, "hp": 190, "atk": 160, "def": 140,
                    "sp_atk": 160, "sp_def": 140, "spd": 150, "move_name": f_move.strip(),
                    "move_type": f_mtype, "move_power": f_mpower, "special": f_special[0] if f_special else "無",
                    "special_mechanics": f_special, "image": f_img.strip()
                }
                ok, msg = add_custom_card(new_card_dict)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

# ==============================================================================
# TAB 7: 🔄 GitHub 雲端同步 (GitHub REST API 雙向持久化備份)
# ==============================================================================
with tabs[6]:
    st.markdown("#### 🔄 GitHub 雲端永久雙向同步")
    st.caption("透過 GitHub REST API 直連您的 GitHub main 分支，換手機、清快取、伺服器重啟均能秒還原！")
    
    g_info = get_git_status()
    st.caption(f"📌 系統版本: `v{g_info['version']}` | 雲端分支: `main` | 倉庫: `JeffHSU8310/pokemonmezastar`")

    # 讀取已永久儲存的 Token（三重來源）
    saved_tok = get_saved_github_token()
    if not saved_tok:
        try:
            saved_tok = st.secrets.get("GITHUB_TOKEN", "")
        except Exception:
            pass
    if not saved_tok and "github_token" in st.session_state:
        saved_tok = st.session_state.get("github_token", "")

    # 儲存狀態診斷
    config_exists = os.path.exists(os.path.join("data", "user_config.json"))
    secrets_exists = os.path.exists(os.path.join(".streamlit", "secrets.toml"))

    st.markdown("##### 🔑 1. 設定並記住 GitHub Personal Access Token (PAT)")
    
    # 顯示 Token 儲存狀態
    if saved_tok:
        st.success(f"✅ **Token 已永久儲存**（磁碟設定檔: {'✓' if config_exists else '✗'} | secrets.toml: {'✓' if secrets_exists else '✗'}）— 每次開啟自動連 GitHub 讀取最新資料！")
    else:
        st.warning("⚠️ **尚未儲存 Token！** 請貼上您的 GitHub Token 並點擊【💾 永久記住 Token】，之後每次開啟都會自動從 GitHub 載入最新卡匣與訓練家！")

    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        tok_input = st.text_input(
            "輸入您的 GitHub Token (以 ghp_ 開頭):",
            value=saved_tok,
            type="password",
            placeholder="例如: ghp_xxxxxxxxxxxxxxxxxxxx",
            help="儲存後永久寫入磁碟，重開機、清快取均有效。"
        )
    with col_t2:
        st.write("")
        st.write("")
        if st.button("💾 永久記住 Token", type="primary", use_container_width=True):
            if tok_input.strip():
                ok = save_github_token(tok_input.strip())
                st.session_state.github_token = tok_input.strip()
                if ok:
                    st.success("✅ Token 已永久儲存至磁碟！下次開啟自動從 GitHub 載入！")
                else:
                    st.warning("⚠️ 儲存可能不完整，請確認程式目錄有寫入權限。")
                # 儲存後立即觸發一次 GitHub 同步更新 session
                st.session_state.pop("github_auto_synced", None)
                st.rerun()
            else:
                st.warning("請先填入 Token！")
        
        if saved_tok:
            if st.button("🗑️ 清除記錄", use_container_width=True):
                clear_saved_github_token()
                for k in ["github_token", "github_auto_synced", "github_startup_loaded"]:
                    st.session_state.pop(k, None)
                st.info("已清除已儲存的 Token")
                st.rerun()

    active_token = tok_input.strip() if tok_input and tok_input.strip() else saved_tok

    if active_token:
        startup_ok = st.session_state.get("github_startup_loaded", False)
        if startup_ok:
            st.caption(f"🟢 **Token 已綁定，本次啟動已成功自 GitHub 載入 {len(st.session_state.owned_ids)} 款卡匣與訓練家資料！**")
        else:
            st.caption("🟡 **Token 已綁定，但本次啟動 GitHub 同步未成功**（可能網路暫時中斷）— 請點擊下方【📥 拉取並還原】手動同步。")
    else:
        st.caption("🔴 **尚未設定 Token** — 請先填入 Token 並點擊【💾 永久記住 Token】，之後每次開啟均自動從 GitHub 載入最新資料！")

    with st.expander("💡 如何在 1 分鐘內免費取得您的 GitHub Token？（超簡單 3 步驟）", expanded=False):
        st.markdown("""
        1. 點擊開啟：[👉 GitHub Token 快速建立頁面 (點此直達)](https://github.com/settings/tokens/new)
        2. **Note（名稱）**：填入 `mezastar-sync`
        3. **Expiration（效期）**：選 `No expiration`（無期限）
        4. **Select scopes（權限勾選）**：務必勾選第 1 項 **`repo`**（包含所有子項目）
        5. 滑到最下方點擊綠色按鈕 **「Generate token」** ➔ 複製綠色框框中的 `ghp_...` 代碼。
        6. 回到上方貼入輸入框中，點擊 **【💾 永久記住 Token】** 即可！
        
        *(進階提示：您也可以在 Streamlit Cloud 後台 Settings ➔ Secrets 填入 `GITHUB_TOKEN = "ghp_..."`，即可所有裝置免輸入自動同步！)*
        """)

    st.divider()

    st.markdown("##### 🚀 2. 雙向同步操作")
    col_syn1, col_syn2 = st.columns(2)
    with col_syn1:
        st.markdown("**📤 將目前裝置資料 ➔ 永久寫入 GitHub**")
        commit_msg = st.text_input("提交備註說明:", value="同步最新卡匣庫與訓練家資料")
        if st.button("🚀 立即全量寫入 GitHub 雲端", type="primary", use_container_width=True):
            if not active_token:
                st.error("❌ 請先在上方填入您的 GitHub Token！")
            else:
                with st.spinner("正在透過 GitHub API 寫入 main 倉庫..."):
                    trainers_curr = load_trainers()
                    ok, res_msg = sync_all_user_data_to_github(
                        owned_ids=list(st.session_state.owned_ids),
                        trainers=trainers_curr,
                        token=active_token,
                        summary=commit_msg
                    )
                    if ok:
                        st.balloons()
                        st.success(res_msg)
                    else:
                        st.error(res_msg)

    with col_syn2:
        st.markdown("**📥 從 GitHub 雲端 ➔ 拉取最新資料至此裝置**")
        st.caption("在換新手機、更換電腦或清除瀏覽器快取後，點擊下方按鈕即可秒還原所有卡匣與訓練家！")
        if st.button("📥 一鍵自 GitHub 雲端拉取並還原", use_container_width=True, type="primary"):
            with st.spinner("正在直連 GitHub main 下載最新檔案..."):
                sync_ok, content_c, content_t, sync_commit, sync_msg = pull_all_user_data_from_github(token=active_token)
                if sync_ok:
                    restore_ok, new_ids, t_data, restore_msg = restore_user_data_snapshot_locally(content_c, content_t)
                    if restore_ok:
                        st.session_state.owned_ids = new_ids
                        st.session_state["github_sync_commit"] = sync_commit
                        st.balloons()
                        st.success(f"🎉 已從 GitHub commit `{sync_commit[:7]}` 完整驗證並還原 {len(new_ids)} 款卡匣與 {len(t_data)} 組訓練家資料！")
                        st.rerun()
                    else:
                        st.error(f"❌ 本機還原失敗：{restore_msg}")
                else:
                    st.error(f"❌ 拉取失敗：{sync_msg}")

    st.divider()

    st.markdown("##### 💾 3. 本地檔案備份與分享中心")
    export_tab1, export_tab2, export_tab3 = st.tabs(["💬 複製 LINE 分享代碼", "📄 下載 JSON 備份檔", "📊 下載 CSV (Excel)"])
    
    with export_tab1:
        share_code = export_collection_share_code(st.session_state.owned_ids)
        st.text_area("📋 卡匣分享代碼 (可複製傳到 LINE 給朋友或自己在其他裝置貼上還原):", value=share_code, height=80)
        st.caption(f"💡 此代碼包含您目前擁有的 {len(st.session_state.owned_ids)} 張卡匣。")
        
    with export_tab2:
        collection_json_str = export_collection_json(st.session_state.owned_ids)
        st.download_button(
            label="📄 下載完整結構化 JSON 備份檔",
            data=collection_json_str,
            file_name="my_mezastar_backup.json",
            mime="application/json",
            use_container_width=True
        )
        
    with export_tab3:
        csv_data = export_collection_csv(st.session_state.owned_ids)
        st.download_button(
            label="📊 下載卡匣清單 CSV 檔 (可在 Excel / Google 試算表開啟)",
            data=csv_data.encode('utf-8-sig'),
            file_name="mezastar_my_collection.csv",
            mime="text/csv",
            use_container_width=True
        )

    st.markdown("##### 📥 4. 匯入與還原卡匣 (支援上傳 JSON 檔案或貼上代碼)")
    with st.expander("點此展開【檔案/代碼匯入面板】", expanded=False):
        import_mode = st.radio("匯入模式:", ["合併加入 (保留現有卡匣並加入新卡匣)", "完全覆蓋 (以此清單取代現有卡匣)"], horizontal=True)
        mode_val = "merge" if "合併" in import_mode else "overwrite"
        
        imp_col1, imp_col2 = st.columns(2)
        with imp_col1:
            st.markdown("**方式 1：上傳 JSON 備份檔**")
            uploaded_file = st.file_uploader("選擇 JSON 檔案:", type=["json"], key="uploader_json_tab7")
            if uploaded_file is not None:
                try:
                    file_str = uploaded_file.getvalue().decode("utf-8")
                    temp_ok, temp_msg, parsed_ids = import_collection_from_json(file_str, mode=mode_val)
                    if temp_ok:
                        preview_cards = get_user_cards(parsed_ids)
                        st.info(f"📋 檔案解析成功！內含 **{len(parsed_ids)}** 張卡匣（匹配 **{len(preview_cards)}** 款圖鑑卡匣）")
                        if st.button("🚀 確認匯入並套用至我的卡庫", type="primary", key="btn_apply_file_tab7", use_container_width=True):
                            st.session_state.owned_ids = parsed_ids
                            save_user_collection_ids(parsed_ids)
                            st.success(f"✅ {temp_msg}")
                            st.rerun()
                    else:
                        st.error(f"❌ {temp_msg}")
                except Exception as e:
                    st.error(f"讀取錯誤: {e}")

        with imp_col2:
            st.markdown("**方式 2：貼上分享代碼或卡號**")
            code_input = st.text_area("貼上代碼 (支援 MEZASTAR-V1:... 或逗號分隔編號):", height=80, placeholder="例如: MEZASTAR-V1:... 或 2-2-001, 2-2-002", key="input_code_tab7")
            if code_input.strip():
                temp_ok, temp_msg, parsed_ids = import_collection_from_share_code(code_input, mode=mode_val)
                if temp_ok:
                    preview_cards = get_user_cards(parsed_ids)
                    st.info(f"📋 代碼解析成功！包含 **{len(parsed_ids)}** 張卡匣（匹配 **{len(preview_cards)}** 款圖鑑卡匣）")
                    if st.button("🚀 確認代碼匯入並套用", type="primary", key="btn_apply_code_tab7", use_container_width=True):
                        st.session_state.owned_ids = parsed_ids
                        save_user_collection_ids(parsed_ids)
                        st.success(f"✅ {temp_msg}")
                        st.rerun()
                else:
                    st.error(f"❌ {temp_msg}")

    with st.expander("💡 如何直接在 GitHub 網頁上手動編輯卡匣資料？（圖文教學）", expanded=False):
        st.markdown("""
        **如果您想直接在 GitHub 網頁上手動編輯卡匣存檔：**
        
        1. 點擊開啟：[👉 GitHub 上的 my_collection.json 檔案](https://github.com/JeffHSU8310/pokemonmezastar/blob/main/data/my_collection.json)
        2. 點擊右上角的 **「鉛筆圖示 ✏️ (Edit this file)」**。
        3. 在中括號 `[` `]` 內填入卡匣編號（雙引號與逗號分隔），例如：
        ```json
        [
          "2-2-001",
          "2-2-002",
          "2-2-005"
        ]
        ```
        4. 點擊右上角綠色按鈕 **「Commit changes...」** ➔ 再次點擊 **「Commit changes」**。
        5. 完成後回到此頁面點擊 **【📥 一鍵自 GitHub 雲端拉取並還原】** 即可同步最新卡匣！
        """)

    st.info("""
    **📱 手機使用小撇步：**
    在手機 Safari 或 Chrome 打開網址後，點擊 **「分享」>「加入主畫面」**，即可像原生 App 一樣全螢幕開啟使用！
    """)
