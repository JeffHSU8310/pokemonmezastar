import unittest

import numpy as np

from live_scanner import LiveCardScanner, frame_quality


class LiveScannerTests(unittest.TestCase):
    def test_blank_frame_is_not_sharp(self):
        sharpness, brightness = frame_quality(np.full((240, 320, 3), 120, dtype=np.uint8))
        self.assertEqual(sharpness, 0.0)
        self.assertAlmostEqual(brightness, 120.0)

    def test_detailed_frame_can_be_captured_manually(self):
        scanner = LiveCardScanner()
        image = np.zeros((360, 480, 3), dtype=np.uint8)
        image[:, ::8] = 255
        image[::8, :] = 255
        scanner.ingest(image)
        image_bytes, error = scanner.capture_current()
        self.assertIsNotNone(image_bytes)
        self.assertIsNone(error)

    def test_dark_frame_is_rejected(self):
        scanner = LiveCardScanner()
        image = np.zeros((360, 480, 3), dtype=np.uint8)
        image[:, ::8] = 20
        scanner.ingest(image)
        image_bytes, error = scanner.capture_current()
        self.assertIsNone(image_bytes)
        self.assertIn("光線不足", error)

    def test_capture_before_camera_frame_is_rejected(self):
        image_bytes, error = LiveCardScanner().capture_current()
        self.assertIsNone(image_bytes)
        self.assertIn("尚未取得畫面", error)


if __name__ == "__main__":
    unittest.main()
