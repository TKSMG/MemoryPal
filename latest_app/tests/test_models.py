import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal.models import Capture, Card  # noqa: E402


class CardFromDictTests(unittest.TestCase):
    def test_missing_fields_get_defaults_not_none(self):
        card = Card.from_dict({"id": "a1", "back": "Answer"})
        for name in ("deck", "front", "pathway", "association", "text_file", "image", "audio", "video", "buried_until"):
            self.assertIsInstance(getattr(card, name), str, name)
        self.assertEqual(card.deck, "General")
        self.assertEqual(card.back, "Answer")

    def test_null_or_bad_numbers_do_not_drop_the_card(self):
        card = Card.from_dict({"id": "a2", "front": "Q", "interval": None, "ease": "oops", "repetitions": "3", "lapses": None})
        self.assertEqual((card.interval, card.repetitions, card.lapses), (0, 3, 0))
        self.assertEqual(card.ease, 2.5)

    def test_camel_case_aliases_still_load(self):
        card = Card.from_dict({"id": "a3", "nextReview": "2030-01-01", "lastScore": 77, "lastResult": "Good", "createdAt": "2024-05-01 10:00"})
        self.assertEqual((card.next_review, card.last_score, card.last_result, card.created_at), ("2030-01-01", 77, "Good", "2024-05-01 10:00"))

    def test_ease_is_kept_in_a_sane_range(self):
        self.assertEqual(Card.from_dict({"ease": 0.2}).ease, 1.3)


class CaptureFromDictTests(unittest.TestCase):
    def test_chunks_are_always_a_list_of_strings(self):
        capture = Capture.from_dict({"notes": "one. two. three", "chunks": None})
        self.assertEqual(capture.chunks, ["one", "two", "three"])
        capture = Capture.from_dict({"chunks": ["a", None, 3]})
        self.assertEqual(capture.chunks, ["a", "3"])


if __name__ == "__main__":
    unittest.main()
