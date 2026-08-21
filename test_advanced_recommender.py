"""Focused tests for the battle optimizer; these tests never touch user data."""

import unittest
from math import ceil

from recommender import (
    RECOMMENDATION_EXCLUDED_CARD_IDS,
    evaluate_card_performance,
    filter_candidate_cards_by_stars,
    filter_recommendation_exclusions,
    recommend_best_lineup,
)


def card(name, *, atk=100, sp_atk=100, defense=100, sp_def=100, speed=100,
         move_type="一般", category="物理", power=100, accuracy=100, hp=150,
         types=None, special="無"):
    return {
        "id": name, "name": name, "series": "TEST", "star": 5, "energy": 120,
        "types": types or [move_type], "hp": hp, "atk": atk, "def": defense,
        "sp_atk": sp_atk, "sp_def": sp_def, "spd": speed,
        "move_name": f"{name}招式", "move_type": move_type, "move_power": power,
        "move_category": category, "move_accuracy": accuracy, "special": special,
        "special_mechanics": [],
    }


class TestAdvancedRecommender(unittest.TestCase):
    def test_temporarily_disabled_cards_never_enter_recommendations(self):
        excluded = [card(card_id, atk=999, power=999) for card_id in sorted(RECOMMENDATION_EXCLUDED_CARD_IDS)]
        eligible = [card("一般A"), card("一般B"), card("一般C")]
        candidates = excluded + eligible

        result = recommend_best_lineup(candidate_cards=candidates, boss_types=["一般"])

        self.assertTrue(result["success"])
        self.assertEqual(
            {item["card"]["id"] for item in result["top_team"]},
            {"一般A", "一般B", "一般C"},
        )
        self.assertTrue(
            RECOMMENDATION_EXCLUDED_CARD_IDS.isdisjoint(
                item["card"]["id"] for item in result["all_ranked"]
            )
        )
        self.assertEqual(len(candidates), 12)

    def test_exclusion_filter_normalizes_card_id_and_handles_all_excluded(self):
        disabled = [card(" sp-001 "), card("Sp-009")]
        self.assertEqual(filter_recommendation_exclusions(disabled), [])
        result = recommend_best_lineup(candidate_cards=disabled, boss_types=["一般"])
        self.assertFalse(result["success"])
        self.assertEqual(result["top_team"], [])
        self.assertIn("暫停推薦", result["message"])

    def test_lineup_star_filter_applies_to_any_candidate_source(self):
        candidates = [card("六星"), card("五星"), card("四星")]
        candidates[0]["star"], candidates[1]["star"], candidates[2]["star"] = 6, 5, 4
        self.assertEqual(
            [item["name"] for item in filter_candidate_cards_by_stars(candidates, [6])],
            ["六星"],
        )
        self.assertEqual(
            [item["name"] for item in filter_candidate_cards_by_stars(candidates, [6, 5])],
            ["六星", "五星"],
        )
        self.assertEqual(filter_candidate_cards_by_stars(candidates, []), [])

    def test_physical_move_uses_attack(self):
        physical = card("物攻型", atk=200, sp_atk=20, category="物理")
        result = evaluate_card_performance(physical, ["一般"])
        self.assertEqual(result["attack_stat"], 200)
        special = card("特攻型", atk=200, sp_atk=20, category="特殊")
        self.assertEqual(evaluate_card_performance(special, ["一般"])["attack_stat"], 20)

    def test_accuracy_is_part_of_expected_damage(self):
        reliable = card("穩定", power=100, accuracy=100)
        risky = card("賭博", power=120, accuracy=50)
        result = recommend_best_lineup(candidate_cards=[reliable, risky], boss_types=["一般"], team_size=1)
        self.assertEqual(result["top_team"][0]["card"]["name"], "穩定")

    def test_boss_defense_changes_best_move(self):
        attacker = card("雙刀", atk=150, sp_atk=150, category="物理")
        attacker["moves"] = [
            {"name": "物理招", "type": "一般", "category": "物理", "power": 100, "accuracy": 100},
            {"name": "特殊招", "type": "一般", "category": "特殊", "power": 100, "accuracy": 100},
        ]
        boss = card("高防Boss", defense=250, sp_def=50)
        result = evaluate_card_performance(attacker, ["一般"], boss_card=boss)
        self.assertEqual(result["best_move_name"], "特殊招")
        self.assertEqual(result["boss_defense_stat"], 50)

    def test_three_card_optimizer_assigns_roles_and_unique_names(self):
        candidates = [
            card("高速主攻", atk=190, speed=200, power=120),
            card("機制爆發", atk=180, power=115, special="超極巨化"),
            card("耐久收尾", atk=110, defense=220, sp_def=220, hp=260),
            card("一般候選", atk=130, power=100),
        ]
        boss = card("Boss", atk=160, sp_atk=160, hp=300, speed=140)
        result = recommend_best_lineup(candidate_cards=candidates, boss_types=["一般"], boss_card=boss)
        team = result["top_team"]
        self.assertEqual(len(team), 3)
        self.assertEqual(len({item["card"]["name"] for item in team}), 3)
        self.assertEqual([item["assigned_role"] for item in team],
                         ["主攻手（第1棒）", "爆發手（第2棒）", "收尾手（第3棒）"])
        self.assertIn("team_score", result)
        self.assertIn("team_synergy", result)

    def test_high_output_remains_primary_team_selection_factor(self):
        candidates = [
            card("高輸出A", atk=220, power=135, defense=90, sp_def=90),
            card("高輸出B", atk=205, power=130, defense=95, sp_def=95),
            card("高輸出C", atk=195, power=125, defense=100, sp_def=100),
            card("低輸出坦克", atk=105, power=85, defense=350, sp_def=350, hp=500),
        ]
        result = recommend_best_lineup(candidate_cards=candidates, boss_types=["一般"])
        selected_names = {item["card"]["name"] for item in result["top_team"]}
        self.assertEqual(selected_names, {"高輸出A", "高輸出B", "高輸出C"})

    def test_high_output_neutral_can_replace_a_very_weak_counter(self):
        candidates = [
            card("高輸出火A", atk=190, power=135, move_type="火"),
            card("高輸出火B", atk=175, power=125, move_type="火"),
            card("低輸出火", atk=60, power=50, move_type="火"),
            card("高輸出中性", atk=240, power=165, move_type="一般"),
        ]
        result = recommend_best_lineup(candidate_cards=candidates, boss_types=["草"])
        self.assertEqual(
            {item["card"]["name"] for item in result["top_team"]},
            {"高輸出火A", "高輸出火B", "高輸出中性"},
        )
        self.assertEqual(sum(item["type_mult"] > 1.0 for item in result["top_team"]), 2)

    def test_golden_lineup_maximizes_damage_without_counter_quota(self):
        candidates = [
            card("高輸出剋制", atk=190, power=135, move_type="火"),
            card("低輸出剋制", atk=90, power=70, move_type="火"),
            card("高輸出中性A", atk=240, power=165, move_type="一般"),
            card("高輸出中性B", atk=225, power=155, move_type="一般"),
        ]
        result = recommend_best_lineup(candidate_cards=candidates, boss_types=["草"])
        self.assertEqual(
            {item["card"]["name"] for item in result["top_team"]},
            {"高輸出剋制", "高輸出中性A", "高輸出中性B"},
        )
        self.assertEqual(sum(item["type_mult"] > 1.0 for item in result["top_team"]), 1)
        self.assertEqual(
            result["top_team"][0]["expected_damage"],
            max(item["expected_damage"] for item in result["top_team"]),
        )

    def test_counter_is_selected_when_its_expected_damage_is_top_three(self):
        candidates = [
            card("唯一剋制", atk=160, power=120, move_type="火"),
            card("中性A", atk=240, power=165, move_type="一般"),
            card("中性B", atk=225, power=155, move_type="一般"),
            card("中性C", atk=180, power=120, move_type="一般"),
        ]
        result = recommend_best_lineup(candidate_cards=candidates, boss_types=["草"])
        self.assertIn("唯一剋制", {item["card"]["name"] for item in result["top_team"]})
        self.assertEqual(sum(item["type_mult"] > 1.0 for item in result["top_team"]), 1)

    def test_golden_lineup_can_select_zero_counters_for_higher_total_damage(self):
        candidates = [
            card("低輸出剋制", atk=80, power=60, move_type="火"),
            card("高輸出中性A", atk=300, power=180, move_type="一般"),
            card("高輸出中性B", atk=280, power=170, move_type="一般"),
            card("高輸出中性C", atk=260, power=160, move_type="一般"),
        ]
        result = recommend_best_lineup(candidate_cards=candidates, boss_types=["草"])
        self.assertEqual(
            {item["card"]["name"] for item in result["top_team"]},
            {"高輸出中性A", "高輸出中性B", "高輸出中性C"},
        )
        self.assertEqual(sum(item["type_mult"] > 1.0 for item in result["top_team"]), 0)
        self.assertEqual(
            result["team_expected_damage"],
            round(sum(item["expected_damage"] for item in result["top_team"]), 1),
        )

    def test_star_rating_does_not_duplicate_card_face_stats(self):
        low_star = card("二星", atk=150, power=120)
        high_star = card("六星", atk=150, power=120)
        low_star["star"], high_star["star"] = 2, 6
        low = evaluate_card_performance(low_star, ["一般"])
        high = evaluate_card_performance(high_star, ["一般"])
        self.assertEqual(high["star_mult"], 1.0)
        self.assertEqual(high["expected_damage"], low["expected_damage"])

    def test_star_rating_remains_a_tiebreaker_not_a_damage_multiplier(self):
        low_star = card("二星", atk=150, power=120)
        high_star = card("六星", atk=150, power=120)
        low_star["star"], high_star["star"] = 2, 6
        result = recommend_best_lineup(
            candidate_cards=[low_star, high_star], boss_types=["一般"], team_size=1
        )
        self.assertEqual(result["top_team"][0]["card"]["name"], "六星")

    def test_mezastar_type_effectiveness_uses_1_point_6_steps(self):
        attacker = card("火打手", atk=100, power=100, move_type="火")
        single = evaluate_card_performance(attacker, ["草"])
        double = evaluate_card_performance(attacker, ["草", "鋼"])
        resisted = evaluate_card_performance(attacker, ["水"])
        self.assertEqual(single["type_mult"], 1.6)
        self.assertEqual(double["type_mult"], 2.56)
        self.assertEqual(resisted["type_mult"], 0.625)

    def test_damage_divides_directly_by_the_matching_boss_defense(self):
        attacker = card("物理打手", atk=100, power=100)
        high_defense = card("高防Boss", defense=200)
        low_defense = card("低防Boss", defense=25)
        high_result = evaluate_card_performance(attacker, ["一般"], boss_card=high_defense)
        low_result = evaluate_card_performance(attacker, ["一般"], boss_card=low_defense)
        self.assertEqual(high_result["expected_damage"], 50.0)
        self.assertEqual(low_result["expected_damage"], 400.0)

    def test_card_face_damage_is_not_multiplied_by_hidden_bonuses_again(self):
        attacker = card("卡面傷害", atk=100, power=100, special="Z招式")
        attacker["star"], attacker["energy"] = 6, 200
        attacker["has_z_move"] = True
        attacker["special_mechanics"] = ["Z招式"]
        attacker["move_damage"] = 12000
        result = evaluate_card_performance(attacker, ["一般"])
        self.assertEqual(result["base_damage"], 12000)
        self.assertEqual(result["special_mult"], 1.0)
        self.assertEqual(result["expected_damage"], 120.0)

    def test_missing_z_move_damage_uses_documented_wheel_bonus(self):
        attacker = card("Z推算", atk=100, power=100, special="Z招式")
        attacker["has_z_move"] = True
        attacker["special_mechanics"] = ["Z招式"]
        result = evaluate_card_performance(attacker, ["一般"])
        self.assertEqual(result["damage_source"], "estimated")
        self.assertEqual(result["special_mult"], 1.4)
        self.assertEqual(result["expected_damage"], 140.0)

    def test_special_defense_override_moves_target_physical_defense(self):
        attacker = card("特殊例外", atk=20, sp_atk=200, power=100, category="特殊")
        attacker["move_name"] = "精神衝擊"
        boss = card("防禦差Boss", defense=200, sp_def=50)
        result = evaluate_card_performance(attacker, ["一般"], boss_card=boss)
        self.assertEqual(result["defense_key"], "def")
        self.assertEqual(result["boss_defense_stat"], 200)
        self.assertEqual(result["expected_damage"], 100.0)

    def test_double_moves_apply_effectiveness_separately_then_sum(self):
        attacker = card("雙招", atk=100, sp_atk=100, power=100, move_type="火")
        attacker["has_double_attack"] = True
        attacker["special"] = "雙重招式"
        attacker["special_mechanics"] = ["雙重招式", "雙重攻擊"]
        attacker["moves"] = [
            {"name": "雙招招式", "type": "火", "category": "物理", "power": 100,
             "accuracy": 100, "damage": 10000},
            {"name": "水副招", "type": "水", "category": "特殊", "power": 100,
             "accuracy": 100, "damage": 10000},
        ]
        result = evaluate_card_performance(attacker, ["草"])
        self.assertTrue(result["is_combined_move"])
        self.assertEqual([move["type_mult"] for move in result["move_components"]], [1.6, 0.625])
        self.assertEqual(result["expected_damage"], 222.5)

    def test_double_move_boss_sums_incoming_damage_too(self):
        defender = card("防守方", defense=100, sp_def=100)
        boss = card("雙招Boss", atk=100, sp_atk=100)
        boss["has_double_attack"] = True
        boss["special"] = "雙重招式"
        boss["special_mechanics"] = ["雙重招式"]
        boss["moves"] = [
            {"name": "雙招Boss招式", "type": "一般", "category": "物理", "power": 100,
             "accuracy": 100, "damage": 10000},
            {"name": "特殊副招", "type": "一般", "category": "特殊", "power": 100,
             "accuracy": 100, "damage": 10000},
        ]
        result = evaluate_card_performance(defender, ["一般"], boss_card=boss)
        self.assertEqual(result["incoming_damage"], 200.0)

    def test_regular_and_gigantamax_move_options_are_not_summed(self):
        attacker = card("極巨卡", atk=100, power=100, move_type="火", special="超極巨化")
        attacker["has_gigantamax"] = True
        attacker["special_mechanics"] = ["超極巨化"]
        attacker["moves"] = [
            {"name": "極巨卡招式", "type": "火", "category": "物理", "power": 100,
             "accuracy": 100, "damage": 10000},
            {"name": "超極巨火焰", "type": "火", "category": "物理", "power": 130,
             "accuracy": 100, "damage": 15600},
        ]
        result = evaluate_card_performance(attacker, ["一般"])
        self.assertFalse(result["is_combined_move"])
        self.assertEqual(result["best_move_name"], "超極巨火焰")
        self.assertEqual(result["expected_damage"], 156.0)

    def test_team_ko_estimate_uses_combined_three_card_damage(self):
        candidates = [
            card("隊員A", atk=150, power=110),
            card("隊員B", atk=145, power=108),
            card("隊員C", atk=140, power=106),
        ]
        boss = card("六星Boss", defense=120, sp_def=120, hp=280)
        boss["star"], boss["energy"] = 6, 220
        result = recommend_best_lineup(candidate_cards=candidates, boss_types=["一般"], boss_card=boss)
        combined = round(sum(item["expected_damage"] for item in result["top_team"]), 1)
        self.assertEqual(result["team_expected_damage"], combined)
        self.assertEqual(result["team_expected_ko_turns"], ceil(result["boss_durability"] / combined))
        self.assertGreaterEqual(result["team_expected_ko_attacks"], result["team_expected_ko_turns"])
        self.assertLessEqual(result["team_expected_ko_attacks"], result["team_expected_ko_turns"] * 3)
        self.assertLess(result["team_expected_ko_turns"], min(
            item["expected_ko_turns"] for item in result["top_team"]
        ))

    def test_strong_balanced_team_can_defeat_six_star_boss_in_three_rotations(self):
        candidates = [
            card("強攻A", atk=150, power=120),
            card("強攻B", atk=150, power=120),
            card("強攻C", atk=150, power=120),
        ]
        boss = card("六星Boss", defense=100, sp_def=100, hp=194)
        boss["star"], boss["energy"] = 6, 206
        result = recommend_best_lineup(candidate_cards=candidates, boss_types=["一般"], boss_card=boss)
        self.assertEqual(result["team_expected_ko_turns"], 3)
        self.assertGreater(result["boss_durability"], boss["hp"] * 7)

    def test_boss_ko_estimate_uses_battle_scale_and_never_one_turn(self):
        attacker = card("強力打手", atk=260, power=180)
        boss = card("六星Boss", defense=80, sp_def=80, hp=220)
        boss["star"] = 6
        boss["energy"] = 210
        result = evaluate_card_performance(attacker, ["一般"], boss_card=boss)
        self.assertGreater(result["boss_durability"], boss["hp"])
        self.assertGreaterEqual(result["expected_ko_turns"], 2)


if __name__ == "__main__":
    unittest.main()
