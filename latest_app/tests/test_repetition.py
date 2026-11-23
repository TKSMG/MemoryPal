import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import repetition
from memorypal.planning import build_study_plan
from memorypal.models import Card
from memorypal.store import MemoryStore


class RepetitionStepsTest(unittest.TestCase):
    def labels(self, *args):
        return [label for label, _ in repetition.repetition_steps(*args)]

    def test_start_five_range_three(self):
        self.assertEqual(self.labels(5, 5, 3), ["5", "5-4", "5-4-3", "3-2-1"])
        self.assertEqual(repetition.repetition_steps(5, 5, 3)[-1], ("3-2-1", [2, 1, 0]))

    def test_no_range_walks_back_to_one(self):
        self.assertEqual(self.labels(5, 5, None), ["5", "5-4", "5-4-3", "5-4-3-2", "5-4-3-2-1"])

    def test_defaults_start_at_five_or_the_last_item(self):
        self.assertEqual(self.labels(12), ["5", "5-4", "5-4-3", "5-4-3-2", "5-4-3-2-1"])
        self.assertEqual(self.labels(3), ["3", "3-2", "3-2-1"])
        self.assertEqual(repetition.repetition_steps(0), [])

    def test_out_of_range_numbers_are_clamped(self):
        self.assertEqual(self.labels(4, 40, 0), ["4", "4-3-2-1"])
        self.assertEqual(self.labels(4, -3, 9), ["1"])


class RepetitionItemsTest(unittest.TestCase):
    def test_typed_list(self):
        self.assertEqual(repetition.items_from_text("Mercury\nH - hydrogen\n\nVenus"), [
            {"prompt": "Item 1", "answer": "Mercury"},
            {"prompt": "H", "answer": "hydrogen"},
            {"prompt": "Item 3", "answer": "Venus"},
        ])

    def test_cards_skip_blank_answers(self):
        cards = [Card(front="Q1", back="A1"), Card(front="Q2", back="  "), Card(front="", back="A3")]
        self.assertEqual(repetition.items_from_cards(cards), [{"prompt": "Q1", "answer": "A1"}, {"prompt": "Item 2", "answer": "A3"}])
        self.assertEqual(repetition.round_expected(repetition.items_from_cards(cards), [1, 0]), "A3\nA1")


class RepetitionPlanTest(unittest.TestCase):
    def test_repetition_habit_adds_a_path_step(self):
        store = MemoryStore()
        store.reset()
        store.cards = [Card(deck="History", front=f"Q{n}", back=f"A{n}") for n in range(8)]
        steps = build_study_plan(store, 45, "All decks", {"repetition"}, "long_term")
        self.assertIn("shuffle", [step["view"] for step in steps])


if __name__ == "__main__":
    unittest.main()
