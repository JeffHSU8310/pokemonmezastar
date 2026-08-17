"""
Unit Tests for Pokemon Mezastar System
"""

import os
import shutil
import tempfile
import unittest
from mezastar_data import (
    calculate_type_effectiveness,
    get_weaknesses,
    load_cards,
    DEFAULT_MEZASTAR_CARDS
)
from recommender import recommend_best_lineup, evaluate_card_performance
from collection_manager import (
    load_user_collection_ids,
    save_user_collection_ids,
    toggle_card_ownership,
    get_collection_stats,
    get_user_cards,
    COLLECTION_FILE_ENV
)
from github_sync import increment_version, load_version_info

class TestPokemonMezastar(unittest.TestCase):
    """
    ⚠️ 測試隔離鐵則：
    本測試會呼叫 save_user_collection_ids / toggle_card_ownership 等寫入函式。
    若未隔離，執行 `python -m unittest test_mezastar.py` 會直接把
    data/my_collection.json 覆蓋成測試用假資料，摧毀使用者真實卡匣庫
    （並在後續自動同步時一併推上 GitHub）。
    因此這裡以環境變數把收藏檔導向暫存目錄，測試結束後還原。
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp_dir = tempfile.mkdtemp(prefix="mezastar_test_")
        cls._prev_env = os.environ.get(COLLECTION_FILE_ENV)
        os.environ[COLLECTION_FILE_ENV] = os.path.join(cls._tmp_dir, "my_collection.json")

    @classmethod
    def tearDownClass(cls):
        if cls._prev_env is None:
            os.environ.pop(COLLECTION_FILE_ENV, None)
        else:
            os.environ[COLLECTION_FILE_ENV] = cls._prev_env
        shutil.rmtree(cls._tmp_dir, ignore_errors=True)

    def test_type_effectiveness_single_type(self):
        # 水剋火 = 2.0
        self.assertEqual(calculate_type_effectiveness("水", ["火"]), 2.0)
        # 電打地面 = 0.0
        self.assertEqual(calculate_type_effectiveness("電", ["地面"]), 0.0)
        # 火打水 = 0.5
        self.assertEqual(calculate_type_effectiveness("火", ["水"]), 0.5)
        # 一般打一般 = 1.0
        self.assertEqual(calculate_type_effectiveness("一般", ["一般"]), 1.0)

    def test_type_effectiveness_dual_type(self):
        # 噴火龍 (火+飛行) 受到 岩石 攻擊 = 2.0 * 2.0 = 4.0x
        self.assertEqual(calculate_type_effectiveness("岩石", ["火", "飛行"]), 4.0)
        # 烈空坐 (龍+飛行) 受到 冰 攻擊 = 2.0 * 2.0 = 4.0x
        self.assertEqual(calculate_type_effectiveness("冰", ["龍", "飛行"]), 4.0)
        # 烈空坐 (龍+飛行) 受到 草 攻擊 = 0.5 * 0.5 = 0.25x
        self.assertEqual(calculate_type_effectiveness("草", ["龍", "飛行"]), 0.25)
        # 巨金怪 (鋼+超能力) 受到 毒 攻擊 = 0.0 * 1.0 = 0.0x
        self.assertEqual(calculate_type_effectiveness("毒", ["鋼", "超能力"]), 0.0)

    def test_recommender_boss_counter(self):
        # 目標: 烈空坐 (龍+飛行)
        # 候選卡中應該由 冰系 (蕾冠王白馬 4.0x) 或 龍/妖精 (蒼響, 帝牙盧卡, 故勒頓) 等強打手獲推薦
        result = recommend_best_lineup(
            candidate_cards=DEFAULT_MEZASTAR_CARDS,
            boss_types=["龍", "飛行"],
            boss_name="烈空坐",
            team_size=3
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["top_team"]), 3)
        # 第一名應該是 4 倍剋制的打手 (如蕾冠王白馬騎士 雪矛 4.0x)
        first_pick = result["top_team"][0]
        self.assertGreaterEqual(first_pick["type_mult"], 2.0)

    def test_recommender_mewtwo_counter(self):
        # 目標: 超夢 (超能力)
        # 弱點: 惡、幽靈、蟲
        result = recommend_best_lineup(
            candidate_cards=DEFAULT_MEZASTAR_CARDS,
            boss_types=["超能力"],
            boss_name="超夢",
            team_size=3
        )
        self.assertTrue(result["success"])
        # 檢查前三名是否有 惡 或 幽靈 系招式打手 (例如 達克萊伊、蕾冠王黑馬、露奈雅拉、騎拉帝納)
        top_move_types = [r["card"]["move_type"] for r in result["top_team"]]
        self.assertTrue(any(t in ["惡", "幽靈", "蟲"] for t in top_move_types))

    def test_collection_manager(self):
        test_ids = {"2-2-001", "2-2-002"}
        save_user_collection_ids(test_ids)
        loaded = load_user_collection_ids()
        self.assertIn("2-2-001", loaded)
        self.assertIn("2-2-002", loaded)

        # 測試切換擁有狀態 (新增與移除)
        updated = toggle_card_ownership("2-2-003", loaded)
        self.assertIn("2-2-003", updated)
        updated = toggle_card_ownership("2-2-003", updated)
        self.assertNotIn("2-2-003", updated)

    def test_versioning(self):
        self.assertEqual(increment_version("1.0.0", "patch"), "1.0.1")
        self.assertEqual(increment_version("1.0.9", "patch"), "1.0.10")
        self.assertEqual(increment_version("1.0.5", "minor"), "1.1.0")
        self.assertEqual(increment_version("1.2.3", "major"), "2.0.0")

    def test_card_full_schema_and_mechanics(self):
        cards = load_cards()
        self.assertGreater(len(cards), 200)
        
        for c in cards:
            # 必備數值檢查
            self.assertIn("energy", c)
            self.assertGreater(c["energy"], 0)
            self.assertIn("hp", c)
            self.assertIn("atk", c)
            self.assertIn("def", c)
            self.assertIn("sp_atk", c)
            self.assertIn("sp_def", c)
            self.assertIn("spd", c)
            self.assertIn("move_name", c)
            self.assertIn("move_type", c)
            self.assertIn("move_power", c)
            self.assertIn("weaknesses", c)
            self.assertIn("resistances", c)
            self.assertIn("special_mechanics", c)
            
            # 機制旗標存在性檢查
            self.assertIn("has_mega", c)
            self.assertIn("has_z_move", c)

    def test_collection_export_and_import(self):
        from collection_manager import (
            export_collection_json,
            export_collection_share_code,
            export_collection_csv,
            import_collection_from_json,
            import_collection_from_share_code
        )
        test_ids = {"2-2-001", "2-2-002", "3-001"}
        save_user_collection_ids(test_ids)
        
        # 測試 JSON 匯出
        json_exported = export_collection_json(test_ids)
        self.assertIn("Pokemon Mezastar Battle Optimizer", json_exported)
        self.assertIn("2-2-001", json_exported)
        
        # 測試分享代碼匯出與匯入
        share_code = export_collection_share_code(test_ids)
        self.assertTrue(share_code.startswith("MEZASTAR-V1:"))
        ok, msg, imported_ids = import_collection_from_share_code(share_code, mode="overwrite")
        self.assertTrue(ok)
        self.assertEqual(imported_ids, test_ids)
        
        # 測試 CSV 匯出
        csv_exported = export_collection_csv(test_ids)
        self.assertIn("卡匣編號", csv_exported)
        self.assertIn("寶可夢名稱", csv_exported)
        
        # 測試合併匯入
        ok_merge, msg_merge, merged_ids = import_collection_from_share_code("DC1-001, GS1-001", mode="merge")
        self.assertTrue(ok_merge)
        self.assertIn("DC1-001", merged_ids)
        self.assertIn("2-2-001", merged_ids)

    # ==========================================================================
    # 🛡️ 使用者資料保護迴歸測試 (Regression Tests - User Data Integrity)
    # ==========================================================================

    def test_import_preview_does_not_touch_saved_collection(self):
        """
        迴歸測試：匯入「預覽解析」階段絕不可寫入收藏檔。
        修復前，UI 只要在分享代碼輸入框打一個字（且選了「完全覆蓋」），
        import_collection_from_share_code 就會立刻存檔，
        在使用者按下「確認匯入」之前就把整個卡匣庫清空。
        """
        from collection_manager import (
            import_collection_from_json,
            import_collection_from_share_code
        )

        baseline = {"2-2-001", "2-2-002", "2-2-005"}
        save_user_collection_ids(baseline)

        # 1. 分享代碼預覽（覆蓋模式）不得動到存檔
        ok, _, parsed = import_collection_from_share_code(
            "2-2-063", mode="overwrite", persist=False
        )
        self.assertTrue(ok)
        self.assertEqual(parsed, {"2-2-063"})
        self.assertEqual(load_user_collection_ids(), baseline, "預覽不應覆寫收藏檔")

        # 2. JSON 檔案預覽（覆蓋模式）不得動到存檔
        ok_j, _, parsed_j = import_collection_from_json(
            '["2-2-068"]', mode="overwrite", persist=False
        )
        self.assertTrue(ok_j)
        self.assertEqual(load_user_collection_ids(), baseline, "預覽不應覆寫收藏檔")

        # 3. 真正確認匯入 (persist=True) 才寫入
        ok_c, _, final_ids = import_collection_from_share_code(
            "2-2-063", mode="overwrite", persist=True
        )
        self.assertTrue(ok_c)
        self.assertEqual(load_user_collection_ids(), {"2-2-063"})

    def test_no_ambiguous_card_aliases(self):
        """
        迴歸測試：卡匣別名不得有歧義。
        修復前 '001' 同時對應 1-1-001 / 1-2-001 / … / 2-2-001 / SP-001 共 7 張卡，
        normalize_collection_ids('005') 會默默把使用者的卡對應成錯的那一張。
        """
        from collection_manager import get_card_alias_map, normalize_collection_ids

        alias_map, canonical_aliases = get_card_alias_map()
        all_ids = {c["id"] for c in load_cards()}

        # 每個標準卡號都必須存在且指向自己
        for cid in all_ids:
            self.assertEqual(alias_map.get(cid), cid, f"標準卡號 {cid} 必須指向自己")

        # 歧義的簡寫別名必須被捨棄，不得出現在對照表中
        self.assertNotIn("001", alias_map, "'001' 有 7 種可能對應，必須捨棄")
        self.assertNotIn("2-001", alias_map, "'2-001' 同時對應 2-1-001 與 2-2-001，必須捨棄")

        # canonical_to_aliases 也不得殘留歧義別名，
        # 否則 toggle_card_ownership 會連帶刪掉其他卡匣
        for cid, aliases in canonical_aliases.items():
            for a in aliases:
                self.assertEqual(
                    alias_map.get(a), cid,
                    f"卡匣 {cid} 的別名 {a} 有歧義，會誤刪其他卡匣"
                )

        # 標準卡號經標準化後必須維持原狀
        self.assertEqual(normalize_collection_ids({"2-1-005"}), {"2-1-005"})
        self.assertEqual(normalize_collection_ids({"2-2-005"}), {"2-2-005"})

    def test_csv_export_contains_real_stats(self):
        """
        迴歸測試：CSV 匯出必須帶出六維體質數值。
        修復前讀取不存在的 c["stats"]，導致 HP/攻擊/特攻/防禦/特防/速度 六欄全空白。
        """
        import csv as _csv
        import io as _io
        from collection_manager import export_collection_csv

        card = next(c for c in load_cards() if c["id"] == "2-2-001")
        csv_text = export_collection_csv({"2-2-001"})
        rows = list(_csv.reader(_io.StringIO(csv_text)))
        header, data_row = rows[0], rows[1]

        for col, key in [
            ("HP", "hp"), ("攻擊", "atk"), ("特攻", "sp_atk"),
            ("防禦", "def"), ("特防", "sp_def"), ("速度", "spd"),
        ]:
            value = data_row[header.index(col)]
            self.assertNotEqual(value, "", f"CSV 欄位「{col}」不可為空")
            self.assertEqual(int(value), card[key], f"CSV 欄位「{col}」數值錯誤")

    def test_collection_stats_covers_all_star_tiers(self):
        """迴歸測試：統計桶需涵蓋 1~6 星（圖鑑內含 30 張 1 星卡匣）。"""
        stats = get_collection_stats(set())
        self.assertEqual(
            sorted(stats["star_counts"].keys()), [1, 2, 3, 4, 5, 6],
            "star_counts 必須涵蓋 1~6 星"
        )

        one_star = next(c for c in load_cards() if c.get("star") == 1)
        stats_one = get_collection_stats({one_star["id"]})
        self.assertEqual(stats_one["star_counts"][1], 1)
        self.assertEqual(stats_one["total_owned"], 1)

    def test_fastapi_endpoints(self):
        """測試 FastAPI 核心 REST 端點"""
        from fastapi.testclient import TestClient
        from api import app
        client = TestClient(app)

        # 1. 健康檢查
        r_health = client.get("/api/health")
        self.assertEqual(r_health.status_code, 200)
        self.assertEqual(r_health.json()["status"], "online")

        # 2. 卡匣查詢與分頁
        r_cards = client.get("/api/cards?limit=10")
        self.assertEqual(r_cards.status_code, 200)
        self.assertGreater(r_cards.json()["total"], 200)

        # 3. 智慧對戰推薦 (對手: 烈空坐 龍+飛行)
        r_rec = client.post("/api/recommend", json={
            "boss_types": ["龍", "飛行"],
            "boss_name": "烈空坐",
            "team_size": 3
        })
        self.assertEqual(r_rec.status_code, 200)
        data = r_rec.json()
        self.assertTrue(data["recommendation"]["success"])
        self.assertEqual(len(data["recommendation"]["top_team"]), 3)

        # 4. 屬性倍率分析
        r_type = client.get("/api/types/chart?def_types=火&def_types=飛行")
        self.assertEqual(r_type.status_code, 200)
        self.assertEqual(r_type.json()["full_chart"]["岩石"], 4.0)

    def test_trainer_and_support_pokemon_qr(self):
        """測試訓練家管理、QR Code 生成與解碼、支援寶可夢資料庫"""
        import qr_manager
        
        # 1. 測試訓練家新增與讀取
        trainers = qr_manager.load_trainers()
        self.assertIsInstance(trainers, list)

        ok, msg, updated = qr_manager.add_trainer("UNITTEST-TR-001", "測試訓練家", "單元測試備註")
        self.assertTrue(ok)
        self.assertTrue(any(t["id"] == "UNITTEST-TR-001" for t in updated))

        # 2. 測試切換目前選用
        ok_act, _, _ = qr_manager.set_active_trainer("UNITTEST-TR-001")
        self.assertTrue(ok_act)

        # 3. 測試 QR Code Base64 與二進位解碼
        qr_bytes = qr_manager.generate_qr_bytes("UNITTEST-TR-001", box_size=10)
        self.assertGreater(len(qr_bytes), 100)

        ok_dec, val, _ = qr_manager.decode_qr_from_bytes(qr_bytes)
        self.assertTrue(ok_dec)
        self.assertEqual(val, "UNITTEST-TR-001")

        # 4. 測試支援寶可夢資料庫
        sp_list = qr_manager.load_support_pokemon()
        self.assertGreaterEqual(len(sp_list), 20)
        charizard_sp = next((sp for sp in sp_list if "噴火龍" in sp["name"]), None)
        self.assertIsNotNone(charizard_sp)
        self.assertIn("qr_data", charizard_sp)
        self.assertIn("skill_name", charizard_sp)

        # 清理測試資料
        qr_manager.delete_trainer("UNITTEST-TR-001")

    def test_chronological_sorting(self):
        """測試圖鑑與卡庫排序：最新發行 (銀河第2彈) 排在最前面，內部按卡號由小到大"""
        from mezastar_data import load_cards, sort_cards_chronological
        cards = load_cards()
        self.assertGreater(len(cards), 0)

        # 第 1 張卡匣必須屬於最新發行的【銀河第2彈】
        first_card = cards[0]
        self.assertEqual(first_card.get("series"), "銀河第2彈")
        self.assertEqual(first_card.get("id"), "2-2-001")

        # 驗證前 10 張卡匣均為銀河第2彈且編號依序遞增
        for i in range(10):
            c = cards[i]
            self.assertEqual(c.get("series"), "銀河第2彈")
            expected_id = f"2-2-{i+1:03d}"
            self.assertEqual(c.get("id"), expected_id)

if __name__ == "__main__":
    unittest.main()




