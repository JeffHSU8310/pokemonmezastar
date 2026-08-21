import unittest
from pathlib import Path

import numpy as np

from live_scanner import LiveCardScanner, frame_quality


class LiveScannerTests(unittest.TestCase):
    def test_camera_component_returns_a_visible_preview_stream(self):
        app_source = (Path(__file__).parent / "app.py").read_text(encoding="utf-8")
        self.assertIn("mode=WebRtcMode.SENDRECV", app_source)
        self.assertIn("sendback_video=True", app_source)
        self.assertNotIn("mode=WebRtcMode.SENDONLY", app_source)

    def test_photo_recognition_uses_an_in_memory_camera_capture(self):
        app_source = (Path(__file__).parent / "app.py").read_text(encoding="utf-8")
        self.assertIn("photographed_card = st.camera_input(", app_source)
        self.assertIn('resolution="1080p"', app_source)
        self.assertIn("photo_bytes = photographed_card.getvalue()", app_source)
        self.assertIn('camera_recognition_source = "photo"', app_source)

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
        image_bytes, error, sharpness = scanner.capture_current()
        self.assertIsNotNone(image_bytes)
        self.assertIsNone(error)
        self.assertGreater(sharpness, 48.0)
        self.assertEqual(scanner.latest_resolution, (480, 360))

    def test_dark_frame_is_rejected(self):
        scanner = LiveCardScanner()
        image = np.zeros((360, 480, 3), dtype=np.uint8)
        image[:, ::8] = 20
        scanner.ingest(image)
        image_bytes, error, _ = scanner.capture_current()
        self.assertIsNone(image_bytes)
        self.assertIn("光線不足", error)

    def test_capture_before_camera_frame_is_rejected(self):
        image_bytes, error, _ = LiveCardScanner().capture_current()
        self.assertIsNone(image_bytes)
        self.assertIn("尚未取得畫面", error)

    def test_capture_selects_sharpest_recent_frame(self):
        scanner = LiveCardScanner()
        blurred = np.full((360, 480, 3), 120, dtype=np.uint8)
        sharp = blurred.copy()
        sharp[:, ::6] = 255
        scanner.ingest(sharp)
        scanner.ingest(blurred)
        image_bytes, error, sharpness = scanner.capture_current()
        self.assertIsNotNone(image_bytes)
        self.assertIsNone(error)
        self.assertGreater(sharpness, 48.0)


if __name__ == "__main__":
    unittest.main()
