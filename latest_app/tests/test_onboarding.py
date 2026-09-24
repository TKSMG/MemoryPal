import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal.onboarding import PERSONA_ORDER, PERSONAS, persona, tour_steps  # noqa: E402
from memorypal.store import PERSONAS as STORE_PERSONAS, default_accessibility  # noqa: E402

KNOWN_VIEWS = {
    "dashboard", "training", "elder", "decks", "plan", "focus", "capture", "review", "testing",
    "quiz", "shuffle", "tools", "cuelab", "games", "library", "stats", "feedback", "settings",
}


class PersonaTests(unittest.TestCase):
    def test_every_persona_is_complete_and_known_to_the_store(self):
        self.assertEqual(set(PERSONA_ORDER), set(PERSONAS))
        self.assertEqual(set(PERSONA_ORDER), set(STORE_PERSONAS))
        for key in PERSONA_ORDER:
            data = PERSONAS[key]
            self.assertTrue(data["title"] and data["body"])
            self.assertTrue(set(data["nav"]) <= KNOWN_VIEWS, key)
            self.assertTrue(set(data["accessibility"]) <= set(default_accessibility()), key)
            self.assertGreaterEqual(len(data["tour"]), 3)

    def test_tour_pages_exist_and_start_with_core_pages(self):
        for key in PERSONA_ORDER:
            for view, title, body in tour_steps(key):
                self.assertIn(view, KNOWN_VIEWS)
                self.assertTrue(title and body)

    def test_unknown_persona_falls_back(self):
        self.assertIs(persona("nope"), PERSONAS["general"])


if __name__ == "__main__":
    unittest.main()
