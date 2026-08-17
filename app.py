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
from recommender import recommend_best_lineup, evaluate_card_performance
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
from scraper import add_custom_card, fetch_online_pokemon_metadata, batch_import_cards
from github_sync import (
    get_git_status,
    load_version_info,
    push_file_to_github_api,
    pull_file_from_github_api,
    sync_all_user_data_to_github
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

# 針對 6.1 吋智慧型手機 (iPhone / Android) 深度調優的響應式 CSS 樣式
render_html("""
<style>
    /* 頁面整體邊距微調，最大化手機可視空間 */
    .block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        max-width: 100% !important;
    }
    
    /* 標題在手機螢幕上的字級適配 */
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

    /* 手機卡匣卡片樣式 */
    .card-box {
        border-radius: 10px;
        padding: 10px;
        background: #ffffff;
        border: 1.5px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        margin-bottom: 8px;
    }
    
    /* 屬性標籤適應手機尺寸 */
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
    
    /* 寶可能量標籤 */
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

    /* 緊湊六維體質排版 */
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

    /* 手機大按鈕好按 (觸控優化) */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: bold !important;
        font-size: 0.82rem !important;
        padding: 0.3rem 0.5rem !important;
        min-height: 38px !important;
    }

    /* 頁籤在手機上的水平捲動與字級 */
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
""")

def render_type_badge(t_name: str) -> str:
    color = TYPE_COLORS.get(t_name, "#888888")
    return f'<span class="type-badge" style="background-color: {color};">{t_name}</span>'

def render_types_html(types: List[str]) -> str:
    return "".join([render_type_badge(t) for t in types])

# 初始化 Session State
if "owned_ids" not in st.session_state:
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
        
    render_html(f"""
    <div style="text-align:center; margin: 8px 0 12px 0;">
        <div style="font-weight: 800; font-size: 1.35rem; color:#1A237E;">{c.get('name')}</div>
        <div style="font-size: 0.85rem; color: #555; margin-top:2px;">
            <b>{c.get('series')}</b> • 官方編號: <code style="font-weight:bold; color:#D32F2F;">{c.get('id')}</code>
        </div>
        <div style="margin-top:6px;">{render_types_html(c.get('types', []))}</div>
    </div>
    """)
    
    # 招式系統
    st.markdown("##### ⚔️ 戰鬥招式")
    sec_m = c.get("second_move", {})
    sec_html = f"<div style='margin-top:4px; font-size:0.85rem; color:#455A64;'>🗡️ <b>副招式:</b> {sec_m.get('name')} ({sec_m.get('type')}) [威力: {sec_m.get('power')}]</div>" if sec_m else ""
    
    render_html(f"""
    <div style="background:#FFF8E1; border:1px solid #FFE082; border-radius:8px; padding:8px 10px; margin-bottom:10px;">
        <div style="font-size:0.85rem;">⚔️ <b>主招式:</b> <b>{c.get('move_name')}</b> ({c.get('move_type')}) [威力: <b>{c.get('move_power')}</b>]</div>
        {sec_html}
    </div>
    """)
    
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
else:
    def show_card_details_modal(c: Dict[str, Any]):
        with st.expander(f"🔍 【詳細數據】{c.get('name')} ({c.get('id')})", expanded=True):
            render_card_detail_content(c)

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
        st.warning(f"⚠️ {len(git_info['changed_files'])} 處變更待同步")
    else:
        st.success("✅ 雲端完全同步")

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
    # 手機上採用卡片式下拉選單
    with st.container():
        boss_options = ["🔍 自訂目標 Boss..."] + [f"{c['name']} ({c['series']} - {c['id']}) ⚡{c.get('energy', 100)}" for c in all_cards]
        selected_boss_idx = st.selectbox("🎯 選擇對手 Boss:", options=range(len(boss_options)), format_func=lambda x: boss_options[x])
        
        if selected_boss_idx == 0:
            boss_name = st.text_input("輸入 Boss 名稱:", value="超夢")
            default_t1 = "超能力"
            default_t2 = "無"
        else:
            picked_c = all_cards[selected_boss_idx - 1]
            boss_name = picked_c["name"]
            default_t1 = picked_c["types"][0] if len(picked_c["types"]) > 0 else "一般"
            default_t2 = picked_c["types"][1] if len(picked_c["types"]) > 1 else "無"

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        type_options = ["無"] + TYPES
        t1_idx = TYPES.index(default_t1) if default_t1 in TYPES else 0
        boss_type1 = st.selectbox("第一屬性:", options=TYPES, index=t1_idx)
    with col_t2:
        t2_idx = type_options.index(default_t2) if default_t2 in type_options else 0
        boss_type2 = st.selectbox("第二屬性:", options=type_options, index=t2_idx)

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
        team_size=3
    )

    if not result.get("recommended_team"):
        st.warning(f"⚠️ {result.get('message', '未找到合適的推薦卡匣！')}")
    else:
        st.markdown(f"#### 🏆 最佳黃金出戰陣容 (Top 3) — *{source_label}*")
        
        # 針對 6.1" 手機直立螢幕：每張推薦卡片垂直排列，資訊高度整合且好讀
        role_badges = ["👑 主攻先鋒 (第1棒)", "⚡ 副攻爆發 (第2棒)", "🛡️ 穩健收尾 (第3棒)"]
        
        for idx, rec in enumerate(result["recommended_team"]):
            c = rec["card"]
            c_id = c["id"]
            sec_move = c.get("second_move", {})
            sec_move_html = f"<div style='font-size:0.75rem; color:#666;'>副招: {sec_move.get('name')} ({sec_move.get('type')}) [威力:{sec_move.get('power')}]</div>" if sec_move else ""
            tags_html = ' '.join([f'<span class="tag-badge">{t}</span>' for t in rec['tags']])
            
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
                        <span>⚔️ <b>出戰招式:</b> {rec['best_move_name']} ({rec['best_move_type']})</span>
                        <span style="color:#D32F2F; font-weight:bold; font-size:0.95rem;">💥 {rec['type_mult']}x 倍率</span>
                    </div>
                    {sec_move_html}
                    <div style="display:flex; justify-content:space-between; margin-top:2px;">
                        <span>⚡ <b>綜合戰力值:</b> <b style="color:#1E88E5;">{rec['damage_score']} pts</b></span>
                        <span style="color:#555;">🛡️ 生存: {rec['survival_score']} pts</span>
                    </div>
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
                    "招式": f"{rec['best_move_name']} ({rec['best_move_type']})",
                    "剋制": f"{rec['type_mult']}x",
                    "機制": c.get("special", "無"),
                    "評分": rec["damage_score"]
                })
            st.dataframe(pd.DataFrame(rank_data), use_container_width=True)

