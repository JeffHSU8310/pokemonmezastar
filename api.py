"""
Pokemon Mezastar RESTful API Engine (FastAPI)
寶可夢 Mezastar 對戰推薦系統、卡匣圖鑑與雲端/手機卡庫 REST API 服務
相容 Python 3.14，支援跨平台手機 App (Flutter / React Native / iOS / Android) 與 Web 端連線。
"""

from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Set
import json
import os

from mezastar_data import (
    TYPES,
    TYPE_COLORS,
    ALL_SERIES_LIST,
    calculate_type_effectiveness,
    get_weaknesses,
    get_full_type_chart_for_defender,
    load_cards,
    DEFAULT_MEZASTAR_CARDS
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
from github_sync import load_version_info

app = FastAPI(
    title="寶可夢 Mezastar 智慧推薦與卡匣庫 API",
    description="專為手機 APP 與 Web 打造的 Mezastar 對戰傷害分析、屬性相剋推薦及卡匣庫同步 API。",
    version="2.1.0"
)

# 啟用 CORS 跨來源資源共用 (允許手機 App 與外部前端存取)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# 📦 Pydantic 資料模型 (Request / Response Schemas)
# ==============================================================================

class RecommendRequest(BaseModel):
    boss_types: List[str] = Field(..., description="對手/頭目的屬性清單 (例如 ['龍', '飛行'])")
    boss_name: Optional[str] = Field(None, description="頭目名稱 (可選)")
    team_size: int = Field(3, ge=1, le=10, description="推薦隊伍人數 (預設 3)")
    use_my_collection_only: bool = Field(False, description="是否僅從玩家持有之卡庫中挑選")
    custom_card_ids: Optional[List[str]] = Field(None, description="自訂挑選之卡匣 ID 清單 (若指定則優先使用此清單)")

class ToggleCollectionRequest(BaseModel):
    card_id: str = Field(..., description="欲切換擁有狀態的卡匣編號")

class SaveCollectionRequest(BaseModel):
    owned_ids: List[str] = Field(..., description="要整批儲存的卡匣 ID 清單")

class ImportJsonRequest(BaseModel):
    json_content: str = Field(..., description="JSON 字串內容")
    mode: str = Field("merge", description="匯入模式: 'merge' (合併) 或 'overwrite' (覆蓋)")

class ImportShareCodeRequest(BaseModel):
    share_code: str = Field(..., description="卡匣分享代碼 (例如 MEZASTAR-V1:... 或逗號分隔編號)")
    mode: str = Field("merge", description="匯入模式: 'merge' (合併) 或 'overwrite' (覆蓋)")

# ==============================================================================
# 🩺 系統與健康檢查端點
# ==============================================================================

@app.get("/api/health", tags=["系統資訊"])
def health_check():
    """服務健康檢查"""
    return {
        "status": "online",
        "service": "Pokemon Mezastar API",
        "version": "2.1.0"
    }

@app.get("/api/version", tags=["系統資訊"])
def get_version():
    """取得目前版本與變更紀錄"""
    return load_version_info()

# ==============================================================================
# 📖 卡匣圖鑑與資料庫端點
# ==============================================================================

@app.get("/api/cards", tags=["卡匣圖鑑"])
def get_cards(
    series: Optional[str] = Query(None, description="依彈別系列篩選 (例如 '第1彈', '超級第2彈')"),
    star: Optional[int] = Query(None, ge=1, le=6, description="依星級篩選 (2~6)"),
    type_name: Optional[str] = Query(None, description="依屬性篩選 (例如 '火', '水')"),
    keyword: Optional[str] = Query(None, description="關鍵字搜尋 (卡名、編號、招式)"),
    limit: int = Query(100, ge=1, le=500, description="每頁回傳數量"),
    offset: int = Query(0, ge=0, description="偏移量 (分頁用)")
):
    """查詢卡匣資料庫 (支援彈別、星級、屬性、關鍵字過濾與分頁)"""
    cards = load_cards()
    filtered = cards

    if series and series != "全部":
        filtered = [c for c in filtered if c.get("series") == series]
    if star:
        filtered = [c for c in filtered if c.get("star") == star]
    if type_name and type_name != "全部":
        filtered = [c for c in filtered if type_name in c.get("types", []) or c.get("move_type") == type_name]
    if keyword:
        kw = keyword.strip().lower()
        filtered = [
            c for c in filtered
            if kw in c.get("name", "").lower() or kw in c.get("id", "").lower() or kw in c.get("move_name", "").lower()
        ]

    total_count = len(filtered)
    paged_cards = filtered[offset : offset + limit]

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "cards": paged_cards
    }

@app.get("/api/cards/{card_id}", tags=["卡匣圖鑑"])
def get_card_by_id(card_id: str):
    """取得特定單張卡匣的完整數據與相剋弱點分析"""
    cards = load_cards()
    for c in cards:
        if c.get("id") == card_id:
            types = c.get("types", [])
            full_chart = get_full_type_chart_for_defender(types)
            return {
                "card": c,
                "type_chart": full_chart
            }
    raise HTTPException(status_code=404, detail=f"找不到編號為 {card_id} 的卡匣")

@app.get("/api/series", tags=["卡匣圖鑑"])
def get_series_list():
    """取得系統中所有收錄的彈別清單與卡匣數量統計"""
    cards = load_cards()
    series_stats: Dict[str, int] = {}
    for c in cards:
        s = c.get("series", "其他")
        series_stats[s] = series_stats.get(s, 0) + 1
    return {
        "series": ALL_SERIES_LIST,
        "counts": series_stats
    }

# ==============================================================================
# 🎯 智慧對戰推薦端點
# ==============================================================================

