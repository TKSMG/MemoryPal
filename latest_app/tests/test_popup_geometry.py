import unittest

from memorypal import popup_geometry as pg

SCREEN = (0, 0, 1920, 1080)


def measure(text):
    # A fake monospace font: 9 px per character.
    return 9 * len(text)


class FitPopupRectTests(unittest.TestCase):
    def test_opens_below_left_aligned_when_there_is_room(self):
        self.assertEqual(pg.fit_popup_rect(300, 200, (100, 100, 220, 140), SCREEN, gap=4), (100, 144, 300, 200))

    def test_right_aligns_with_anchor_near_right_edge(self):
        x, _y, width, _h = pg.fit_popup_rect(400, 200, (1700, 100, 1900, 140), SCREEN, gap=4)
        self.assertEqual(x + width, 1900)

    def test_shifts_left_when_wider_than_space_to_anchor_right(self):
        x, _y, width, _h = pg.fit_popup_rect(1000, 200, (1800, 100, 1900, 140), SCREEN)
        self.assertGreaterEqual(x, 8)
        self.assertLessEqual(x + width, 1912)

    def test_flips_above_near_bottom(self):
        x, y, _w, height = pg.fit_popup_rect(300, 300, (100, 900, 220, 940), SCREEN, gap=4)
        self.assertEqual(y + height, 896)

    def test_pins_to_screen_when_neither_side_fits(self):
        _x, y, _w, height = pg.fit_popup_rect(300, 700, (100, 500, 220, 540), SCREEN, gap=4)
        self.assertGreaterEqual(y, 8)
        self.assertLessEqual(y + height, 1072)

    def test_caps_size_to_screen(self):
        x, y, width, height = pg.fit_popup_rect(5000, 5000, (0, 0, 10, 10), SCREEN)
        self.assertEqual((x, y, width, height), (8, 8, 1904, 1064))


class ElideTests(unittest.TestCase):
    def test_short_text_is_untouched(self):
        self.assertEqual(pg.elide(measure, "Import image", 500), "Import image")

    def test_long_text_gets_ellipsis_and_fits(self):
        text = "Import note, PDF, Word or RTF"
        shown = pg.elide(measure, text, 120)
        self.assertTrue(shown.endswith(pg.ELLIPSIS))
        self.assertLessEqual(measure(shown), 120)


class DropdownLayoutTests(unittest.TestCase):
    def test_list_is_wide_enough_for_longest_label(self):
        labels = ["Import note, PDF, Word or RTF", "Save current note", "Remove note"]
        # A narrow 60 px anchor, like the NOTE cue button.
        x, y, width, height, rows, shown = pg.dropdown_layout(labels, measure, (200, 200, 260, 240), SCREEN, row_height=24, inset=6, side=18)
        self.assertEqual(shown, labels)
        self.assertGreaterEqual(width, measure(labels[0]) + 2 * 18 + 2 * 6)
        self.assertEqual(rows, 3)
        self.assertEqual(height, 3 * 24 + 12)

    def test_never_narrower_than_anchor(self):
        _x, _y, width, *_ = pg.dropdown_layout(["A"], measure, (100, 100, 700, 140), SCREEN, 24, 6, 18)
        self.assertEqual(width, 600)

    def test_stays_on_screen_at_right_edge(self):
        x, _y, width, *_ = pg.dropdown_layout(["Import note, PDF, Word or RTF"], measure, (1880, 100, 1915, 140), SCREEN, 24, 6, 18)
        self.assertLessEqual(x + width, 1912)

    def test_elides_labels_wider_than_screen(self):
        label = "x" * 400
        _x, _y, width, _h, _rows, shown = pg.dropdown_layout([label], measure, (0, 0, 10, 10), SCREEN, 24, 6, 18)
        self.assertLessEqual(width, 1904)
        self.assertLessEqual(measure(shown[0]), width - 12 - 36)

    def test_fewer_rows_on_short_screen(self):
        labels = [f"Item {n}" for n in range(10)]
        _x, y, _w, height, rows, _ = pg.dropdown_layout(labels, measure, (0, 40, 100, 60), (0, 0, 800, 200), 24, 6, 18)
        self.assertLess(rows, 10)
        self.assertGreaterEqual(y, 8)
        self.assertLessEqual(y + height, 192)


class CenteredRectTests(unittest.TestCase):
    def test_centres_over_owner(self):
        self.assertEqual(pg.centered_rect(400, 300, (100, 100, 900, 700), SCREEN), (300, 250, 400, 300))

    def test_kept_on_screen_and_capped(self):
        x, y, width, height = pg.centered_rect(3000, 300, (1800, 900, 1920, 1080), SCREEN)
        self.assertEqual(width, 1904)
        self.assertGreaterEqual(x, 8)
        self.assertLessEqual(y + height, 1072)


if __name__ == "__main__":
    unittest.main()
