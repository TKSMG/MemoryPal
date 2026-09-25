import os
import sys
import tempfile
import unittest
from pathlib import Path

# Point the store at a throwaway data folder before memorypal.paths is imported.
_DATA_DIR = tempfile.mkdtemp(prefix="memorypal-tests-")
os.environ["MEMORYPAL_DATA_DIR"] = _DATA_DIR
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal.core import add_days, today_iso  # noqa: E402
from memorypal.models import Card  # noqa: E402
from memorypal.store import MemoryStore  # noqa: E402


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.store.reset()

    def reload(self):
        return MemoryStore()


class CardIdentityTests(StoreTestCase):
    """Objects the UI holds must stay the live, saved objects after a save."""

    def test_rating_a_card_held_across_a_save_is_kept(self):
        card = self.store.cards[0]
        card.next_review = today_iso()
        self.store.save()  # e.g. Focus "Practice" saves before opening Test Lab
        self.store.schedule(card, 5)
        saved = next(c for c in self.reload().cards if c.id == card.id)
        self.assertEqual(saved.repetitions, 1)
        self.assertEqual(saved.last_result, "Easy")

    def test_second_cue_attached_after_a_save_is_kept(self):
        card = self.store.cards[0]
        card.image = "picture.png"
        self.store.save()
        card.audio = "voice.wav"  # Cue Lab: generate a voice cue after attaching an image
        self.store.save()
        saved = next(c for c in self.reload().cards if c.id == card.id)
        self.assertEqual((saved.image, saved.audio), ("picture.png", "voice.wav"))

    def test_quiz_round_ratings_all_persist(self):
        round_cards = list(self.store.cards[:3])
        for card in round_cards:
            self.store.schedule(card, 4)
        reloaded = {c.id: c for c in self.reload().cards}
        self.assertTrue(all(reloaded[c.id].repetitions == 1 for c in round_cards))


class OnboardingTests(StoreTestCase):
    def test_new_profile_needs_welcome(self):
        self.assertFalse(self.store.onboarding["done"])

    def test_finished_welcome_is_saved(self):
        self.store.onboarding = {"done": True, "persona": "student"}
        self.store.save()
        self.assertEqual(self.reload().onboarding, {"done": True, "persona": "student"})

    def test_existing_data_without_onboarding_is_not_interrupted(self):
        import json
        raw = json.loads(self.store.data_file.read_text(encoding="utf-8"))
        raw.pop("onboarding", None)
        self.store.data_file.write_text(json.dumps(raw), encoding="utf-8")
        self.assertTrue(self.reload().onboarding["done"])


class SchedulingTests(StoreTestCase):
    def fresh_card(self, **fields):
        card = Card(front="Q", back="A", **fields)
        self.store.add_card(card)
        return card

    def test_new_card_steps(self):
        card = self.fresh_card()
        self.store.schedule(card, 4)
        self.assertEqual((card.interval, card.next_review), (1, add_days(1)))
        self.store.schedule(card, 4)
        self.assertEqual(card.interval, 3)

    def test_hard_grows_less_than_good_which_grows_less_than_easy(self):
        intervals = {}
        for quality in (3, 4, 5):
            card = self.fresh_card(repetitions=3, interval=10, next_review=today_iso())
            self.store.schedule(card, quality)
            intervals[quality] = card.interval
        self.assertLess(intervals[3], intervals[4])
        self.assertLess(intervals[4], intervals[5])
        self.assertGreater(intervals[3], 10)

    def test_lapse_resets_and_counts(self):
        card = self.fresh_card(repetitions=4, interval=20)
        self.store.schedule(card, 1)
        self.assertEqual((card.repetitions, card.interval, card.lapses), (0, 1, 1))

    def test_remembering_an_overdue_card_earns_a_longer_interval(self):
        on_time = self.fresh_card(repetitions=3, interval=10, next_review=today_iso())
        overdue = self.fresh_card(repetitions=3, interval=10, next_review=add_days(-10))
        self.store.schedule(on_time, 4)
        self.store.schedule(overdue, 4)
        self.assertGreater(overdue.interval, on_time.interval)

    def test_interval_is_capped(self):
        card = self.fresh_card(repetitions=9, interval=300, ease=3.0, next_review=today_iso())
        self.store.schedule(card, 5)
        self.assertLessEqual(card.interval, 365)

    def test_undo_restores_the_card(self):
        card = self.fresh_card()
        self.store.schedule(card, 5)
        self.assertTrue(self.store.undo_last())
        self.assertEqual((card.repetitions, card.interval), (0, 0))

    def test_undo_takes_back_the_review_count_and_todays_activity(self):
        card = self.fresh_card()
        before = (self.store.practiced, self.store.today_count())
        self.store.schedule(card, 4)
        self.store.undo_last()
        self.assertEqual((self.store.practiced, self.store.today_count()), before)
        saved = self.reload()
        self.assertEqual((saved.practiced, saved.today_count()), before)

    def test_ease_stays_within_bounds(self):
        card = self.fresh_card(repetitions=3, interval=10, ease=3.45)
        self.store.schedule(card, 5)
        self.assertLessEqual(card.ease, 3.5)


class TwoWindowTests(StoreTestCase):
    """Two open windows on one profile must not lose each other's work."""

    def test_reviews_from_both_windows_add_up(self):
        other = self.reload()
        self.store.schedule(self.store.cards[0], 4)
        other.schedule(other.cards[1], 4)
        saved = self.reload()
        self.assertEqual(saved.practiced, 2)
        self.assertEqual(saved.today_count(), 2)
        rated = {card.id for card in saved.cards if card.repetitions}
        self.assertEqual(rated, {self.store.cards[0].id, other.cards[1].id})

    def test_undo_in_one_window_keeps_the_other_windows_review(self):
        other = self.reload()
        self.store.schedule(self.store.cards[0], 4)
        other.schedule(other.cards[1], 4)
        self.store.undo_last()
        saved = self.reload()
        self.assertEqual(saved.practiced, 1)
        self.assertEqual(saved.today_count(), 1)

    def test_card_added_elsewhere_appears_after_next_save(self):
        other = self.reload()
        other.add_card(Card(front="From the other window", back="Hi"))
        self.store.schedule(self.store.cards[0], 4)
        self.assertIn("From the other window", [card.front for card in self.store.cards])


if __name__ == "__main__":
    unittest.main()
