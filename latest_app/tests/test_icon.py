import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import icon  # noqa: E402


class IconTests(unittest.TestCase):
    def test_small_sizes_have_transparent_corners_and_solid_centre(self):
        for size in (16, 32):
            pixels = icon.icon_pixels(size)
            self.assertEqual((len(pixels), len(pixels[0])), (size, size))
            self.assertLess(pixels[0][0][3], 40)
            self.assertLess(pixels[size - 1][size - 1][3], 40)
            self.assertEqual(pixels[size // 2][size // 2][3], 255)

    def test_mark_is_white_on_the_left_stroke(self):
        size = 32
        x, y = icon.LOGO_LEGS[0], (icon.LOGO_ARCH_Y + icon.LOGO_BOTTOM) / 2
        red, green, blue, _alpha = icon.icon_pixels(size)[int(y * size)][int(x * size)]
        self.assertGreater(min(red, green, blue), 200)

    def test_recall_dot_is_amber_and_clear_of_the_mark(self):
        size = 64
        x, y, _radius = icon.LOGO_DOT
        red, green, blue, _alpha = icon.render_icon_pixels(size)[int(y * size)][int(x * size)]
        self.assertGreater(red, 200)
        self.assertLess(blue, 120)
        self.assertGreater(icon.logo_mark_distance(x * size, y * size, size), icon.LOGO_DOT[2] * size)

    def test_master_cache_name_tracks_artwork_version(self):
        self.assertIn(f"v{icon.MASTER_CACHE_VERSION}", icon.master_cache_path().name)


if __name__ == "__main__":
    unittest.main()
