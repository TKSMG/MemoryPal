import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import windowtheme  # noqa: E402


class WindowThemeTests(unittest.TestCase):
    def test_colorref_is_bgr(self):
        self.assertEqual(windowtheme.colorref("#112233"), 0x332211)
        self.assertEqual(windowtheme.colorref("ffffff"), 0xFFFFFF)
        self.assertIsNone(windowtheme.colorref("#fff"))
        self.assertIsNone(windowtheme.colorref("#zzzzzz"))
        self.assertIsNone(windowtheme.colorref(None))

    def test_dark_mode_first_then_colours(self):
        pairs = windowtheme.dwm_attributes(True, caption="#0f172a", text="#e5e7eb")
        self.assertEqual(pairs[0], (windowtheme.DWMWA_USE_IMMERSIVE_DARK_MODE, 1))
        self.assertEqual(pairs[1], (windowtheme.DWMWA_USE_IMMERSIVE_DARK_MODE_OLD, 1))
        self.assertIn((windowtheme.DWMWA_CAPTION_COLOR, 0x2A170F), pairs)
        self.assertIn((windowtheme.DWMWA_TEXT_COLOR, 0xEBE7E5), pairs)

    def test_light_without_colours(self):
        self.assertEqual(windowtheme.dwm_attributes(False), [(20, 0), (19, 0)])

    def test_mac_appearance(self):
        self.assertEqual(windowtheme.mac_appearance(True), "darkaqua")
        self.assertEqual(windowtheme.mac_appearance(False), "aqua")

    def test_apply_is_a_no_op_off_platform(self):
        if not sys.platform.startswith("win"):
            self.assertEqual(windowtheme.apply_windows(1234, True), 0)
        if sys.platform != "darwin":
            self.assertFalse(windowtheme.apply_mac(object(), True))


if __name__ == "__main__":
    unittest.main()
