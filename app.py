"""
Pokemon Mezastar Battle Optimizer & Cloud Card Deck System
寶可夢 Mezastar 智慧對戰推薦系統與雲端卡匣庫 (完整六維數值、寶可能量、相剋弱點/抵抗、全特殊機制)
"""

import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Set
import os

from mezastar_data import (
    TYPES,
    TYPE_COLORS,
    ALL_SERIES_LIST,
    calculate_type_effectiveness,
    get_weaknesses,
    get_full_type_chart_for_defender,
    load_cards,
    save_cards,
    DEFAULT_MEZASTAR_CARDS
)
from recommender import recommend_best_lineup, evaluate_card_performance
from collection_manager import (
    load_user_collection_ids,
    save_user_collection_ids,
    get_user_cards,
    toggle_card_ownership,
    get_collection_stats
)
from scraper import add_custom_card, fetch_online_pokemon_metadata, batch_import_cards
from github_sync import (
    get_git_status,
    auto_commit_and_push,
    load_version_info
)

# 設定頁面資訊與寬版版面
st.set_page_config(
    page_title="寶可夢 Mezastar 智慧對戰陣容推薦系統",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自訂 CSS 樣式增強 UI 美觀
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #E53935;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.1rem;
        color: #555;
        margin-bottom: 1.5rem;
    }
    .card-box {
        border-radius: 12px;
        padding: 14px;
        background: #ffffff;
        border: 2px solid #e9ecef;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
        margin-bottom: 12px;
        transition: transform 0.2s;
    }
    .card-box:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(0,0,0,0.1);
    }
    .type-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 10px;
        color: white;
        font-weight: bold;
        font-size: 0.8rem;
        margin-right: 3px;
        margin-bottom: 3px;
    }
    .energy-badge {
        background: linear-gradient(135deg, #FF6B6B, #FF8E53);
        color: white;
        font-weight: bold;
        padding: 3px 8px;
        border-radius: 8px;
        font-size: 0.85rem;
    }
    .star-badge {
        color: #FFB300;
        font-weight: bold;
        font-size: 1.05rem;
    }
    .tag-badge {
        display: inline-block;
        padding: 2px 6px;
        border-radius: 6px;
        background-color: #f1f3f5;
        color: #333;
        font-size: 0.75rem;
        margin-right: 3px;
        margin-bottom: 3px;
        border: 1px solid #dee2e6;
    }
    .stat-row {
        display: flex;
        justify-content: space-between;
        font-size: 0.8rem;
        color: #495057;
        margin: 2px 0;
    }
</style>
""", unsafe_allow_html=True)

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

# 側邊欄：系統資訊與快捷操作
with st.sidebar:
    st.markdown("### 🎮 Mezastar 對戰小助手")
    ver_info = load_version_info()
    st.caption(f"📌 目前系統版本: **v{ver_info.get('version', '1.0.0')}**")
    st.caption(f"🕒 最後更新: {ver_info.get('last_updated', '')}")
    
    st.markdown("---")
    stats = get_collection_stats(st.session_state.owned_ids)
    st.markdown("#### 📊 我的收藏庫摘要")
    c1, c2 = st.columns(2)
    c1.metric("已持有卡匣", f"{stats['total_owned']} 張")
    c2.metric("6星傳說卡", f"{stats['star_counts'].get(6, 0)} 張")
    
    st.markdown("---")
    st.markdown("#### ⚡ 快速全選/清空收藏")
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
    st.write(f"🔗 遠端: `{git_info['remote_url'].split('/')[-1]}`")
    if git_info["has_changes"]:
        st.warning(f"⚠️ 有 {len(git_info['changed_files'])} 個檔案尚未同步至 GitHub")
    else:
        st.success("✅ 與本機/雲端完全同步")

# 主標題
st.markdown('<div class="main-title">⚡ Pokémon MEZASTAR 智慧對戰推薦系統</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">完整六維體質 • 寶可能量 • 屬性相剋/弱點抵抗 • 全戰鬥機制 (Mega/極巨/Z招/連擊/雙重攻擊) 最佳陣容推薦</div>', unsafe_allow_html=True)

# 頁籤導覽
tabs = st.tabs([
    "⚔️ 智慧對戰推薦 (Battle Lineup)",
    "🎒 我的卡匣庫 (My Collection)",
    "📖 全卡匣圖鑑庫 (Pokedex)",
    "🌐 網路資料擴充 (Web Scraper)",
    "🔄 GitHub 雲端同步 (Git Sync)"
])

# ==============================================================================
# TAB 1: 智慧對戰推薦 (Battle Lineup Optimizer)
# ==============================================================================
with tabs[0]:
    st.subheader("🎯 目標寶可夢 (Boss) 攻擊陣容分析")
    
    col_boss1, col_boss2, col_boss3 = st.columns([2, 2, 1.5])
    
    with col_boss1:
        boss_options = ["自訂目標寶可夢..."] + [f"{c['name']} ({c['series']} - {c['id']}) [能量:{c.get('energy', 100)}]" for c in all_cards]
        selected_boss_idx = st.selectbox("選擇對手 Boss (或選自訂):", options=range(len(boss_options)), format_func=lambda x: boss_options[x])
        
        if selected_boss_idx == 0:
            boss_name = st.text_input("輸入對手寶可夢名稱:", value="超夢")
            default_t1 = "超能力"
            default_t2 = "無"
        else:
            picked_c = all_cards[selected_boss_idx - 1]
            boss_name = picked_c["name"]
            default_t1 = picked_c["types"][0] if len(picked_c["types"]) > 0 else "一般"
            default_t2 = picked_c["types"][1] if len(picked_c["types"]) > 1 else "無"

    with col_boss2:
        type_options = ["無"] + TYPES
        t1_idx = TYPES.index(default_t1) if default_t1 in TYPES else 0
        boss_type1 = st.selectbox("Boss 第一屬性:", options=TYPES, index=t1_idx)
        
        t2_idx = type_options.index(default_t2) if default_t2 in type_options else 0
        boss_type2 = st.selectbox("Boss 第二屬性 (若有):", options=type_options, index=t2_idx)

    with col_boss3:
        boss_move_type = st.selectbox("Boss 攻擊招式屬性 (可選，計算我方防禦):", options=["未指定/自動評估"] + TYPES, index=0)
        actual_move_type = None if boss_move_type == "未指定/自動評估" else boss_move_type
        search_scope = st.radio("候選卡匣來源:", options=["從我擁有的卡匣中挑選", "從全卡匣圖鑑中挑選"], index=0)

    # 組合 Boss 屬性
    boss_types = [boss_type1]
    if boss_type2 != "無" and boss_type2 != boss_type1:
        boss_types.append(boss_type2)

    # 顯示 Boss 屬性與弱點分析
    st.markdown("---")
    c_info1, c_info2 = st.columns([1, 3])
    with c_info1:
        st.markdown(f"#### 👾 目標：**{boss_name}**")
        st.markdown(f"屬性：{render_types_html(boss_types)}", unsafe_allow_html=True)
    
    with c_info2:
        full_chart = get_full_type_chart_for_defender(boss_types)
        weak_4x = [k for k, v in full_chart.items() if v >= 4.0]
        weak_2x = [k for k, v in full_chart.items() if v == 2.0]
        resist = [k for k, v in full_chart.items() if 0.0 < v <= 0.5]
        immune = [k for k, v in full_chart.items() if v == 0.0]
        
        w_html = "<div>"
        if weak_4x:
            w_html += f"<b>💥 4倍極限弱點：</b> {''.join([render_type_badge(t) for t in weak_4x])} &nbsp;&nbsp;"
        if weak_2x:
            w_html += f"<b>🎯 2倍弱點：</b> {''.join([render_type_badge(t) for t in weak_2x])} &nbsp;&nbsp;"
        if resist:
            w_html += f"<br><b>🛡️ 抵抗屬性 (傷害減半)：</b> {''.join([render_type_badge(t) for t in resist])} &nbsp;&nbsp;"
        if immune:
            w_html += f"<b>🚫 無效/極低傷害：</b> {''.join([render_type_badge(t) for t in immune])}"
        w_html += "</div>"
        st.markdown(w_html, unsafe_allow_html=True)

    st.markdown("---")

    # 決定候選卡匣
    if search_scope == "從我擁有的卡匣中挑選":
        candidates = get_user_cards(st.session_state.owned_ids)
        source_label = f"我的收藏庫 (共 {len(candidates)} 張卡匣)"
    else:
        candidates = all_cards
        source_label = f"全卡匣圖鑑庫 (共 {len(candidates)} 張卡匣)"

    # 執行推薦
    result = recommend_best_lineup(
        user_cards=candidates,
        boss_types=boss_types,
        boss_name=boss_name,
        boss_move_type=actual_move_type,
        team_size=3
    )

    if not result.get("recommended_team"):
        st.warning(f"⚠️ {result.get('message', '未找到合適的推薦卡匣！')}")
    else:
        st.markdown(f"### 🏆 最佳黃金出戰陣容 (Top 3 推薦) — *資料來源: {source_label}*")
        
        team_cols = st.columns(3)
        for idx, rec in enumerate(result["recommended_team"]):
            c = rec["card"]
            with team_cols[idx]:
                sec_move = c.get("second_move", {})
                sec_move_html = f"<div style='font-size:0.8rem; color:#666;'>副招: {sec_move.get('name')} ({sec_move.get('type')}) [威力:{sec_move.get('power')}]</div>" if sec_move else ""
                
                st.markdown(f"""
                <div class="card-box" style="border-top: 5px solid {TYPE_COLORS.get(rec['best_move_type'], '#E53935')};">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span class="star-badge">{'⭐' * c.get('star', 5)} ({c.get('star', 5)}星)</span>
                        <span class="energy-badge">⚡ 能量: {c.get('energy', 100)}</span>
                    </div>
                    <div style="text-align: center; margin: 8px 0;">
                        <img src="{c.get('image', '')}" style="width: 95px; height: 95px; object-fit: contain;">
                        <h4 style="margin: 4px 0;">{c.get('name')}</h4>
                        <div style="font-size: 0.8rem; color: #888;">{c.get('series', '')} • {c.get('id', '')}</div>
                    </div>
                    <div style="margin-bottom: 6px;">
                        <b>卡匣屬性：</b> {render_types_html(c.get('types', []))}
                    </div>
                    <div style="margin-bottom: 6px;">
                        <b>出戰最佳招式：</b> <b>{rec['best_move_name']}</b> {render_type_badge(rec['best_move_type'])} [威力: {rec['best_move_power']}]
                        {sec_move_html}
                    </div>
                    <div style="background: #f8f9fa; padding: 6px 10px; border-radius: 8px; margin-bottom: 6px;">
                        <div style="display: flex; justify-content: space-between;">
                            <span>💥 <b>對Boss相剋倍率:</b></span>
                            <span style="color: #E53935; font-weight: bold; font-size: 1.05rem;">{rec['type_mult']}x</span>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span>⚡ <b>綜合傷害戰力值:</b></span>
                            <span style="font-weight: bold; color: #1E88E5;">{rec['damage_score']} pts</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: #666;">
                            <span>🛡️ 防禦生存係數:</span>
                            <span>{rec['survival_score']} pts</span>
                        </div>
                    </div>
                    <div style="font-size: 0.8rem; margin-bottom: 6px;">
                        <b>六維體質：</b>
                        <div class="stat-row">
                            <span>HP: <b>{c.get('hp')}</b> | 速度: <b>{c.get('spd')}</b></span>
                            <span>物攻: <b>{c.get('atk')}</b> | 特攻: <b>{c.get('sp_atk')}</b></span>
                        </div>
                        <div class="stat-row">
                            <span>物防: <b>{c.get('def')}</b> | 特防: <b>{c.get('sp_def')}</b></span>
                        </div>
                    </div>
                    <div style="margin-top: 4px;">
                        {' '.join([f'<span class="tag-badge">{t}</span>' for t in rec['tags']])}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("### 💡 實戰策略與出招指南")
        for t_msg in result.get("tactics", []):
            st.info(t_msg)

        # 完整候選打手戰力排行表
        with st.expander("📊 檢視所有候選卡匣綜合戰力排行榜 (完整數據表格)"):
            rank_data = []
            for r_idx, rec in enumerate(result.get("all_ranked", [])):
                c = rec["card"]
                rank_data.append({
                    "排名": r_idx + 1,
                    "卡匣名稱": c.get("name"),
                    "星級": f"{c.get('star')}⭐",
                    "能量": c.get("energy", 100),
                    "彈別編號": f"{c.get('series')} {c.get('id')}",
                    "屬性": "/".join(c.get("types", [])),
                    "最佳招式": f"{rec['best_move_name']} ({rec['best_move_type']})",
                    "招式威力": rec['best_move_power'],
                    "剋制倍率": f"{rec['type_mult']}x",
                    "特殊機制": ", ".join(c.get("special_mechanics", [c.get("special", "無")])),
                    "傷害戰力評分": rec["damage_score"],
                    "弱點屬性": ", ".join(c.get("weaknesses", [])),
                    "抵抗屬性": ", ".join(c.get("resistances", []))
                })
            df_rank = pd.DataFrame(rank_data)
            st.dataframe(df_rank, use_container_width=True)

# ==============================================================================
# TAB 2: 我的卡匣庫 (My Collection)
# ==============================================================================
with tabs[1]:
    st.subheader("🎒 我的卡匣收藏管理")
    st.caption("在此勾選您實際擁有的卡匣，對戰推薦系統將優先為您搭配您手中的實體卡！")
    
    col_f1, col_f2, col_f3, col_f4 = st.columns([1.5, 1.5, 1.5, 2])
    with col_f1:
        star_filter = st.multiselect("星級篩選:", options=[6, 5, 4, 3, 2, 1], default=[6, 5])
    with col_f2:
        all_series = [s for s in ALL_SERIES_LIST if any(c.get("series") == s for c in all_cards)]
        series_filter = st.multiselect("彈別篩選:", options=all_series, default=all_series)
    with col_f3:
        status_filter = st.selectbox("擁有狀態:", options=["全部卡匣", "僅顯示已擁有", "僅顯示未擁有"], index=0)
    with col_f4:
        keyword = st.text_input("🔍 搜尋名稱、編號或特殊機制:", value="")

    # 篩選卡匣
    filtered_cards = []
    for c in all_cards:
        if c.get("star", 5) not in star_filter:
            continue
        if c.get("series", "") not in series_filter:
            continue
        is_owned = c.get("id") in st.session_state.owned_ids
        if status_filter == "僅顯示已擁有" and not is_owned:
            continue
        if status_filter == "僅顯示未擁有" and is_owned:
            continue
        if keyword:
            k_lower = keyword.lower()
            name_match = k_lower in c.get("name", "").lower()
            id_match = k_lower in c.get("id", "").lower()
            mech_match = any(k_lower in m.lower() for m in c.get("special_mechanics", []))
            if not (name_match or id_match or mech_match):
                continue
        filtered_cards.append(c)

    st.write(f"📋 共符合 **{len(filtered_cards)}** 張卡匣：")

    # 卡匣網格陳列與勾選
    card_cols = st.columns(4)
    for i, c in enumerate(filtered_cards):
        c_id = c["id"]
        is_owned = c_id in st.session_state.owned_ids
        
        with card_cols[i % 4]:
            border_color = "#E53935" if is_owned else "#E0E0E0"
            bg_color = "#FFF8F8" if is_owned else "#FFFFFF"
            
            mechs_str = ", ".join(c.get("special_mechanics", [c.get("special", "無")]))
            weak_str = ", ".join(c.get("weaknesses", []))
            
            st.markdown(f"""
            <div class="card-box" style="border: 2px solid {border_color}; background-color: {bg_color}; min-height: 290px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span class="star-badge">{'⭐' * c.get('star', 5)}</span>
                    <span class="energy-badge">⚡ {c.get('energy', 100)}</span>
                </div>
                <div style="text-align: center; margin: 4px 0;">
                    <img src="{c.get('image', '')}" style="width: 70px; height: 70px; object-fit: contain;">
                    <div style="font-weight: bold; font-size: 1.05rem;">{c.get('name')}</div>
                    <div style="font-size: 0.75rem; color: #666;">{c.get('series')} • {c.get('id')}</div>
                </div>
                <div style="margin: 3px 0;">{render_types_html(c.get('types', []))}</div>
                <div style="font-size: 0.8rem;">招式: <b>{c.get('move_name')}</b> ({c.get('move_type')}) [{c.get('move_power')}]</div>
                <div style="font-size: 0.75rem; color: #555;">體質: HP {c.get('hp')} | 攻 {c.get('atk')} | 防 {c.get('def')} | 速 {c.get('spd')}</div>
                <div style="font-size: 0.75rem; color: #0288D1;">機制: {mechs_str}</div>
            </div>
            """, unsafe_allow_html=True)
            
            btn_label = "✅ 已擁有 (點擊取消)" if is_owned else "➕ 標記為擁有"
            btn_type = "primary" if is_owned else "secondary"
            if st.button(btn_label, key=f"btn_own_{c_id}", use_container_width=True, type=btn_type):
                st.session_state.owned_ids = toggle_card_ownership(c_id, st.session_state.owned_ids)
                st.rerun()

# ==============================================================================
# TAB 3: 全卡匣圖鑑庫 (Pokedex)
# ==============================================================================
with tabs[2]:
    st.subheader("📖 寶可夢 Mezastar 全卡匣完整數據圖鑑庫")
    
    df_all = pd.DataFrame([{
        "編號 (ID)": c.get("id"),
        "名稱": c.get("name"),
        "彈別": c.get("series"),
        "星級": f"{c.get('star')}⭐",
        "寶可能量": c.get("energy", 100),
        "屬性": " / ".join(c.get("types", [])),
        "主要招式": c.get("move_name"),
        "招式屬性": c.get("move_type"),
        "招式威力": c.get("move_power"),
        "HP": c.get("hp"),
        "物攻": c.get("atk"),
        "物防": c.get("def"),
        "特攻": c.get("sp_atk"),
        "特防": c.get("sp_def"),
        "速度": c.get("spd"),
        "弱點屬性": ", ".join(c.get("weaknesses", [])),
        "抵抗屬性": ", ".join(c.get("resistances", [])),
        "特殊戰鬥機制": ", ".join(c.get("special_mechanics", [c.get("special", "無")])),
        "Mega進化": "✔️" if c.get("has_mega") else "—",
        "Z招式": "✔️" if c.get("has_z_move") else "—",
        "超極巨化": "✔️" if c.get("has_gigantamax") else "—",
        "極巨化": "✔️" if c.get("has_dynamax") else "—",
        "雙重攻擊": "✔️" if c.get("has_double_attack") else "—",
        "連擊卡匣": "✔️" if c.get("has_chain_attack") else "—",
        "太晶化": "✔️" if c.get("has_terastal") else "—"
    } for c in all_cards])
    
    st.dataframe(df_all, use_container_width=True)

# ==============================================================================
# TAB 4: 網路資料擴充與爬蟲 (Web Scraper & PokeAPI)
# ==============================================================================
with tabs[3]:
    st.subheader("🌐 網路搜尋與新增/匯入卡匣資料")
    
    col_net1, col_net2 = st.columns(2)
    
    with col_net1:
        st.markdown("#### 🔍 1. 線上查詢寶可夢官方資料庫 (PokeAPI 自動填入)")
        poke_query = st.text_input("輸入欲抓取的寶可夢名稱 (例如: 密勒頓, 固拉多, 妙蛙花):", value="超夢")
        if st.button("🌐 從網路獲取資料並預覽", use_container_width=True):
            with st.spinner("正在聯網抓取資料中..."):
                meta = fetch_online_pokemon_metadata(poke_query)
                if meta:
                    st.success(f"✅ 成功獲取 {meta['name']} 網路數據！")
                    st.json(meta)
                    if meta.get("image"):
                        st.image(meta["image"], width=120)
                else:
                    st.error("❌ 查無此寶可夢資料，請確認名稱是否正確。")

    with col_net2:
        st.markdown("#### ➕ 2. 新增 / 更新自訂卡匣至資料庫")
        with st.form("add_card_form"):
            f_id = st.text_input("卡匣編號 (ID，例: 4-2-001):", value="4-2-001")
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
            f_img = st.text_input("卡片圖片 URL (可選):", value="https://img.pokemondb.net/sprites/home/normal/zacian.png")
            
            submitted = st.form_submit_button("💾 儲存並加入卡匣庫", use_container_width=True)
            if submitted:
                types_list = [f_t1]
                if f_t2 != "無" and f_t2 != f_t1:
                    types_list.append(f_t2)
                
                new_card_dict = {
                    "id": f_id.strip(),
                    "name": f_name.strip(),
                    "series": f_series,
                    "star": f_star,
                    "energy": f_energy,
                    "types": types_list,
                    "hp": 190,
                    "atk": 160,
                    "def": 140,
                    "sp_atk": 160,
                    "sp_def": 140,
                    "spd": 150,
                    "move_name": f_move.strip(),
                    "move_type": f_mtype,
                    "move_power": f_mpower,
                    "special": f_special[0] if f_special else "無",
                    "special_mechanics": f_special,
                    "image": f_img.strip()
                }
                ok, msg = add_custom_card(new_card_dict)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

# ==============================================================================
# TAB 5: GitHub 雲端同步 (Git Sync & Cloud Deployment)
# ==============================================================================
with tabs[4]:
    st.subheader("🔄 GitHub 自動版本記錄與雲端回併同步")
    st.caption("支援將本機新增的卡匣、修改的資料自動建立版次 Commit，並自動回併推送至 GitHub main 分支！")
    
    col_git1, col_git2 = st.columns(2)
    
    with col_git1:
        st.markdown("#### 📦 當前 Git 與版次狀態")
        g_info = get_git_status()
        st.write(f"• **版次號碼:** `v{g_info['version']}`")
        st.write(f"• **最後更新時間:** `{g_info['last_updated']}`")
        st.write(f"• **Git 分支:** `{g_info['branch']}`")
        st.write(f"• **最新 Commit ID:** `{g_info['commit']}`")
        st.write(f"• **GitHub 遠端倉庫:** `{g_info['remote_url']}`")
        
        if g_info["has_changes"]:
            st.warning(f"📝 偵測到有 {len(g_info['changed_files'])} 處檔案變更待同步：")
            for f in g_info["changed_files"][:5]:
                st.code(f, language="text")
        else:
            st.success("✨ 所有本機檔案與版次均已完成提交！")

        st.markdown("---")
        commit_summary = st.text_input("修改摘要說明 (例如: 全面收錄寶可能量、六維體質、弱點抵抗與全戰鬥機制):", value="全面收錄寶可能量、六維體質、弱點抵抗與全戰鬥機制")
        if st.button("🚀 立即建立版次並同步至 GitHub main", use_container_width=True, type="primary"):
            with st.spinner("正在執行 Git Commit、記錄版次與推送至 GitHub..."):
                success, sync_msg = auto_commit_and_push(change_summary=commit_summary, branch="main")
                if success:
                    st.success(sync_msg)
                    st.rerun()
                else:
                    st.error(sync_msg)

    with col_git2:
        st.markdown("#### ☁️ 如何在雲端/手機上永久免費運行此程式？")
        st.info("""
        **推薦方式：Streamlit Community Cloud (100% 免費 & 隨開即用)**
        
        1. 登入 [share.streamlit.io](https://share.streamlit.io/) 並連結您的 GitHub 帳號。
        2. 點擊 **「Create app」**。
        3. 選擇 Repository: `JeffHSU8310/pokemonmezastar`。
        4. Branch: `main`，Main file path: `app.py`。
        5. 點擊 **「Deploy」**！
        6. 完成後即可獲得專屬網址（例如：`https://pokemonmezastar.streamlit.app`），隨時隨地用手機或電腦打開使用！
        """)
        
        st.markdown("#### 📜 版次更新歷史紀錄")
        v_data = load_version_info()
        for item in v_data.get("history", [])[:6]:
            st.markdown(f"- **v{item.get('version')}** (`{item.get('timestamp')}`) : {item.get('message')}")
