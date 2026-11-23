import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

os.environ.setdefault("MEMORYPAL_DATA_DIR", tempfile.mkdtemp(prefix="memorypal-tests-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import notifications as notes  # noqa: E402
from memorypal.models import Capture, Card, DeckInfo  # noqa: E402
from memorypal.store import MemoryStore  # noqa: E402

TODAY = date.today()
MORNING = datetime(TODAY.year, TODAY.month, TODAY.day, 9, 0)


def on(offset):
    return (TODAY + timedelta(days=offset)).isoformat()


def card(deck="Biology", due=0, **fields):
    made = Card(deck=deck, front=f"Question {fields.pop('n', 0)}", back="Answer", **fields)
    made.next_review = on(due)
    return made


def settings(*kinds, **extra):
    return {"enabled": True, "kinds": list(kinds or notes.KINDS), "quiet": "off", **extra}


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.store.reset()

    def plan(self, *kinds, **extra):
        return notes.plan_notifications(self.store, settings(*kinds, **extra), start=MORNING)

    def test_off_means_nothing(self):
        self.store.cards = [card(due=0)]
        self.assertEqual(notes.plan_notifications(self.store, {"enabled": False}, start=MORNING), [])
        self.assertEqual(notes.normalize_settings(None)["enabled"], False)

    def test_cards_due_each_day_counting_what_waits(self):
        self.store.cards = [card(due=-2, n=1), card(due=0, n=2), card(due=2, n=3)]
        found = self.plan("cards_due")
        self.assertEqual([(entry["at"].date().isoformat(), entry["at"].hour, entry["due"]) for entry in found][:3], [(on(0), 19, 2), (on(1), 19, 2), (on(2), 19, 3)])
        self.assertEqual(found[0]["title"], "2 cards are ready to review")
        self.assertEqual(found[0]["open"], "review")

    def test_studied_today_skips_today(self):
        self.store.cards = [card(due=0)]
        self.store.activity[on(0)] = 3
        self.assertEqual(self.plan("cards_due")[0]["at"].date().isoformat(), on(1))

    def test_streak_saver_late_evening(self):
        self.store.activity[on(-1)] = 2
        self.store.activity[on(-2)] = 5
        found = self.plan("streak")
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0]["at"].hour, found[0]["title"]), (21, "Keep your 2-day streak"))

    def test_test_countdown(self):
        self.store.cards = [card(due=5, n=1), card(due=5, n=2, repetitions=3, last_score=90)]
        self.store.deck_infos = [DeckInfo(id="Biology", exam_date=on(3))]
        found = self.plan("test_countdown")
        self.assertEqual([(entry["at"].date().isoformat(), entry["title"]) for entry in found], [(on(0), "Biology test in 3 days"), (on(2), "Biology test tomorrow"), (on(3), "Biology test today")])
        self.assertEqual(found[2]["at"].hour, 7)
        self.assertIn("1 card still needs work", found[0]["body"])
        self.assertEqual(found[0]["open"], "deck:Biology")

    def test_plan_replaces_cards_due_and_nudges(self):
        self.store.cards = [card(due=0, n=index) for index in range(5)]
        self.store.set_study_plan({"unit": "minutes", "amount": "30", "deck": "All decks", "goal_label": "Long-term retention", "habits": []})
        found = [entry for entry in self.plan("cards_due", "plan_today", "plan_unfinished") if entry["at"].date() == TODAY]
        self.assertEqual([entry["kind"] for entry in found], ["plan_today", "plan_unfinished"])
        self.assertTrue(found[0]["title"].startswith("Today's plan: "))
        self.assertEqual(found[1]["at"].hour, 20)

    def test_plan_under_way_only_nudges(self):
        self.store.cards = [card(due=0, n=index) for index in range(5)]
        self.store.set_study_plan({"unit": "minutes", "amount": "30", "deck": "All decks", "goal_label": "Long-term retention", "habits": []})
        steps = notes._plan_days(self.store, TODAY, 1)[on(0)]
        self.store.toggle_plan_step(0, on(0), steps)
        kinds = [entry["kind"] for entry in self.plan("plan_today", "plan_unfinished") if entry["at"].date() == TODAY]
        self.assertEqual(kinds, ["plan_unfinished"])

    def test_quiet_hours_and_one_a_day(self):
        self.store.cards = [card(due=0)]
        self.store.activity[on(-1)] = 2
        self.store.activity[on(-2)] = 2
        today = [entry["kind"] for entry in self.plan("cards_due", "streak") if entry["at"].date() == TODAY]
        self.assertEqual(today, ["cards_due", "streak"])
        quiet = [entry["kind"] for entry in self.plan("cards_due", "streak", quiet="21:00-08:00") if entry["at"].date() == TODAY]
        self.assertEqual(quiet, ["cards_due"])
        one = [entry["kind"] for entry in self.plan("cards_due", "streak", one_a_day=True) if entry["at"].date() == TODAY]
        self.assertEqual(one, ["cards_due"])

    def test_notes_waiting_on_saturday(self):
        self.store.captures = [Capture(title="Chapter 3", notes="Cells make energy.\nMitochondria do it.")]
        found = self.plan("notes_waiting")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["at"].weekday(), 5)
        self.store.cards = [card(deck="Cells")]
        self.store.captures[0].deck = "Cells"
        self.assertEqual(self.plan("notes_waiting"), [])

    def test_weekly_recap_on_sunday(self):
        sunday = TODAY + timedelta(days=(6 - TODAY.weekday()))
        self.store.activity[(sunday - timedelta(days=2)).isoformat()] = 12
        if sunday - timedelta(days=4) >= TODAY - timedelta(days=30):
            self.store.activity[(sunday - timedelta(days=4)).isoformat()] = 4
        found = self.plan("weekly_recap")
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0]["at"].weekday(), found[0]["at"].hour), (6, 18))
        self.assertIn("Best day: Friday (12)", found[0]["body"])

    def test_best_time_falls_back(self):
        self.assertEqual(notes.reminder_clock(self.store, "best"), (19, 0))
        self.assertEqual(notes.reminder_clock(self.store, "08:00"), (8, 0))


if __name__ == "__main__":
    unittest.main()
