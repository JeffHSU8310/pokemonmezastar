import unittest
from unittest.mock import patch

import cv2
import numpy as np

from camera_recognizer import _parse_ocr_output, detect_star_count, normalize_text, recognize_card


class CameraRecognizerTests(unittest.TestCase):
    def test_parses_current_rapidocr_output(self):
        class Output:
            txts = ("蒼響", "2-2-001")
            scores = (0.91, 0.97)

        texts, scores = _parse_ocr_output(Output())
        self.assertEqual(texts, ["蒼響", "2-2-001"])
        self.assertEqual(scores, [0.91, 0.97])

    def test_normalize_text_keeps_card_id_and_chinese(self):
        self.assertEqual(normalize_text(" 2-2-001 蒼響! "), "22001蒼響")

    def test_star_count_prefers_ocr(self):
        image = np.zeros((300, 300, 3), dtype=np.uint8)
        self.assertEqual(detect_star_count(image, ["稀有度 6★"])[0], 6)

    @patch("camera_recognizer._visual_score", return_value=0.0)
    @patch("camera_recognizer.learning_adjustments", return_value={})
    @patch("camera_recognizer.extract_ocr", return_value=(["2-2-001", "Zacian", "6★"], 0.93, None))
    def test_exact_ocr_id_ranks_expected_card_first(self, _ocr, _learning, _visual):
        ok = {"id": "2-2-001", "name": "蒼響", "name_en": "Zacian", "star": 6, "image": ""}
        other = {"id": "2-2-002", "name": "藏瑪然特", "name_en": "Zamazenta", "star": 6, "image": ""}
        image_bytes = cv2.imencode(".jpg", np.zeros((200, 200, 3), dtype=np.uint8))[1].tobytes()
        result = recognize_card(image_bytes, [other, ok])
        self.assertEqual(result["candidates"][0]["card"]["id"], "2-2-001")
        self.assertEqual(result["detected_star"], 6)

    @patch("camera_recognizer._visual_score", side_effect=lambda _descriptor, card: 0.9 if card["id"] == "WRONG" else 0.2)
    @patch("camera_recognizer.learning_adjustments", return_value={"RIGHT": 1.0, "WRONG": -0.45})
    @patch("camera_recognizer.extract_ocr", return_value=([], 0.0, None))
    def test_learned_feedback_promotes_confirmed_card(self, _ocr, _learning, _visual):
        wrong = {"id": "WRONG", "name": "錯誤", "name_en": "Wrong", "star": 5, "image": ""}
        right = {"id": "RIGHT", "name": "正確", "name_en": "Right", "star": 5, "image": ""}
        image_bytes = cv2.imencode(".jpg", np.zeros((200, 200, 3), dtype=np.uint8))[1].tobytes()
        result = recognize_card(image_bytes, [wrong, right])
        self.assertEqual(result["candidates"][0]["card"]["id"], "RIGHT")
        self.assertGreater(result["candidates"][0]["learned_score"], 0.9)

    @patch("camera_recognizer.detect_star_count", return_value=(6, 0.8))
    @patch("camera_recognizer._visual_score", return_value=0.1)
    @patch("camera_recognizer.learning_adjustments", return_value={})
    @patch("camera_recognizer.extract_ocr", return_value=([], 0.0, None))
    def test_reliable_star_count_limits_visual_search_pool(self, _ocr, _learning, visual, _star):
        cards = [
            {"id": f"S6-{index}", "name": f"六星{index}", "star": 6}
            for index in range(70)
        ] + [
            {"id": f"S5-{index}", "name": f"五星{index}", "star": 5}
            for index in range(120)
        ]
        image_bytes = cv2.imencode(".jpg", np.zeros((200, 200, 3), dtype=np.uint8))[1].tobytes()
        recognize_card(image_bytes, cards)
        self.assertEqual(visual.call_count, 70)


if __name__ == "__main__":
    unittest.main()