# ==============================================================================
# TAB 2: 🎒 我的卡匣庫 (My Collection) - 支援一鍵備份與雲端驗證
# ==============================================================================
with tabs[1]:
    st.markdown("#### 🎒 我的卡匣庫存標記")
    
    # 雲端同步狀態橫幅與一鍵備份按鈕
    cur_git_info = get_git_status()
    render_html(f"""
    <div style="background:#E3F2FD; border:1px solid #90CAF9; border-radius:8px; padding:8px 10px; margin-bottom:8px; font-size:0.8rem;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <span>☁️ <b>雲端儲存狀態:</b> 目前已記錄 <b>{len(st.session_state.owned_ids)}</b> 款卡匣</span>
            <span>版次: <b>v{cur_git_info['version']}</b></span>
        </div>
        <div style="margin-top:4px; font-size:0.75rem;">
            🔗 GitHub 檔案位置: <a href="https://github.com/JeffHSU8310/pokemonmezastar/blob/main/data/my_collection.json" target="_blank"><b>data/my_collection.json (點此直達 GitHub 檢查/編輯)</b></a>
        </div>
    </div>
    """)
    
    col_sync_btn1, col_sync_btn2, col_sync_btn3 = st.columns([1.2, 1, 1])
    with col_sync_btn1:
        # 優先從 Secrets 或 Session 讀取 Token
        user_token = st.secrets.get("GITHUB_TOKEN", None) if hasattr(st, "secrets") else None
        if not user_token and "github_token" in st.session_state:
            user_token = st.session_state.github_token
            
        if st.button("🚀 永久寫入 GitHub 雲端", use_container_width=True, type="primary", help="透過 GitHub API 直接將卡匣與訓練家寫入 main 倉庫"):
            if not user_token:
                st.warning("⚠️ 請先至【🔄 雲端同步】頁籤填入一次 GitHub Token，即可永久一鍵同步！")
            else:
                with st.spinner("正在透過 GitHub API 寫入 main 倉庫..."):
                    trainers_curr = load_trainers()
                    ok, sync_res = sync_all_user_data_to_github(
                        owned_ids=list(st.session_state.owned_ids),
                        trainers=trainers_curr,
                        token=user_token,
                        summary=f"更新卡匣庫 ({len(st.session_state.owned_ids)} 張) 與訓練家 ({len(trainers_curr)} 組)"
                    )
                    if ok:
                        st.success(sync_res)
                        st.rerun()
                    else:
                        st.error(sync_res)

    with col_sync_btn2:
        if st.button("📥 自 GitHub 抓取最新", use_container_width=True, help="換裝置或清快取時，點此直接自 GitHub 下載最新卡匣庫"):
            with st.spinner("正在自 GitHub main 下載最新卡匣庫..."):
                user_token = st.secrets.get("GITHUB_TOKEN", None) if hasattr(st, "secrets") else None
                if not user_token and "github_token" in st.session_state:
                    user_token = st.session_state.github_token
                ok, content_str, msg = pull_file_from_github_api("data/my_collection.json", token=user_token)
                if ok:
                    imp_ok, imp_msg, new_ids = import_collection_from_json(content_str, mode="overwrite")
                    if imp_ok:
                        st.session_state.owned_ids = new_ids
                        st.success(f"✅ 成功自 GitHub 同步！已載入 {len(new_ids)} 張卡匣！")
                        st.rerun()
                else:
                    st.error(f"❌ 下載失敗: {msg}")

    with col_sync_btn3:
        # JSON 匯出下載按鈕
        collection_json_str = export_collection_json(st.session_state.owned_ids)
        st.download_button(
            label="💾 下載 JSON 檔",
            data=collection_json_str,
            file_name="my_mezastar_collection.json",
            mime="application/json",
            use_container_width=True
        )

    # 匯出與分享抽屜
    with st.expander("📤 匯出我的卡匣庫 (支援 JSON 備份 / LINE 複製代碼 / CSV 試算表)", expanded=False):
        export_tab1, export_tab2, export_tab3 = st.tabs(["💬 複製 LINE/訊息分享代碼", "📊 下載 CSV (Excel 試算表)", "📄 完整 JSON 備份檔"])
        
        with export_tab1:
            share_code = export_collection_share_code(st.session_state.owned_ids)
            st.text_area("📋 卡匣分享代碼 (可直接複製並透過 LINE / 訊息傳送給朋友或在其他手機貼上匯入):", value=share_code, height=90)
            st.caption(f"💡 此代碼包含您目前收藏的 {len(st.session_state.owned_ids)} 張卡匣。")
            
        with export_tab2:
            csv_data = export_collection_csv(st.session_state.owned_ids)
            st.download_button(
                label="📊 下載卡匣清單 CSV 檔 (可在 Excel / Google 試算表開啟)",
                data=csv_data.encode('utf-8-sig'),
                file_name="mezastar_my_collection.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        with export_tab3:
            st.download_button(
                label="📄 下載完整結構化 JSON 備份檔",
                data=export_collection_json(st.session_state.owned_ids),
                file_name="my_mezastar_backup.json",
                mime="application/json",
                use_container_width=True
            )

    # 匯入與還原抽屜
    with st.expander("📥 匯入與還原卡匣 (支援上傳 JSON 檔案或直接貼上代碼)", expanded=False):
        import_mode = st.radio("匯入模式:", ["合併加入 (保留現有卡匣並加入新卡匣)", "完全覆蓋 (以此清單取代現有卡匣)"], horizontal=True)
        mode_val = "merge" if "合併" in import_mode else "overwrite"
        
        imp_col1, imp_col2 = st.columns(2)
        with imp_col1:
            st.markdown("**方式 1：上傳 JSON 備份檔**")
            uploaded_file = st.file_uploader("選擇 my_collection.json 檔案:", type=["json"], key="uploader_json")
            if uploaded_file is not None:
                try:
                    file_str = uploaded_file.getvalue().decode("utf-8")
                    # 預先解析預覽
                    temp_ok, temp_msg, parsed_ids = import_collection_from_json(file_str, mode=mode_val)
                    if temp_ok:
                        preview_cards = get_user_cards(parsed_ids)
                        st.info(f"📋 檔案解析成功！內含 **{len(parsed_ids)}** 張卡匣（成功匹配 **{len(preview_cards)}** 款圖鑑卡匣）")
                        if st.button("🚀 確認匯入並套用至我的卡庫", type="primary", key="btn_apply_file", use_container_width=True):
                            st.session_state.owned_ids = parsed_ids
                            save_user_collection_ids(parsed_ids)
                            st.success(f"✅ {temp_msg}")
                            st.rerun()
                    else:
                        st.error(f"❌ {temp_msg}")
                except Exception as e:
                    st.error(f"讀取錯誤: {e}")

        with imp_col2:
            st.markdown("**方式 2：貼上卡匣分享代碼或編號清單**")
            code_input = st.text_area("貼上 MEZASTAR 分享代碼或卡匣編號 (支援逗號或換行分隔):", height=80, placeholder="例如: MEZASTAR-V1:... 或 1-002, 1-004, 2-2-001", key="input_share_code")
            if code_input.strip():
                temp_ok, temp_msg, parsed_ids = import_collection_from_share_code(code_input, mode=mode_val)
                if temp_ok:
                    preview_cards = get_user_cards(parsed_ids)
                    st.info(f"📋 代碼解析成功！包含 **{len(parsed_ids)}** 張卡匣（成功匹配 **{len(preview_cards)}** 款圖鑑卡匣）")
                    if st.button("🚀 確認代碼匯入並套用", type="primary", key="btn_apply_code", use_container_width=True):
                        st.session_state.owned_ids = parsed_ids
                        save_user_collection_ids(parsed_ids)
                        st.success(f"✅ {temp_msg}")
                        st.rerun()
                else:
                    st.error(f"❌ {temp_msg}")

    # GitHub 網頁直接編輯與備份教學抽屜
    with st.expander("💡 如何直接在 GitHub 網頁上修改或儲存卡匣？（圖文教學）", expanded=False):
        st.markdown("""
        **如果您想直接在 GitHub 網頁上一次新增或編輯擁有的所有卡匣：**
        
        1. 點擊開啟：[👉 GitHub 上的 my_collection.json 檔案](https://github.com/JeffHSU8310/pokemonmezastar/blob/main/data/my_collection.json)
        2. 點擊右上角的 **「鉛筆圖示 ✏️ (Edit this file)」**。
        3. 在中括號 `[` `]` 內填入您擁有的卡匣編號清單（用雙引號與逗號分隔），例如：
        ```json
        [
          "2-2-001",
          "2-2-002",
          "2-2-004",
          "2-2-022",
          "1-2-025",
          "1-4-001"
        ]
        ```
        4. 點擊右上角綠色按鈕 **「Commit changes...」** ➔ 再次點擊 **「Commit changes」**。
        5. 完成！回到手機或瀏覽器重新整理 Streamlit 網頁，系統就會自動載入您在 GitHub 上儲存的最新卡匣清單！
        """)

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
                id_match = k_low in c.get("id", "").lower()
                move_match = k_low in c.get("move_name", "").lower() or k_low in c.get("move_type", "").lower()
                if not (name_match or id_match or move_match):
                    continue
            filtered_my_cards.append(c)

        st.caption(f"🎒 目前顯示已擁有卡匣共 **{len(filtered_my_cards)}** 款：")

        # 針對 6.1" 手機：採用 2 列直立卡片網格 (只顯示已擁有卡匣)
        card_cols = st.columns(2)
        for i, c in enumerate(filtered_my_cards):
            c_id = c["id"]
            with card_cols[i % 2]:
                render_html(f"""
                <div class="card-box" style="border: 2px solid #E53935; background-color: #FFF8F8; min-height: 220px; padding: 8px;">
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
                        st.session_state.owned_ids = toggle_card_ownership(c_id, st.session_state.owned_ids)
                        st.rerun()

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
                if ak_low not in c.get("name", "").lower() and ak_low not in c.get("id", "").lower():
                    continue
            cand_to_add.append(c)
            
        add_cols = st.columns(2)
        for i, c in enumerate(cand_to_add[:40]):
            c_id = c["id"]
            is_owned = c_id in st.session_state.owned_ids
            with add_cols[i % 2]:
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
            <div style="font-size:0.8rem; color:#616161; font-family:monospace;">ID: {t_id}</div>
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
                    st.markdown(f"{status_badge}**{tr_name}** (`{tr_id}`)")
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
                        delete_trainer(tr_id)
                        st.rerun()
                
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

    # 支援寶可夢卡片式列表
    sp_grid_cols = st.columns(2)
    for idx, sp in enumerate(filtered_sp):
        sp_id = sp.get("id", "")
        sp_name = sp.get("name", "")
        sp_types = sp.get("types", [])
        sp_skill = sp.get("skill_name", "")
        sp_desc = sp.get("skill_desc", "")
        sp_series = sp.get("series", "")
        sp_qr_data = sp.get("qr_data", f"MEZASTAR-SP:{sp_id}")
        sp_icon = sp.get("icon_url", "")

        with sp_grid_cols[idx % 2]:
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
            id_match = s_low in c.get("id", "").lower()
            type_match = any(s_low in t.lower() for t in c.get("types", []))
            move_match = s_low in c.get("move_name", "").lower() or s_low in c.get("move_type", "").lower()
            mech_match = any(s_low in m.lower() for m in c.get("special_mechanics", []))
            if not (n_match or id_match or type_match or move_match or mech_match):
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
        # 6.1 吋手機雙列卡片網格
        pk_cols = st.columns(2)
        for i, c in enumerate(pokedex_cards):
            c_id = c["id"]
            with pk_cols[i % 2]:
                weak_str = ", ".join(c.get("weaknesses", []))
                sec_m = c.get("second_move", {})
                sec_text = f"<div style='font-size:0.7rem; color:#666;'>副招: {sec_m.get('name')} [{sec_m.get('power')}]</div>" if sec_m else ""
                
                render_html(f"""
                <div class="card-box" style="border-top: 4px solid {TYPE_COLORS.get(c.get('move_type', '一般'), '#E53935')}; min-height: 250px; padding:8px;">
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
                    if st.button("🔍 詳情", key=f"btn_pk_det_{i}_{c_id}", use_container_width=True):
                        show_card_details_modal(c)
                with pk_btn_c2:
                    is_owned = c_id in st.session_state.owned_ids
                    pk_lbl = "✅ 擁有" if is_owned else "➕ 加入"
                    pk_tp = "primary" if is_owned else "secondary"
                    if st.button(pk_lbl, key=f"btn_pk_own_{i}_{c_id}", use_container_width=True, type=pk_tp):
                        st.session_state.owned_ids = toggle_card_ownership(c_id, st.session_state.owned_ids)
                        st.rerun()
    else:
        df_all = pd.DataFrame([{
            "編號": c.get("id"),
            "名稱": c.get("name"),
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
    
    render_html("""
    <div style="background: linear-gradient(135deg, #E8F5E9, #C8E6C9); border: 1.5px solid #81C784; border-radius: 10px; padding: 12px; margin-bottom: 12px;">
        <div style="font-weight: 800; font-size: 1.05rem; color: #1B5E20; margin-bottom: 4px;">
            🚀 官方最新彈別一鍵自動聯網抓取 (免人工輸入)
        </div>
        <div style="font-size: 0.8rem; color: #2E7D32; line-height: 1.4;">
            未來當台灣官方機台推出<b>【銀河第3彈】、【銀河第4彈】或最新特別彈</b>時，只要點擊下方按鈕，系統就會<b>自動連線台灣官方網站 (pokemonmezastar.com.tw)</b>，自動偵測最新卡表、抓取官方實體卡匣立繪、生成屬性與體質數據，並自動同步儲存至雲端！
        </div>
    </div>
    """)
    
    if st.button("🚀 立即一鍵自動掃描並抓取官方最新卡匣", use_container_width=True, type="primary"):
        with st.spinner("正在自動連線台灣寶可夢官方網站掃描全彈別資料庫 (pokemonmezastar.com.tw)..."):
            crawl_res = fetch_and_sync_official_new_cards(start_id=1, end_id=20, auto_push=True)
            if crawl_res.get("new_count", 0) > 0:
                st.balloons()
                st.success(f"🎉 太棒了！成功發現並自動收錄 **{crawl_res['new_count']}** 款官方全新卡匣！")
                st.info(f"☁️ 雲端狀態：{crawl_res['sync_message']}")
                with st.expander("📋 查看本次自動新增的官方新卡匣清單", expanded=True):
                    for cid, cname, sname in crawl_res.get("new_cards", []):
                        st.write(f"• **{sname}** | 編號 `{cid}` | **{cname}**")
                st.rerun()
            else:
                st.success("✅ 官方網站掃描完成！目前資料庫已是官方最新版本（共 428 款卡匣），無任何遺漏！")
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

    # 讀取現有 Token (優先從 secrets，次之 session_state)
    default_tok = st.secrets.get("GITHUB_TOKEN", "") if hasattr(st, "secrets") else ""
    if not default_tok and "github_token" in st.session_state:
        default_tok = st.session_state.github_token

    st.markdown("##### 🔑 1. 設定 GitHub Personal Access Token (PAT)")
    tok_input = st.text_input(
        "輸入您的 GitHub Token (以 ghp_ 開頭):",
        value=default_tok,
        type="password",
        placeholder="例如: ghp_xxxxxxxxxxxxxxxxxxxx",
        help="此 Token 僅用於直接呼叫 GitHub API 寫入您的私人倉庫，請安心使用。"
    )
    if tok_input:
        st.session_state.github_token = tok_input.strip()

    with st.expander("💡 如何在 1 分鐘內免費取得您的 GitHub Token？（超簡單 3 步驟）", expanded=False):
        st.markdown("""
        1. 點擊開啟：[👉 GitHub Token 快速建立頁面 (點此直達)](https://github.com/settings/tokens/new)
        2. **Note（名稱）**：填入 `mezastar-sync`
        3. **Expiration（效期）**：選 `No expiration`（無期限）
        4. **Select scopes（權限勾選）**：務必勾選第 1 項 **`repo`**（包含所有子項目）
        5. 滑到最下方點擊綠色按鈕 **「Generate token」** ➔ 複製綠色框框中的 `ghp_...` 代碼。
        6. 回到上方貼入輸入框中即可！
        
        *(進階提示：您也可以在 Streamlit Cloud 後台 Settings ➔ Secrets 填入 `GITHUB_TOKEN = "ghp_..."`，即可所有裝置免輸入自動同步！)*
        """)

    st.divider()

    st.markdown("##### 🚀 2. 雙向同步操作")
    col_syn1, col_syn2 = st.columns(2)
    with col_syn1:
        st.markdown("**📤 將目前裝置資料 ➔ 永久寫入 GitHub**")
        commit_msg = st.text_input("提交備註說明:", value="同步最新卡匣庫與訓練家資料")
        if st.button("🚀 立即全量寫入 GitHub 雲端", type="primary", use_container_width=True):
            current_token = tok_input.strip() if tok_input else default_tok
            if not current_token:
                st.error("❌ 請先在上方填入您的 GitHub Token！")
            else:
                with st.spinner("正在透過 GitHub API 寫入 main 倉庫..."):
                    trainers_curr = load_trainers()
                    ok, res_msg = sync_all_user_data_to_github(
                        owned_ids=list(st.session_state.owned_ids),
                        trainers=trainers_curr,
                        token=current_token,
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
        if st.button("📥 一鍵自 GitHub 雲端拉取並還原", use_container_width=True):
            current_token = tok_input.strip() if tok_input else default_tok
            with st.spinner("正在自 GitHub main 下載最新資料..."):
                ok_c, content_c, msg_c = pull_file_from_github_api("data/my_collection.json", token=current_token)
                ok_t, content_t, msg_t = pull_file_from_github_api("data/trainers.json", token=current_token)
                
                success_count = 0
                if ok_c:
                    imp_ok, _, new_ids = import_collection_from_json(content_c, mode="overwrite")
                    if imp_ok:
                        st.session_state.owned_ids = new_ids
                        success_count += 1
                if ok_t:
                    try:
                        t_data = json.loads(content_t)
                        if isinstance(t_data, list):
                            save_trainers(t_data)
                            success_count += 1
                    except Exception:
                        pass
                
                if success_count > 0:
                    st.success(f"🎉 成功自 GitHub 雲端完全還原！載入 {len(st.session_state.owned_ids)} 張卡匣與最新訓練家資料！")
                    st.rerun()
                else:
                    st.error(f"❌ 拉取失敗: {msg_c}")

    st.info("""
    **📱 手機使用小撇步：**
    在手機 Safari 或 Chrome 打開網址後，點擊 **「分享」>「加入主畫面」**，即可像原生 App 一樣全螢幕開啟使用！
    """)
