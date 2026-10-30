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

    def test_mark_is_dark_ink_on_a_white_card(self):
        size = 64
        pixels = icon.render_icon_pixels(size)
        x, y = icon.LOGO_LEGS[0], (icon.LOGO_ARCH_Y + icon.LOGO_BOTTOM) / 2
        red, green, blue, _alpha = pixels[int(y * size)][int(x * size)]
        self.assertLess(max(red, green, blue), 140)
        # Between the legs, below the arches, the card shows through white.
        x = (icon.LOGO_LEGS[0] + icon.LOGO_LEGS[1]) / 2
        red, green, blue, _alpha = pixels[int(icon.LOGO_BOTTOM * size) - 2][int(x * size)]
        self.assertGreater(min(red, green, blue), 200)

    def test_folded_corner_is_amber_and_cut_from_the_card(self):
        size = 64
        _left, top, right, _bottom = icon.LOGO_CARD
        x, y = right - icon.LOGO_FOLD * 3 / 4, top + icon.LOGO_FOLD * 3 / 4
        red, green, blue, _alpha = icon.render_icon_pixels(size)[int(y * size)][int(x * size)]
        self.assertGreater(red, 200)
        self.assertLess(blue, 120)
        # The card's own top-right corner is gone: that spot is the tile.
        self.assertGreater(icon.card_distance((right - 0.01) * size, (top + 0.01) * size, size), 0)

    def test_master_cache_name_tracks_artwork_version(self):
        self.assertIn(f"v{icon.MASTER_CACHE_VERSION}", icon.master_cache_path().name)


if __name__ == "__main__":
    unittest.main()
