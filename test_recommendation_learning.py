"""Tests for battle-result learning; never writes production learning data."""

from pathlib import Path
import tempfile
import unittest

from recommendation_learning import (
    learned_pair_adjustment,
    recommendation_feedback_count,
    recommendation_learning_adjustments,
    record_recommendation_feedback,
)
from recommender import recommend_best_lineup


class RecommendationLearningTests(unittest.TestCase):
    def test_win_feedback_adds_conservative_card_and_pair_weight(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "learning.json"
            count = record_recommendation_feedback(
                "超夢", ["超能力"], ["A", "B", "C"], True, "A", path
            )
            self.assertEqual(count, 1)
            learned = recommendation_learning_adjustments(["超能力"], path)
            self.assertGreater(learned["card_adjustments"]["A"], learned["card_adjustments"]["B"])
            self.assertGreater(learned_pair_adjustment(["A", "B", "C"], learned["pair_adjustments"]), 0)
            self.assertEqual(recommendation_feedback_count(path), 1)

    def test_feedback_only_applies_to_same_boss_types(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "learning.json"
            record_recommendation_feedback("超夢", ["超能力"], ["A", "B", "C"], False, path=path)
            self.assertLess(recommendation_learning_adjustments(["超能力"], path)["card_adjustments"]["A"], 0)
            self.assertEqual(recommendation_learning_adjustments(["火"], path)["matching_feedback_count"], 0)

    def test_recommender_applies_learned_result(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "learning.json"
            base = {
                "series": "TEST", "star": 5, "energy": 120, "types": ["一般"],
                "hp": 150, "atk": 120, "def": 100, "sp_atk": 80, "sp_def": 100, "spd": 100,
                "move_name": "撞擊", "move_type": "一般", "move_power": 100,
                "move_category": "物理", "move_accuracy": 100, "special": "無",
            }
            cards = [{**base, "id": "A", "name": "A"}, {**base, "id": "B", "name": "B"}]
            record_recommendation_feedback("Boss", ["一般"], ["A"], False, path=path)
            record_recommendation_feedback("Boss", ["一般"], ["B"], True, "B", path)
            result = recommend_best_lineup(
                candidate_cards=cards, boss_types=["一般"], team_size=1, learning_path=path
            )
            self.assertEqual(result["top_team"][0]["card"]["id"], "B")
            self.assertEqual(result["matching_feedback_count"], 2)


if __name__ == "__main__":
    unittest.main()
