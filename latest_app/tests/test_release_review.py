"""Fixes from the pre-release review: damaged synced data, conflicts, quoting."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import sync  # noqa: E402
from memorypal.media import ps_quote  # noqa: E402
from memorypal.models import Card, number  # noqa: E402


def card(**fields):
    base = {"id": "c", "front": "Q", "back": "A", "repetitions": 5, "lapses": 0, "next_review": "2026-10-20"}
    base.update(fields)
    return base


class DamagedRecords(unittest.TestCase):
    def test_bad_counts_count_as_nothing(self):
        for bad in ({"count": "abc"}, {"count": 1e400}, [1], "x", None):
            self.assertEqual(sync.count_of(bad), 0)
        records = {"activity:2026-10-11:other": {"day": "2026-10-11", "count": "abc"}, "practiced:other": [1]}
        result = sync.payload_from_records({"cards": []}, records)
        self.assertEqual(result["practiced"], 0)

    def test_huge_numbers_fall_back(self):
        self.assertEqual(number(1e400, int, 7), 7)
        self.assertEqual(number(float("nan"), float, 2.5), 2.5)
        self.assertEqual(Card.from_dict({"id": "c", "interval": 1e400}).interval, 0)

    def test_overlong_ids_are_replaced(self):
        self.assertNotEqual(Card.from_dict({"id": "x" * 400}).id, "x" * 400)
        self.assertEqual(Card.from_dict({"id": "abc"}).id, "abc")


class Conflicts(unittest.TestCase):
    def test_a_miss_wins_over_more_reviews(self):
        base = card()
        missed = card(repetitions=0, lapses=1, next_review="2026-10-12")
        good = card(repetitions=6, next_review="2026-12-25")
        merged = sync.merge_record("card:c", base, good, missed)
        self.assertEqual(merged["lapses"], 1)
        self.assertEqual(merged["next_review"], "2026-10-12")

    def test_deleted_starter_card_stays_deleted_on_a_new_device(self):
        starter = card(id="sample-chunking", repetitions=0)
        plan = sync.plan_sync({"card:sample-chunking": starter}, {}, {"card:sample-chunking": None})
        self.assertEqual(plan.push, {})
        self.assertIsNone(plan.apply["card:sample-chunking"])

    def test_reviewed_card_beats_a_delete(self):
        plan = sync.plan_sync({"card:c": card()}, {}, {"card:c": None})
        self.assertIn("card:c", plan.push)


class Quoting(unittest.TestCase):
    def test_every_single_quote_is_doubled(self):
        self.assertEqual(ps_quote("a’b'c"), "'a’’b''c'")


if __name__ == "__main__":
    unittest.main()
