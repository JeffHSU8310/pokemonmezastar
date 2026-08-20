import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from recognition_learning import learning_adjustments, learning_example_count, record_confirmation


def sample_image_bytes(seed=0):
    rng = np.random.default_rng(seed)
    image = rng.integers(0, 256, (240, 320, 3), dtype=np.uint8)
    return cv2.imencode(".jpg", image)[1].tobytes()


class RecognitionLearningTests(unittest.TestCase):
    def test_confirmation_boosts_correct_and_penalizes_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "learning.json"
            image = sample_image_bytes()
            self.assertEqual(record_confirmation(image, "RIGHT", "WRONG", path), 1)
            scores = learning_adjustments(image, path)
            self.assertGreater(scores["RIGHT"], 0.9)
            self.assertLess(scores["WRONG"], 0.0)

    def test_duplicate_confirmation_does_not_add_raw_photo_or_new_example(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "learning.json"
            image = sample_image_bytes(2)
            record_confirmation(image, "CARD-1", path=path)
            record_confirmation(image, "CARD-1", path=path)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(learning_example_count(path), 1)
            self.assertEqual(data["examples"][0]["confirmations"], 2)
            self.assertNotIn("image", data["examples"][0])

    def test_different_image_has_no_strong_adjustment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "learning.json"
            record_confirmation(sample_image_bytes(3), "CARD-1", path=path)
            self.assertLess(learning_adjustments(sample_image_bytes(4), path).get("CARD-1", 0.0), 0.8)


if __name__ == "__main__":
    unittest.main()
