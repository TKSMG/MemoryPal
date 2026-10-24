import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import winfullscreen  # noqa: E402


class FullscreenStyleTests(unittest.TestCase):
    def test_full_screen_drops_the_frame_only(self):
        overlapped = 0x10CF0000  # WS_VISIBLE | WS_OVERLAPPEDWINDOW
        style, exstyle = winfullscreen.fullscreen_styles(overlapped, 0x00000100 | 0x00040000)
        self.assertEqual(style & winfullscreen.WS_CAPTION, 0)
        self.assertEqual(style & winfullscreen.WS_THICKFRAME, 0)
        self.assertTrue(style & 0x10000000)  # still visible
        self.assertTrue(style & 0x00020000)  # minimize box kept
        self.assertEqual(exstyle, 0x00040000)  # WS_EX_APPWINDOW kept, window edge dropped

    def test_does_nothing_without_a_window(self):
        self.assertIsNone(winfullscreen.enter(None))
        self.assertFalse(winfullscreen.leave(None, {"style": 0}))
        if not sys.platform.startswith("win"):
            self.assertIsNone(winfullscreen.enter(1234))


if __name__ == "__main__":
    unittest.main()
