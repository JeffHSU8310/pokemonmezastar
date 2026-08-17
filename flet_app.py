"""
Pokemon Mezastar Mobile App (Flet / Flutter Engine)
寶可夢 Mezastar 手機專用原生跨平台 APP
100% 純 Python 打造，支援 Android APK / iOS 打包與離線運作。
"""

import flet as ft
from typing import List, Dict, Any, Set
import json
import os

from mezastar_data import (
    TYPES,
    TYPE_COLORS,
    ALL_SERIES_LIST,
    calculate_type_effectiveness,
    get_weaknesses,
    get_full_type_chart_for_defender,
    load_cards
)
from recommender import recommend_best_lineup
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

def main(page: ft.Page):
    page.title = "寶可夢 Mezastar 對戰推薦 APP"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 10
    page.scroll = ft.ScrollMode.AUTO

    # 初始化卡庫狀態
    owned_ids: Set[str] = load_user_collection_ids()
    all_cards: List[Dict[str, Any]] = load_cards()

    # 通知訊息小工具
    def show_toast(message: str, is_error: bool = False):
        snack = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE),
            bgcolor=ft.Colors.RED_700 if is_error else ft.Colors.GREEN_700,
            duration=3000
        )
        page.overlay.append(snack)
        snack.open = True
        page.update()

    # ==============================================================================
    # ⚔️ 頁面 1：對戰推薦 (Battle Optimizer)
    # ==============================================================================
    selected_boss_types: List[str] = ["龍", "飛行"]
    use_my_deck_only = ft.Ref[ft.Switch]()
    recommend_results_col = ft.Column(spacing=10)

    def refresh_recommendations(e=None):
        if not selected_boss_types:
            recommend_results_col.controls = [
                ft.Text("請至少選擇 1 個對手屬性！", color=ft.Colors.ORANGE_800, weight=ft.FontWeight.BOLD)
            ]
            page.update()
            return

        candidate_pool = all_cards
        if use_my_deck_only.current and use_my_deck_only.current.value:
            candidate_pool = [c for c in all_cards if c.get("id") in owned_ids]
            if not candidate_pool:
                recommend_results_col.controls = [
                    ft.Container(
                        content=ft.Text("⚠️ 您的卡庫目前沒有卡匣，請先在「我的卡庫」標記或切換為全圖鑑！", color=ft.Colors.RED_700),
                        padding=10,
                        bgcolor=ft.Colors.RED_50,
                        border_radius=8
                    )
                ]
                page.update()
                return

        rec = recommend_best_lineup(
            candidate_cards=candidate_pool,
            boss_types=selected_boss_types,
            team_size=3
        )

        cards_ui = []
        # 顯示對手弱點倍率橫幅
        weaknesses = get_weaknesses(selected_boss_types)
        weak_chips = []
        for t, mult in weaknesses.items():
            if mult >= 2.0:
                weak_chips.append(
                    ft.Chip(
                        label=ft.Text(f"{t} {mult}x", size=12, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                        bgcolor=TYPE_COLORS.get(t, "#666666")
                    )
                )

        cards_ui.append(
            ft.Container(
                content=ft.Column([
                    ft.Text(f"🎯 對手屬性：{' / '.join(selected_boss_types)}", weight=ft.FontWeight.BOLD, size=15),
                    ft.Text("極限弱點 (剋制倍率):", size=12, color=ft.Colors.GREY_700),
                    ft.Row(weak_chips, wrap=True, spacing=5) if weak_chips else ft.Text("無明顯弱點", size=12)
                ]),
                padding=10,
                bgcolor=ft.Colors.BLUE_50,
                border_radius=8
            )
        )

        for idx, item in enumerate(rec.get("top_team", [])):
            c = item.get("card", {})
            star = c.get("star", 5)
            special = c.get("special", "Normal")
            mult = item.get("type_mult", 1.0)
            score = item.get("score", 0)

            star_color = ft.Colors.AMBER_600 if star >= 6 else (ft.Colors.PURPLE_600 if star == 5 else ft.Colors.BLUE_600)
            star_text = "⭐" * star

            card_control = ft.Card(
                elevation=3,
                content=ft.Container(
                    padding=12,
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                content=ft.Text(f"TOP {idx + 1}", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, size=12),
                                bgcolor=ft.Colors.RED_600 if idx == 0 else ft.Colors.BLUE_GREY_700,
                                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                border_radius=6
                            ),
                            ft.Text(f"{c.get('name')} [{c.get('id')}]", weight=ft.FontWeight.BOLD, size=16),
                            ft.Text(star_text, color=star_color, size=12)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(height=1),
                        ft.Row([
                            ft.Text(f"招式: {c.get('move_name')} ({c.get('move_type')})", size=13, weight=ft.FontWeight.W_500),
                            ft.Text(f"剋制: {mult}x 倍率", color=ft.Colors.RED_700 if mult >= 2.0 else ft.Colors.BLACK, weight=ft.FontWeight.BOLD, size=14)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([
                            ft.Text(f"系列: {c.get('series')}", size=12, color=ft.Colors.GREY_700),
                            ft.Text(f"特殊機制: {special}", size=12, color=ft.Colors.INDIGO_700, weight=ft.FontWeight.BOLD if special != "Normal" else ft.FontWeight.NORMAL),
                            ft.Text(f"推薦評分: {int(score)}", size=12, color=ft.Colors.GREEN_800, weight=ft.FontWeight.BOLD)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                    ], spacing=6)
                )
            )
            cards_ui.append(card_control)

        recommend_results_col.controls = cards_ui
        page.update()

    def on_boss_type_click(type_name: str):
        if type_name in selected_boss_types:
            selected_boss_types.remove(type_name)
        else:
            if len(selected_boss_types) >= 2:
                selected_boss_types.pop(0)
            selected_boss_types.append(type_name)
        rebuild_type_buttons()
        refresh_recommendations()

    type_buttons_row = ft.Row(wrap=True, spacing=6)
    def rebuild_type_buttons():
        btns = []
        for t in TYPES:
            is_sel = t in selected_boss_types
            bg_color = TYPE_COLORS.get(t, "#888888")
            btns.append(
                ft.Container(
                    content=ft.Text(t, color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                    bgcolor=bg_color,
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    border_radius=8,
                    border=ft.border.all(3, ft.Colors.BLACK) if is_sel else None,
                    on_click=lambda e, val=t: on_boss_type_click(val)
                )
            )
        type_buttons_row.controls = btns

    rebuild_type_buttons()

    battle_view = ft.Container(
        content=ft.Column([
            ft.Text("⚡ 選擇對手/頭目屬性 (可選 1~2 個):", weight=ft.FontWeight.BOLD, size=15),
            type_buttons_row,
            ft.Row([
                ft.Switch(ref=use_my_deck_only, label="僅從我的卡匣庫推薦", value=False, on_change=refresh_recommendations),
                ft.ElevatedButton("🔄 重新計算", icon=ft.Icons.REFRESH, on_click=refresh_recommendations, bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(),
            recommend_results_col
        ], spacing=10),
        padding=10
    )

    # 預設載入一次推薦
    refresh_recommendations()

    # ==============================================================================
    # 🎒 頁面 2：我的卡匣庫 (My Collection)
    # ==============================================================================
    collection_list_col = ft.Column(spacing=6)
    stats_text = ft.Text("", size=13, weight=ft.FontWeight.BOLD)

    def refresh_collection_view(star_filter=None):
        stats = get_collection_stats(owned_ids)
        stats_text.value = f"🎒 已收藏: {stats['total_owned']} / {stats['total_available']} 張 (收集率: {stats['completion_rate']}%) | 6星: {stats['star_counts'].get(6, 0)} 張"
        
        cards_controls = []
        user_cards = get_user_cards(owned_ids)
        if star_filter and star_filter != "全部":
            user_cards = [c for c in user_cards if str(c.get("star")) == str(star_filter)]

        if not user_cards:
            cards_controls.append(ft.Text("尚無卡匣，請點選右上角新增或在圖鑑中標記！", color=ft.Colors.GREY_600))
        else:
            for c in user_cards:
                cid = c.get("id")
                star_stars = "⭐" * c.get("star", 5)
                cards_controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Column([
                                ft.Text(f"{c.get('name')} ({cid})", weight=ft.FontWeight.BOLD, size=14),
                                ft.Text(f"{star_stars} | {c.get('series')} | 招式: {c.get('move_name')}", size=11, color=ft.Colors.GREY_700)
                            ]),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_color=ft.Colors.RED_500,
                                tooltip="移出收藏",
                                on_click=lambda e, card_id=cid: remove_from_collection(card_id)
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        padding=8,
                        bgcolor=ft.Colors.WHITE,
                        border_radius=8,
                        border=ft.border.all(1, ft.Colors.GREY_300)
                    )
                )
        collection_list_col.controls = cards_controls
        page.update()

    def remove_from_collection(card_id: str):
        toggle_card_ownership(card_id, owned_ids)
        show_toast(f"已將 {card_id} 移出卡庫")
        refresh_collection_view()

    collection_view = ft.Container(
        content=ft.Column([
            ft.Text("🎒 我的卡匣庫存清單", size=16, weight=ft.FontWeight.BOLD),
            stats_text,
            ft.Divider(),
            collection_list_col
        ], spacing=10),
        padding=10
    )

    # ==============================================================================
    # ⚙️ 頁面 3：備份、匯出與匯入 (Backup & Share)
    # ==============================================================================
    share_code_field = ft.TextField(
        label="卡匣分享代碼",
        multiline=True,
        min_lines=3,
        max_lines=5,
        read_only=False,
        hint_text="在此貼上 MEZASTAR-V1:... 分享代碼"
    )

    def on_copy_share_code(e):
        code = export_collection_share_code(owned_ids)
        share_code_field.value = code
        page.set_clipboard(code)
        show_toast("✅ 分享代碼已產生並複製到手機剪貼簿！可直接傳到 LINE。")
        page.update()

    def on_import_share_code(mode="merge"):
        code = share_code_field.value
        if not code or not code.strip():
            show_toast("請先輸入或貼上代碼！", is_error=True)
            return
        ok, msg, new_ids = import_collection_from_share_code(code, mode=mode)
        if ok:
            owned_ids.clear()
            owned_ids.update(new_ids)
            show_toast(f"✅ {msg}")
            refresh_collection_view()
        else:
            show_toast(f"❌ {msg}", is_error=True)

    backup_view = ft.Container(
        content=ft.Column([
            ft.Text("📱 卡匣備份、匯出與 LINE 一鍵分享", size=16, weight=ft.FontWeight.BOLD),
            ft.Text("可隨時將手機卡匣庫備份為代碼，傳送到 LINE 或在其他手機還原！", size=12, color=ft.Colors.GREY_700),
            ft.Divider(),
            share_code_field,
            ft.Row([
                ft.ElevatedButton("📋 產生並複製 LINE 代碼", icon=ft.Icons.COPY, bgcolor=ft.Colors.GREEN_600, color=ft.Colors.WHITE, on_click=on_copy_share_code),
            ]),
            ft.Divider(),
            ft.Text("📥 匯入代碼至手機卡庫：", weight=ft.FontWeight.BOLD, size=14),
            ft.Row([
                ft.ElevatedButton("➕ 合併加入", bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE, on_click=lambda e: on_import_share_code("merge")),
                ft.ElevatedButton("🔄 完全覆蓋", bgcolor=ft.Colors.ORANGE_700, color=ft.Colors.WHITE, on_click=lambda e: on_import_share_code("overwrite"))
            ])
        ], spacing=10),
        padding=10
    )

    # ==============================================================================
    # 📖 頁面 4：全卡匣圖鑑庫 (Pokedex)
    # ==============================================================================
    pokedex_list_col = ft.Column(spacing=6)
    pokedex_search_field = ft.TextField(hint_text="🔍 搜尋卡匣名稱、編號或招式...", on_change=lambda e: refresh_pokedex_view())

    def refresh_pokedex_view():
        kw = pokedex_search_field.value.strip().lower() if pokedex_search_field.value else ""
        cards_to_show = all_cards
        if kw:
            cards_to_show = [
                c for c in cards_to_show
                if kw in c.get("name", "").lower() or kw in c.get("id", "").lower() or kw in c.get("move_name", "").lower()
            ]

        items = []
        for c in cards_to_show[:60]:  # 避免一次渲染過多影響手機流暢度
            cid = c.get("id")
            is_owned = cid in owned_ids
            star = c.get("star", 5)
            items.append(
                ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Row([
                                ft.Text(f"{c.get('name')}", weight=ft.FontWeight.BOLD, size=14),
                                ft.Text(f"[{cid}]", size=12, color=ft.Colors.GREY_700),
                                ft.Text("⭐" * star, size=11, color=ft.Colors.AMBER_700)
                            ]),
                            ft.Text(f"{c.get('series')} | 招式: {c.get('move_name')} ({c.get('move_type')}) | 威力: {c.get('move_power')}", size=11, color=ft.Colors.GREY_600)
                        ]),
                        ft.IconButton(
                            icon=ft.Icons.CHECK_CIRCLE if is_owned else ft.Icons.ADD_CIRCLE_OUTLINE,
                            icon_color=ft.Colors.GREEN_600 if is_owned else ft.Colors.GREY_400,
                            tooltip="切換持有狀態",
                            on_click=lambda e, card_id=cid: toggle_pokedex_card(card_id)
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=8,
                    bgcolor=ft.Colors.GREEN_50 if is_owned else ft.Colors.WHITE,
                    border_radius=8,
                    border=ft.border.all(1, ft.Colors.GREEN_200 if is_owned else ft.Colors.GREY_300)
                )
            )
        pokedex_list_col.controls = items
        page.update()

    def toggle_pokedex_card(card_id: str):
        toggle_card_ownership(card_id, owned_ids)
        refresh_pokedex_view()
        refresh_collection_view()

    pokedex_view = ft.Container(
        content=ft.Column([
            ft.Text("📖 Mezastar 全卡匣圖鑑庫", size=16, weight=ft.FontWeight.BOLD),
            pokedex_search_field,
            pokedex_list_col
        ], spacing=10),
        padding=10
    )

    # ==============================================================================
    # 📱 主導覽列與畫面切換
    # ==============================================================================
    body_container = ft.Container(content=battle_view)

    def on_navigation_change(e):
        idx = e.control.selected_index
        if idx == 0:
            body_container.content = battle_view
            refresh_recommendations()
        elif idx == 1:
            body_container.content = collection_view
            refresh_collection_view()
        elif idx == 2:
            body_container.content = pokedex_view
            refresh_pokedex_view()
        elif idx == 3:
            body_container.content = backup_view
        page.update()

    page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationDestination(icon=ft.Icons.FLASH_ON, label="對戰推薦"),
            ft.NavigationDestination(icon=ft.Icons.FOLDER_SPECIAL, label="我的卡庫"),
            ft.NavigationDestination(icon=ft.Icons.MENU_BOOK, label="卡匣圖鑑"),
            ft.NavigationDestination(icon=ft.Icons.SHARE, label="備份分享"),
        ],
        selected_index=0,
        on_change=on_navigation_change
    )

    page.add(body_container)

if __name__ == "__main__":
    ft.app(target=main)
