import unittest

import numpy as np

from live_scanner import LiveCardScanner, frame_quality


class LiveScannerTests(unittest.TestCase):
    def test_blank_frame_is_not_sharp(self):
        sharpness, brightness = frame_quality(np.full((240, 320, 3), 120, dtype=np.uint8))
        self.assertEqual(sharpness, 0.0)
        self.assertAlmostEqual(brightness, 120.0)

    def test_stable_detailed_frame_becomes_candidate(self):
        scanner = LiveCardScanner()
        image = np.zeros((360, 480, 3), dtype=np.uint8)
        image[:, ::8] = 255
        image[::8, :] = 255
        for _ in range(7):
            scanner.ingest(image)
        self.assertIsNotNone(scanner.pop_candidate(minimum_interval=0.0))

    def test_dark_frame_is_rejected(self):
        scanner = LiveCardScanner()
        image = np.zeros((360, 480, 3), dtype=np.uint8)
        image[:, ::8] = 20
        for _ in range(7):
            scanner.ingest(image)
        self.assertIsNone(scanner.pop_candidate(minimum_interval=0.0))


if __name__ == "__main__":
    unittest.main()
