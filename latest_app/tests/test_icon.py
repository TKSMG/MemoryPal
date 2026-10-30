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

    def test_m_is_white_with_green_folds(self):
        size = 64
        pixels = icon.render_icon_pixels(size)
        unit = size / icon.LOGO_GRID
        # The middle of the left leg is solid white.
        red, green, blue, _alpha = pixels[int(700 * unit)][int(262 * unit)]
        self.assertGreater(min(red, green, blue), 200)
        # The notch between the legs, under the V, shows the green tile.
        red, green, blue, _alpha = pixels[int(760 * unit)][int(512 * unit)]
        self.assertLess(red, 80)
        # A fold point on the left hemisphere is drawn in the fold colour.
        x, y = icon.logo_fold_lines()[0][0]
        self.assertTrue(icon.on_fold(x, y))
        self.assertTrue(icon.inside_mark(x, y))

    def test_folds_are_mirrored(self):
        lines = icon.logo_fold_lines()
        left, right = lines[0], lines[1]
        self.assertAlmostEqual(left[0][0] + right[0][0], icon.LOGO_GRID)
        self.assertEqual(left[0][1], right[0][1])

    def test_master_cache_name_tracks_artwork_version(self):
        self.assertIn(f"v{icon.MASTER_CACHE_VERSION}", icon.master_cache_path().name)


if __name__ == "__main__":
    unittest.main()
