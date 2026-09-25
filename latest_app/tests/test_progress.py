import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("MEMORYPAL_DATA_DIR", tempfile.mkdtemp(prefix="memorypal-tests-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import progress  # noqa: E402
from memorypal.models import Card  # noqa: E402
from memorypal.store import MemoryStore  # noqa: E402


def iso(offset):
    return (date.today() + timedelta(days=offset)).isoformat()


class LevelTests(unittest.TestCase):
    def test_levels_need_more_xp_each_time(self):
        self.assertEqual(progress.level_info(0), {"level": 1, "xp": 0, "need": 100, "pct": 0.0})
        self.assertEqual(progress.level_info(10)["level"], 2)  # 100 XP
        self.assertEqual(progress.level_info(30)["level"], 3)  # 100 + 200 XP
        self.assertEqual(progress.level_info(29)["level"], 2)


class SeriesTests(unittest.TestCase):
    def test_daily_series_is_oldest_first_and_fills_gaps(self):
        series = progress.daily_series({iso(0): 4, iso(-2): 1}, 3)
        self.assertEqual([count for _day, count in series], [1, 0, 4])

    def test_best_streak(self):
        activity = {iso(-10): 1, iso(-9): 2, iso(-8): 1, iso(-3): 1, iso(0): 1}
        self.assertEqual(progress.best_streak(activity), 3)

    def test_forecast_counts_overdue_as_today(self):
        cards = [Card(next_review=iso(-4)), Card(next_review=iso(0)), Card(next_review=iso(2)), Card(next_review=iso(40))]
        counts = [count for _day, count in progress.due_forecast(cards, 7)]
        self.assertEqual(counts[0], 2)
        self.assertEqual(counts[2], 1)
        self.assertEqual(sum(counts), 3)

    def test_maturity_groups(self):
        cards = [Card(), Card(repetitions=1, interval=2), Card(repetitions=3, interval=10), Card(repetitions=5, interval=40)]
        self.assertEqual(progress.maturity_breakdown(cards), {"new": 1, "learning": 1, "young": 1, "mature": 1})

    def test_rating_mix_uses_button_names(self):
        cards = [Card(repetitions=1, last_result="Strong match"), Card(repetitions=1, last_result="Again"), Card(repetitions=1, last_result="Close enough"), Card()]
        self.assertEqual(progress.rating_mix(cards), {"Again": 1, "Hard": 0, "Good": 1, "Easy": 1})


class AchievementTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.store.reset()

    def test_fresh_profile_has_nothing_earned(self):
        self.assertFalse(any(badge["done"] for badge in progress.achievements(self.store)))
        self.assertIsNotNone(progress.next_achievement(self.store))

    def test_first_review_is_earned_and_listed_first(self):
        self.store.schedule(self.store.cards[0], 4)
        badges = progress.achievements(self.store)
        self.assertEqual(badges[0]["key"], "first_review")
        self.assertTrue(badges[0]["done"])


if __name__ == "__main__":
    unittest.main()
