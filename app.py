"""
Pokemon Mezastar Battle Optimizer & Cloud Card Deck System
寶可夢 Mezastar 智慧對戰推薦系統與雲端卡匣庫
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
        border: 2px solid #f0f0f0;
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
        padding: 3px 10px;
        border-radius: 12px;
        color: white;
        font-weight: bold;
        font-size: 0.85rem;
        margin-right: 4px;
        margin-bottom: 4px;
    }
    .star-badge {
        color: #FFB300;
        font-weight: bold;
        font-size: 1.05rem;
    }
    .tag-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 6px;
        background-color: #f1f3f5;
        color: #333;
        font-size: 0.8rem;
        margin-right: 4px;
        border: 1px solid #dee2e6;
    }
    .stat-badge {
        font-size: 0.85rem;
        color: #666;
        background: #f8f9fa;
        padding: 4px 8px;
        border-radius: 6px;
        display: inline-block;
        margin: 2px;
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
    all_cards = load_cards()
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
st.markdown('<div class="sub-title">精準屬性相剋倍率計算 • 最佳爆發傷害隊伍推薦 • 個人卡匣雲端庫</div>', unsafe_allow_html=True)

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
        # 從資料庫中快速挑選已知 Boss，或手動自訂
        boss_options = ["自訂目標寶可夢..."] + [f"{c['name']} ({c['series']} - {c['id']})" for c in all_cards]
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
        weaknesses = get_weaknesses(boss_types)
        weak_4x = [k for k, v in weaknesses.items() if v >= 4.0]
        weak_2x = [k for k, v in weaknesses.items() if v == 2.0]
        resist = [k for k, v in weaknesses.items() if v <= 0.5 and v > 0.0]
        immune = [k for k, v in weaknesses.items() if v == 0.0]
        
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
        candidate_cards=candidates,
        boss_types=boss_types,
        boss_name=boss_name,
        boss_move_type=actual_move_type,
        team_size=3
    )

    if not result["success"]:
        st.warning(f"⚠️ {result['message']}")
    else:
        st.markdown(f"### 🏆 最佳黃金出戰陣容 (Top 3 推薦) — *資料來源: {source_label}*")
        
        team_cols = st.columns(3)
        for idx, rec in enumerate(result["top_team"]):
            c = rec["card"]
            with team_cols[idx]:
                st.markdown(f"""
                <div class="card-box" style="border-top: 5px solid {TYPE_COLORS.get(c.get('move_type', '一般'), '#E53935')};">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span class="star-badge">{'⭐' * c.get('star', 5)} ({c.get('star', 5)}星)</span>
                        <span style="font-weight: bold; color: #888; font-size: 0.85rem;">#{idx + 1} 推薦順位</span>
                    </div>
                    <div style="text-align: center; margin: 10px 0;">
                        <img src="{c.get('image', '')}" style="width: 100px; height: 100px; object-fit: contain;">
                        <h4 style="margin: 5px 0;">{c.get('name')}</h4>
                        <div style="font-size: 0.8rem; color: #888;">{c.get('series', '')} • {c.get('id', '')}</div>
                    </div>
                    <div style="margin-bottom: 8px;">
                        <b>卡匣屬性：</b> {render_types_html(c.get('types', []))}
                    </div>
                    <div style="margin-bottom: 8px;">
                        <b>主要招式：</b> {c.get('move_name')} {render_type_badge(c.get('move_type', '一般'))}
                    </div>
                    <div style="background: #f8f9fa; padding: 8px; border-radius: 8px; margin-bottom: 8px;">
                        <div style="display: flex; justify-content: space-between;">
                            <span>💥 <b>屬性相剋倍率:</b></span>
                            <span style="color: #E53935; font-weight: bold; font-size: 1.1rem;">{rec['type_mult']}x</span>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span>⚡ <b>綜合戰力指數:</b></span>
                            <span style="font-weight: bold; color: #1E88E5;">{rec['damage_score']} pts</span>
                        </div>
                    </div>
                    <div>
                        {' '.join([f'<span class="tag-badge">{t}</span>' for t in rec['tags']])}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("### 💡 實戰策略與出招指南")
        st.info(result["strategy"])

        # 完整候選打手戰力排行表
        with st.expander("📊 檢視所有候選卡匣綜合戰力排行榜 (完整數據表格)"):
            rank_data = []
            for r_idx, rec in enumerate(result["recommendations"]):
                c = rec["card"]
                rank_data.append({
                    "排名": r_idx + 1,
                    "卡匣名稱": c.get("name"),
                    "星級": f"{c.get('star')}⭐",
                    "彈別編號": f"{c.get('series')} {c.get('id')}",
                    "屬性": "/".join(c.get("types", [])),
                    "招式": c.get("move_name"),
                    "招式屬性": c.get("move_type"),
                    "相剋倍率": f"{rec['type_mult']}x",
                    "特殊機制": c.get("special", "無"),
                    "綜合評分": rec["damage_score"]
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
        star_filter = st.multiselect("星級篩選:", options=[6, 5, 4, 3, 2], default=[6, 5])
    with col_f2:
        all_series = [s for s in ALL_SERIES_LIST if any(c.get("series") == s for c in all_cards)]
        series_filter = st.multiselect("彈別篩選:", options=all_series, default=all_series)
    with col_f3:
        status_filter = st.selectbox("擁有狀態:", options=["全部卡匣", "僅顯示已擁有", "僅顯示未擁有"], index=0)
    with col_f4:
        keyword = st.text_input("🔍 搜尋名稱或編號:", value="")

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
            if keyword.lower() not in c.get("name", "").lower() and keyword.lower() not in c.get("id", "").lower():
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
            
            st.markdown(f"""
            <div class="card-box" style="border: 2px solid {border_color}; background-color: {bg_color}; min-height: 240px;">
                <div style="display: flex; justify-content: space-between;">
                    <span class="star-badge">{'⭐' * c.get('star', 5)}</span>
                    <span style="font-size: 0.8rem; color: #888;">{c.get('id')}</span>
                </div>
                <div style="text-align: center; margin: 5px 0;">
                    <img src="{c.get('image', '')}" style="width: 70px; height: 70px; object-fit: contain;">
                    <div style="font-weight: bold; font-size: 1.05rem;">{c.get('name')}</div>
                    <div style="font-size: 0.75rem; color: #666;">{c.get('series')}</div>
                </div>
                <div style="margin: 4px 0;">{render_types_html(c.get('types', []))}</div>
                <div style="font-size: 0.85rem;">招式: <b>{c.get('move_name')}</b> ({c.get('move_type')})</div>
                <div style="font-size: 0.8rem; color: #888;">特殊: {c.get('special', '無')}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # 勾選按鈕
            btn_label = "✅ 已擁有 (點擊取消)" if is_owned else "➕ 標記為擁有"
            btn_type = "primary" if is_owned else "secondary"
            if st.button(btn_label, key=f"btn_own_{c_id}", use_container_width=True, type=btn_type):
                st.session_state.owned_ids = toggle_card_ownership(c_id, st.session_state.owned_ids)
                st.rerun()

# ==============================================================================
# TAB 3: 全卡匣圖鑑庫 (Pokedex)
# ==============================================================================
with tabs[2]:
    st.subheader("📖 寶可夢 Mezastar 全卡匣圖鑑資料庫")
    
    df_all = pd.DataFrame([{
        "編號 (ID)": c.get("id"),
        "名稱": c.get("name"),
        "彈別": c.get("series"),
        "星級": f"{c.get('star')}⭐",
        "屬性": " / ".join(c.get("types", [])),
        "招式名稱": c.get("move_name"),
        "招式屬性": c.get("move_type"),
        "招式威力": c.get("move_power"),
        "HP": c.get("hp"),
        "物攻": c.get("atk"),
        "物防": c.get("def"),
        "特攻": c.get("sp_atk"),
        "特防": c.get("sp_def"),
        "速度": c.get("spd"),
        "特殊機制": c.get("special", "無")
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
            f_star = st.slider("星級:", min_value=2, max_value=6, value=6)
            f_t1 = st.selectbox("第一屬性:", options=TYPES, index=17)
            f_t2 = st.selectbox("第二屬性 (若無選無):", options=["無"] + TYPES, index=17)
            f_move = st.text_input("招式名稱:", value="巨獸斬")
            f_mtype = st.selectbox("招式屬性:", options=TYPES, index=16)
            f_mpower = st.number_input("招式威力:", min_value=50, max_value=250, value=175)
            f_special = st.selectbox("特殊機制:", options=["無", "超極巨化", "極巨化", "超級進化", "Z招式", "太晶化", "雙重衝刺", "雙重招式", "連擊", "原始回歸"])
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
                    "types": types_list,
                    "hp": 190,
                    "atk": 150,
                    "def": 130,
                    "sp_atk": 180,
                    "sp_def": 130,
                    "spd": 150,
                    "move_name": f_move.strip(),
                    "move_type": f_mtype,
                    "move_power": f_mpower,
                    "special": f_special,
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
        commit_summary = st.text_input("修改摘要說明 (例如: 更新第GS3彈卡匣與個人收藏):", value="更新寶可夢卡匣與對戰設定")
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
