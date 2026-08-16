"""
Unit Tests for Pokemon Mezastar System
"""

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
    get_user_cards
)
from github_sync import increment_version, load_version_info

class TestPokemonMezastar(unittest.TestCase):

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
        test_ids = {"1-001", "1-002"}
        save_user_collection_ids(test_ids)
        loaded = load_user_collection_ids()
        self.assertIn("1-001", loaded)
        self.assertIn("1-002", loaded)

        # 測試切換擁有狀態
        updated = toggle_card_ownership("1-003", loaded)
        self.assertIn("1-003", updated)
        updated = toggle_card_ownership("1-003", updated)
        self.assertNotIn("1-003", updated)

    def test_versioning(self):
        self.assertEqual(increment_version("1.0.0", "patch"), "1.0.1")
        self.assertEqual(increment_version("1.0.9", "patch"), "1.0.10")
        self.assertEqual(increment_version("1.0.5", "minor"), "1.1.0")
        self.assertEqual(increment_version("1.2.3", "major"), "2.0.0")

if __name__ == "__main__":
    unittest.main()
