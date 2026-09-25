import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("MEMORYPAL_DATA_DIR", tempfile.mkdtemp(prefix="memorypal-tests-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal.core import add_days, today_iso  # noqa: E402
from memorypal.models import Card  # noqa: E402
from datetime import date, timedelta  # noqa: E402

from memorypal.planning import build_multi_day_plan, build_study_plan, plan_for_today  # noqa: E402
from memorypal.store import MemoryStore  # noqa: E402

ALL_HABITS = {"mnemonics", "repetition", "quick_mc", "games", "breaks", "explain"}


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


class EncompassingPlanTests(PlanTestCase):
    def test_long_sessions_get_rest_breaks_between_blocks(self):
        steps = build_study_plan(self.store, 90, "All decks", {"breaks"}, "long_term")
        views = [step["view"] for step in steps]
        self.assertGreaterEqual(views.count("break"), 2)
        self.assertNotEqual(views[0], "break")
        self.assertNotEqual(views[-1], "break")
        self.assertEqual(sum(step["minutes"] for step in steps), 90)

    def test_no_breaks_without_the_habit(self):
        steps = build_study_plan(self.store, 90, "All decks", set(), "long_term")
        self.assertNotIn("break", [step["view"] for step in steps])

    def test_new_cards_are_introduced_in_a_steady_amount(self):
        self.store.add_cards([Card(front=f"New {i}", back="A") for i in range(60)])
        steps = build_study_plan(self.store, 30, "All decks", set(), "long_term")
        learn = next(step for step in steps if step["title"] == "Learn new cards")
        self.assertIn("up to", learn["blurb"])
        self.assertNotIn("60 new", learn["blurb"])

    def test_explain_habit_adds_a_teaching_step(self):
        steps = build_study_plan(self.store, 30, "All decks", {"explain"}, "long_term")
        self.assertIn("Explain it back", [step["title"] for step in steps])

    def test_sessions_end_with_a_wrap_up(self):
        steps = build_study_plan(self.store, 45, "All decks", set(), "exam_prep")
        self.assertEqual(steps[-1]["title"], "Wrap up")


class SavedPlanTests(PlanTestCase):
    def test_session_plan_repeats_each_day(self):
        plan = {"settings": {"unit": "minutes", "amount": "30", "deck": "All decks", "goal_label": "Exam prep", "habits": []}, "created": today_iso(), "done": {}}
        today = plan_for_today(self.store, plan)
        self.assertFalse(today["finished"])
        self.assertEqual(sum(step["minutes"] for step in today["steps"]), 30)

    def test_multi_day_plan_follows_the_calendar(self):
        start = date.today() - timedelta(days=2)
        plan = {"settings": {"unit": "days", "amount": "5", "deck": "All decks", "goal_label": "Exam prep", "habits": []}, "created": start.isoformat(), "done": {}}
        today = plan_for_today(self.store, plan)
        self.assertEqual((today["day"], today["total_days"]), (3, 5))
        self.assertTrue(today["title"].startswith("Day 3 of 5"))

    def test_multi_day_plan_finishes(self):
        start = date.today() - timedelta(days=9)
        plan = {"settings": {"unit": "weeks", "amount": "1", "deck": "All decks", "goal_label": "Cram", "habits": []}, "created": start.isoformat(), "done": {}}
        self.assertTrue(plan_for_today(self.store, plan)["finished"])

    def test_saved_plan_and_ticks_persist(self):
        self.store.set_study_plan({"unit": "minutes", "amount": "15", "deck": "All decks", "goal_label": "Cram", "habits": []})
        self.assertTrue(self.store.toggle_plan_step(1))
        reloaded = MemoryStore()
        self.assertEqual(reloaded.study_plan["settings"]["amount"], "15")
        self.assertEqual(reloaded.plan_steps_done(), {1})
        self.assertFalse(reloaded.toggle_plan_step(1))


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
