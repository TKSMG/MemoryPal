"""The study plan learns from the practice log, fits techniques to sets, and is gentle for everyday users."""

import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

os.environ.setdefault("MEMORYPAL_DATA_DIR", tempfile.mkdtemp(prefix="memorypal-tests-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import techniques  # noqa: E402
from memorypal.core import add_days  # noqa: E402
from memorypal.models import Capture, Card  # noqa: E402
from memorypal.planning import (  # noqa: E402
    MINUTES_PER_CARD,
    best_study_hour,
    build_multi_day_plan,
    build_study_plan,
    learner_profile,
    plan_insights,
)
from memorypal.store import MemoryStore, normalize_practice_log  # noqa: E402

ALL_HABITS = {"mnemonics", "repetition", "quick_mc", "games", "breaks", "explain"}


def entry(when, method="review", ok=True, sec=0, hook=""):
    return {"at": when.replace(microsecond=0).isoformat(), "m": method, "ok": ok, "sec": sec, "hook": hook}


class SmartPlanCase(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.store.reset()
        self.store.cards = [
            Card(id=f"c{n}", deck="Planets", front=f"Planet {n}?", back=name, repetitions=n % 2, lapses=1 if n < 3 else 0, last_score=30 if n < 3 else 90, next_review=add_days(-1 if n % 2 else 3))
            for n, name in enumerate(["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn"])
        ]
        self.now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)


class TechniqueTests(SmartPlanCase):
    def test_hook_kinds_are_recognised(self):
        items = ["apple", "banana", "cherry"]
        for kind in techniques.TECHNIQUE_KEYS:
            for hook in techniques.hooks_for(kind, items):
                self.assertEqual(techniques.hook_kind(hook), kind, hook)
        self.assertEqual(techniques.hook_kind("My own picture of a red bus"), "own")
        self.assertEqual(techniques.hook_kind(""), "")
        self.assertEqual(techniques.hook_kind('Made with AI, check it.\nSource: "x"'), "")

    def test_techniques_fit_the_list(self):
        self.assertIn("acronym", techniques.fitting_techniques(["Red", "Orange", "Yellow", "Green", "Blue"]))
        self.assertEqual(techniques.fitting_techniques(["1066", "1492", "1776", "1945"])[0], "chunk")
        self.assertEqual(techniques.fitting_techniques([f"item {n}" for n in range(30)])[0], "chunk")
        self.assertIn("chain", techniques.fitting_techniques(["light hits the leaf cells", "water is split into oxygen", "sugar is built from carbon"]))
        self.assertEqual(techniques.fitting_techniques(["one"]), [])

    def test_proven_technique_is_used_but_others_still_tried(self):
        items = ["Mercury", "Venus", "Earth", "Mars"]
        picks = [techniques.pick_technique(items, "palace", turn) for turn in range(6)]
        self.assertTrue(all(pick == "palace" for turn, pick in enumerate(picks) if turn % 3 != 2))
        self.assertEqual(len({techniques.pick_technique(items, "", turn) for turn in range(3)}), 3)

    def test_mnemonics_step_names_a_technique_and_set(self):
        steps = build_study_plan(self.store, 30, "All decks", {"mnemonics"}, "long_term")
        hook = next(step for step in steps if step["view"] == "tools")
        self.assertIn(hook["technique"], techniques.TECHNIQUE_KEYS)
        self.assertEqual(hook["deck"], "Planets")
        self.assertIn(techniques.TECHNIQUE_TITLES[hook["technique"]].lower(), hook["title"])

    def test_explain_opens_talk_back_and_games_use_the_set(self):
        steps = build_study_plan(self.store, 45, "All decks", {"explain", "games"}, "long_term")
        views = {step["view"]: step for step in steps}
        self.assertIn("talkback", views)
        self.assertEqual(views["games"]["puzzle_kind"], "pairs")
        self.assertEqual(views["games"]["deck"], "Planets")

    def test_new_cards_open_new_card_review(self):
        self.store.cards.append(Card(id="new", deck="Planets", front="Planet 9?", back="Pluto", repetitions=0, lapses=0))
        steps = build_study_plan(self.store, 30, "All decks", set(), "long_term")
        new = next(step for step in steps if step["title"] == "Learn new cards")
        self.assertEqual((new["view"], new["review_mode"]), ("review", "new"))


class PracticeLogTests(SmartPlanCase):
    def test_schedule_logs_method_hook_and_gap(self):
        card = self.store.cards[0]
        card.association = "One rhymes with sun: imagine Mercury stuck to a sun."
        self.store.schedule(card, 4, method="quiz")
        self.store.practice_log[-1]["at"] = (datetime.now() - timedelta(seconds=20)).replace(microsecond=0).isoformat()
        self.store.schedule(self.store.cards[1], 1)
        first, second = self.store.practice_log[-2:]
        self.assertEqual((first["m"], first["ok"], first["hook"]), ("quiz", True, "peg"))
        self.assertEqual((second["m"], second["ok"], second["hook"]), ("review", False, ""))
        self.assertTrue(19 <= second["sec"] <= 22, second)

    def test_undo_removes_the_log_line(self):
        self.store.schedule(self.store.cards[0], 4)
        self.assertEqual(len(self.store.practice_log), 1)
        self.store.undo_last()
        self.assertEqual(self.store.practice_log, [])

    def test_log_survives_a_reload_and_is_cleaned(self):
        self.store.log_practice("talkback", True, save=True)
        again = MemoryStore()
        self.assertEqual(again.practice_log[-1]["m"], "talkback")
        cleaned = normalize_practice_log([{"at": "bad", "m": "review"}, {"at": "2026-01-01T10:00:00", "m": "hack"}, {"at": "2026-01-01T10:00:00", "m": "review", "ok": 1, "sec": 9999, "hook": "x"}])
        self.assertEqual(cleaned, [{"at": "2026-01-01T10:00:00", "m": "review", "ok": False, "sec": 0, "hook": ""}])

    def test_synced_payload_keeps_this_devices_log(self):
        self.store.log_practice("review", True)
        payload = self.store.payload()
        payload.pop("practice_log")
        self.store.apply_saved_payload(payload)
        self.assertEqual(len(self.store.practice_log), 1)


class ProfileTests(SmartPlanCase):
    def test_no_log_uses_defaults_and_more_time(self):
        self.assertEqual(learner_profile(self.store)["minutes_per_card"], MINUTES_PER_CARD)
        self.store.accessibility["more_time"] = True
        self.assertAlmostEqual(learner_profile(self.store)["minutes_per_card"], MINUTES_PER_CARD * 1.5)
        self.assertEqual(plan_insights(self.store), [])
        self.assertIsNone(best_study_hour(self.store))

    def test_measured_pace_best_hook_time_and_struggling(self):
        log = []
        for n in range(20):
            log.append(entry(self.now - timedelta(minutes=n), sec=60, ok=n % 2 == 0, hook="palace" if n < 8 else ""))
        for n in range(12):
            log.append(entry(self.now.replace(hour=20) - timedelta(days=1, minutes=n), ok=False, sec=60))
        for n in range(8):
            log.append(entry(self.now - timedelta(days=2, minutes=n), method="quiz", ok=False))
        self.store.practice_log = normalize_practice_log(log)
        profile = learner_profile(self.store)
        self.assertAlmostEqual(profile["minutes_per_card"], 1.1)
        self.assertEqual(profile["best_hook"], "")  # palace: 4/8 right, not better than 50%
        self.assertEqual(profile["best_time"], "morning")
        self.assertEqual(profile["best_hour"], 8)
        self.assertGreaterEqual(profile["miss_rate"], 0.4)
        lines = " ".join(plan_insights(self.store))
        self.assertIn("66 seconds", lines)
        self.assertIn("multiple choice", lines)
        self.assertIn("fewer new cards", lines)
        steps = build_study_plan(self.store, 30, "All decks", set(), "long_term")
        self.assertTrue(all(step.get("quiz_mode") != "self" for step in steps))

    def test_best_hook_needs_to_beat_plain_cards(self):
        log = [entry(self.now - timedelta(minutes=n), ok=True, hook="story") for n in range(8)]
        log += [entry(self.now - timedelta(minutes=20 + n), ok=n % 2 == 0) for n in range(8)]
        self.store.practice_log = normalize_practice_log(log)
        self.assertEqual(learner_profile(self.store)["best_hook"], "story")
        picks = []
        for offset in range(3):
            steps = build_study_plan(self.store, 30, "Planets", {"mnemonics"}, "long_term", on=(date.today() + timedelta(days=offset)).isoformat())
            picks += [step["technique"] for step in steps if step.get("technique")]
        self.assertEqual(picks.count("story"), 2, picks)


class GentlePlanTests(SmartPlanCase):
    def test_everyday_users_get_calm_steps(self):
        self.store.onboarding = {"done": True, "persona": "everyday"}
        for minutes in (10, 20, 30, 60):
            steps = build_study_plan(self.store, minutes, "All decks", set(), "long_term")
            self.assertEqual(sum(step["minutes"] for step in steps), minutes)
            views = [step["view"] for step in steps]
            self.assertEqual(steps[0].get("review_mode"), "gentle")
            self.assertIn("games", views)
            self.assertFalse(any("exam" in step["blurb"].lower() or "test" in step["blurb"].lower() for step in steps))
        steps = build_study_plan(self.store, 60, "All decks", set(), "long_term")
        self.assertIn("shuffle", [step["view"] for step in steps])
        self.assertIn("break", [step["view"] for step in steps])

    def test_a_chosen_exam_goal_is_kept(self):
        self.store.onboarding = {"done": True, "persona": "caregiver"}
        steps = build_study_plan(self.store, 30, "All decks", set(), "exam_prep")
        self.assertNotEqual(steps[0].get("review_mode"), "gentle")

    def test_gentle_multi_day_plans_are_shorter(self):
        self.store.onboarding = {"done": True, "persona": "everyday"}
        days = build_multi_day_plan(self.store, 7, "All decks", set(), "long_term")
        self.assertTrue(all(day["minutes"] <= 45 for day in days))


class NotesStepTests(SmartPlanCase):
    def test_notes_not_yet_cards_are_suggested(self):
        notes = "Mercury is the closest planet to the sun.\nJupiter has a great red spot that is a huge storm.\nSaturn has bright rings made of ice and rock.\nNeptune has the fastest winds in the solar system.\nUranus spins on its side like a rolling ball."
        self.store.captures = [Capture(id="n1", title="Space notes", notes=notes, chunks=notes.split("\n"), deck="Planets")]
        steps = build_study_plan(self.store, 30, "All decks", set(), "long_term")
        step = next(step for step in steps if step["view"] == "notes")
        self.assertEqual(step["capture_id"], "n1")
        self.assertIn("Space notes", step["blurb"])
        # Mercury's, Jupiter's and Saturn's parts hold a card's answer; Neptune's and Uranus's are new.
        self.assertIn("has 2 parts", step["blurb"])

    def test_covered_notes_are_not_suggested(self):
        notes = "Mercury is closest.\nVenus is hottest."
        self.store.captures = [Capture(id="n1", title="Space", notes=notes, chunks=notes.split("\n"), deck="Planets")]
        steps = build_study_plan(self.store, 30, "All decks", set(), "long_term")
        self.assertFalse(any(step["view"] == "notes" for step in steps))


if __name__ == "__main__":
    unittest.main()