@app.post("/api/recommend", tags=["智慧對戰推薦"])
def get_recommendation(payload: RecommendRequest):
    """
    依據對手 (Boss) 屬性計算最優傷害加乘，推薦 TOP 3 最佳出戰卡匣隊伍。
    """
    all_cards = load_cards()
    candidate_cards = all_cards

    # 判斷候選卡匣來源
    if payload.custom_card_ids:
        custom_id_set = set(payload.custom_card_ids)
        candidate_cards = [c for c in all_cards if c.get("id") in custom_id_set]
    elif payload.use_my_collection_only:
        owned_ids = load_user_collection_ids()
        candidate_cards = [c for c in all_cards if c.get("id") in owned_ids]

    if not candidate_cards:
        raise HTTPException(
            status_code=400,
            detail="候選卡匣庫為空！請確認已標記持有卡匣或提供正確的自訂清單。"
        )

    recommendation = recommend_best_lineup(
        candidate_cards=candidate_cards,
        boss_types=payload.boss_types,
        boss_name=payload.boss_name,
        team_size=payload.team_size
    )

    weaknesses_info = get_weaknesses(payload.boss_types)
    full_chart = get_full_type_chart_for_defender(payload.boss_types)

    return {
        "boss_types": payload.boss_types,
        "boss_name": payload.boss_name,
        "weaknesses_info": weaknesses_info,
        "type_chart": full_chart,
        "candidate_pool_size": len(candidate_cards),
        "recommendation": recommendation
    }

# ==============================================================================
# ⚡ 屬性相剋表端點
# ==============================================================================

@app.get("/api/types", tags=["屬性相剋"])
def get_all_types():
    """取得 18 種屬性清單與官方代表色碼"""
    return {
        "types": TYPES,
        "type_colors": TYPE_COLORS
    }

@app.get("/api/types/chart", tags=["屬性相剋"])
def get_type_effectiveness(
    def_types: List[str] = Query(..., description="防守方屬性清單 (可指定 1~2 個屬性)")
):
    """查詢指定屬性組合遭受 18 種屬性攻擊時的倍率分析"""
    full_chart = get_full_type_chart_for_defender(def_types)
    weaknesses = get_weaknesses(def_types)
    return {
        "defender_types": def_types,
        "weaknesses": weaknesses,
        "full_chart": full_chart
    }

# ==============================================================================
# 🎒 我的卡匣庫 (儲存、匯出、匯入、分享代碼) 端點
# ==============================================================================

@app.get("/api/collection", tags=["我的卡匣庫"])
def get_my_collection():
    """取得目前雲端儲存之玩家卡匣清單與統計數據"""
    owned_ids = load_user_collection_ids()
    stats = get_collection_stats(owned_ids)
    user_cards = get_user_cards(owned_ids)
    return {
        "total_owned": len(owned_ids),
        "owned_ids": sorted(list(owned_ids)),
        "stats": stats,
        "cards": user_cards
    }

@app.post("/api/collection/toggle", tags=["我的卡匣庫"])
def toggle_collection_card(payload: ToggleCollectionRequest):
    """切換單張卡匣的擁有狀態 (有則移除，無則加入)"""
    owned_ids = load_user_collection_ids()
    updated = toggle_card_ownership(payload.card_id, owned_ids)
    is_now_owned = payload.card_id in updated
    return {
        "card_id": payload.card_id,
        "is_owned": is_now_owned,
        "total_owned": len(updated)
    }

@app.post("/api/collection/save", tags=["我的卡匣庫"])
def save_my_collection(payload: SaveCollectionRequest):
    """整批儲存/更新持有之卡匣清單"""
    id_set = set(payload.owned_ids)
    ok = save_user_collection_ids(id_set)
    if not ok:
        raise HTTPException(status_code=500, detail="儲存失敗")
    return {
        "success": True,
        "total_owned": len(id_set),
        "owned_ids": sorted(list(id_set))
    }

@app.get("/api/collection/export/json", tags=["我的卡匣庫"])
def export_json_endpoint():
    """匯出完整結構化 JSON 備份檔案"""
    json_str = export_collection_json()
    return Response(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=my_mezastar_backup.json"}
    )

@app.get("/api/collection/export/share-code", tags=["我的卡匣庫"])
def export_share_code_endpoint():
    """取得一鍵複製之 LINE / 訊息分享代碼"""
    owned_ids = load_user_collection_ids()
    code = export_collection_share_code(owned_ids)
    return {
        "share_code": code,
        "total_count": len(owned_ids)
    }

@app.get("/api/collection/export/csv", tags=["我的卡匣庫"])
def export_csv_endpoint():
    """匯出 CSV 試算表檔案 (支援 Excel)"""
    csv_str = export_collection_csv()
    return Response(
        content=csv_str.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=my_mezastar_collection.csv"}
    )

@app.post("/api/collection/import/json", tags=["我的卡匣庫"])
def import_json_endpoint(payload: ImportJsonRequest):
    """從 JSON 字串內容匯入卡匣 (支援 merge 合併或 overwrite 覆蓋)"""
    ok, msg, final_ids = import_collection_from_json(payload.json_content, mode=payload.mode)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {
        "success": True,
        "message": msg,
        "total_owned": len(final_ids),
        "owned_ids": sorted(list(final_ids))
    }

@app.post("/api/collection/import/share-code", tags=["我的卡匣庫"])
def import_share_code_endpoint(payload: ImportShareCodeRequest):
    """從分享代碼匯入卡匣 (支援 merge 合併或 overwrite 覆蓋)"""
    ok, msg, final_ids = import_collection_from_share_code(payload.share_code, mode=payload.mode)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {
        "success": True,
        "message": msg,
        "total_owned": len(final_ids),
        "owned_ids": sorted(list(final_ids))
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
