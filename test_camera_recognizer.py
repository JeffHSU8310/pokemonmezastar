import unittest
from unittest.mock import patch

import cv2
import numpy as np

from camera_recognizer import detect_star_count, normalize_text, recognize_card


class CameraRecognizerTests(unittest.TestCase):
    def test_normalize_text_keeps_card_id_and_chinese(self):
        self.assertEqual(normalize_text(" 2-2-001 蒼響! "), "22001蒼響")

    def test_star_count_prefers_ocr(self):
        image = np.zeros((300, 300, 3), dtype=np.uint8)
        self.assertEqual(detect_star_count(image, ["稀有度 6★"])[0], 6)

    @patch("camera_recognizer._visual_score", return_value=0.0)
    @patch("camera_recognizer.extract_ocr", return_value=(["2-2-001", "Zacian", "6★"], 0.93, None))
    def test_exact_ocr_id_ranks_expected_card_first(self, _ocr, _visual):
        ok = {"id": "2-2-001", "name": "蒼響", "name_en": "Zacian", "star": 6, "image": ""}
        other = {"id": "2-2-002", "name": "藏瑪然特", "name_en": "Zamazenta", "star": 6, "image": ""}
        image_bytes = cv2.imencode(".jpg", np.zeros((200, 200, 3), dtype=np.uint8))[1].tobytes()
        result = recognize_card(image_bytes, [other, ok])
        self.assertEqual(result["candidates"][0]["card"]["id"], "2-2-001")
        self.assertEqual(result["detected_star"], 6)


if __name__ == "__main__":
    unittest.main()
