import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("MEMORYPAL_DATA_DIR", tempfile.mkdtemp(prefix="memorypal-tests-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal.core import add_days, today_iso  # noqa: E402
from memorypal.models import Card  # noqa: E402
from memorypal.planning import build_multi_day_plan, build_study_plan  # noqa: E402
from memorypal.store import MemoryStore  # noqa: E402

ALL_HABITS = {"mnemonics", "repetition", "quick_mc", "games"}


class PlanTestCase(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.store.reset()


class SessionPlanTests(PlanTestCase):
    def test_minutes_add_up_exactly(self):
        for minutes in (10, 15, 20, 30, 45, 60, 90, 240):
            for goal in ("cram", "exam_prep", "long_term"):
                for deck in ("All decks", "New material"):
                    for habits in (set(), ALL_HABITS):
                        steps = build_study_plan(self.store, minutes, deck, habits, goal)
                        self.assertEqual(sum(step["minutes"] for step in steps), minutes, (minutes, goal, deck, habits))
                        self.assertTrue(all(step["minutes"] >= 2 for step in steps))

    def test_short_sessions_stay_focused(self):
        steps = build_study_plan(self.store, 10, "All decks", ALL_HABITS, "exam_prep")
        self.assertLessEqual(len(steps), 2)

    def test_review_step_reports_workload(self):
        steps = build_study_plan(self.store, 30, "All decks", set(), "long_term")
        review = next(step for step in steps if step["view"] in ("review", "focus"))
        self.assertIn("due", review["blurb"])

    def test_empty_library_starts_with_capture(self):
        self.store.cards = []
        steps = build_study_plan(self.store, 30, "All decks", set(), "long_term")
        self.assertEqual(steps[0]["view"], "capture")

    def test_interleaving_when_several_decks(self):
        self.store.add_cards([Card(deck="Biology", front="Q1", back="A1"), Card(deck="History", front="Q2", back="A2")])
        steps = build_study_plan(self.store, 45, "All decks", set(), "exam_prep")
        self.assertTrue(any("Mixed" in step["title"] for step in steps))


class MultiDayPlanTests(PlanTestCase):
    def test_projects_cards_that_come_due_later(self):
        self.store.cards = [Card(front=f"Q{i}", back="A", next_review=add_days(3), repetitions=2, interval=3) for i in range(6)]
        days = build_multi_day_plan(self.store, 5, "All decks", set(), "long_term")
        self.assertEqual(days[0]["due"], 0)
        self.assertEqual(days[3]["due"], 6)

    def test_new_material_uses_expanding_review_days(self):
        days = build_multi_day_plan(self.store, 7, "New material", set(), "long_term")
        views = [day["steps"][0]["view"] for day in days]
        self.assertEqual(views[0], "capture")
        review_days = [day["day"] for day in days if day["kind"] == "review"]
        self.assertEqual(review_days, [2, 4, 7])

    def test_exam_prep_ends_with_a_light_day(self):
        days = build_multi_day_plan(self.store, 7, "All decks", set(), "exam_prep")
        self.assertEqual(days[-1]["kind"], "light")
        self.assertLess(days[-1]["minutes"], days[-2]["minutes"])

    def test_every_day_budget_adds_up(self):
        for goal in ("cram", "exam_prep", "long_term"):
            for day in build_multi_day_plan(self.store, 14, "All decks", ALL_HABITS, goal):
                self.assertEqual(sum(step["minutes"] for step in day["steps"]), day["minutes"])


if __name__ == "__main__":
    unittest.main()
