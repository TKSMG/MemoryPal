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
from memorypal.models import Capture, Card  # noqa: E402
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


class DeckRenameTests(StoreTestCase):
    def test_rename_moves_every_card_and_persists(self):
        self.store.cards = []
        self.store.add_cards([Card(deck="Bio", front="a", back="b"), Card(deck="Bio", front="c", back="d"), Card(deck="Art", front="e", back="f")])
        self.assertEqual(self.store.rename_deck("Bio", "  Biology   101 "), 2)
        decks = sorted(card.deck for card in self.reload().cards)
        self.assertEqual(decks, ["Art", "Biology 101", "Biology 101"])

    def test_blank_or_same_name_changes_nothing(self):
        self.store.cards = []
        self.store.add_cards([Card(deck="Bio", front="a", back="b")])
        self.assertEqual(self.store.rename_deck("Bio", "   "), 0)
        self.assertEqual(self.store.rename_deck("Bio", "Bio"), 0)
        self.assertEqual(self.store.cards[0].deck, "Bio")

    def test_cards_without_a_deck_rename_as_general(self):
        self.store.cards = []
        self.store.add_cards([Card(deck="", front="a", back="b")])
        self.assertEqual(self.store.rename_deck("General", "Misc"), 1)
        self.assertEqual(self.store.cards[0].deck, "Misc")


class DeckDetailsTests(StoreTestCase):
    def test_details_save_clean_and_persist(self):
        self.store.set_deck_info(" Cardio ", exam_date="2026-11-02", ai_style="clinical cases", ai_examples="Why aspirin?", junk="x")
        info = self.reload().deck_info("Cardio")
        self.assertEqual((info.exam_date, info.ai_style, info.ai_examples), ("2026-11-02", "clinical cases", "Why aspirin?"))
        self.store.set_deck_info("Cardio", exam_date="next week")
        self.assertEqual(self.store.deck_info("Cardio").exam_date, "")
        self.store.set_deck_info("Cardio", ai_style="", ai_examples="")
        self.assertEqual(self.reload().deck_infos, [])  # nothing left: no record kept

    def test_rename_moves_details_and_notes(self):
        self.store.cards = []
        self.store.add_cards([Card(deck="Bio", front="a", back="b")])
        self.store.set_deck_info("Bio", exam_date="2026-11-02", about="Year 1")
        self.store.set_deck_info("Biology", about="kept")
        self.store.add_capture(Capture(title="Bio: Cells", notes="x"))   # saved before notes had a set
        self.store.add_capture(Capture(title="Plants", notes="y", deck="Bio"))
        self.store.add_capture(Capture(title="Art: Colour", notes="z"))
        self.store.rename_deck("Bio", "Biology")
        store = self.reload()
        self.assertEqual(store.deck_info("Bio").about, "")
        self.assertEqual((store.deck_info("Biology").about, store.deck_info("Biology").exam_date), ("kept", "2026-11-02"))
        self.assertEqual(sorted((c.title, c.deck) for c in store.notes_for_deck("Biology")), [("Cells", "Biology"), ("Plants", "Biology")])
        self.assertEqual([c.title for c in store.notes_for_deck("Art")], ["Art: Colour"])

    def test_delete_set_keeps_its_notes(self):
        self.store.cards = []
        self.store.add_cards([Card(deck="Bio", front="a", back="b"), Card(deck="Art", front="c", back="d")])
        self.store.set_deck_info("Bio", about="Year 1")
        self.store.add_capture(Capture(title="Cells", notes="x", deck="Bio"))
        self.assertEqual(self.store.delete_deck("Bio"), 1)
        store = self.reload()
        self.assertEqual([card.deck for card in store.cards], ["Art"])
        self.assertEqual(store.deck_infos, [])
        self.assertEqual([(c.title, c.deck) for c in store.captures], [("Cells", "")])

    def test_two_windows_keep_each_others_details(self):
        other = self.reload()
        self.store.set_deck_info("Bio", about="from here")
        other.set_deck_info("Art", about="from there")
        store = self.reload()
        self.assertEqual(sorted(info.id for info in store.deck_infos), ["Art", "Bio"])

    def test_ai_cards_find_the_notes_they_came_from(self):
        heart = Capture(title="Heart", deck="Cardio", notes="The heart has four chambers.\nAspirin stops platelets sticking together.", chunks=["The heart has four chambers.", "Aspirin stops platelets sticking together."])
        other = Capture(title="Lungs", deck="Resp", notes="Aspirin stops platelets sticking together.")
        self.store.captures = [other, heart]
        card = Card(deck="Cardio", front="What does aspirin do?", back="Stops platelets", pathway="Made with AI > Heart", association='Made with AI, check it. Source: "aspirin stops platelets sticking-together"')
        self.assertEqual(self.store.source_notes(card), (heart, 1))
        by_title = Card(deck="Cardio", pathway="Made with AI > Heart", association="Made with AI, check it.")
        self.assertEqual(self.store.source_notes(by_title), (heart, -1))
        self.assertEqual(self.store.source_notes(Card(deck="Cardio", front="Mine")), (None, -1))

    def test_technique_hooks_go_onto_each_card_once(self):
        self.store.cards = []
        self.store.add_cards([Card(deck="Heart", front="Pacemaker?", back="SA node"), Card(deck="Heart", front="Biggest chamber?", back="Left ventricle", association="Thick wall")])
        self.store.add_cards([Card(deck="Other", front="x", back="y")])
        self.assertEqual(self.store.technique_items("Heart")[1], ["SA node", "Left ventricle"])
        self.assertEqual(self.store.add_technique_hooks("Heart", "acronym"), 2)
        hooks = {card.front: card.association for card in self.reload().cards}
        self.assertEqual(hooks["Pacemaker?"], "Acronym SL: S is for SA node.")
        self.assertEqual(hooks["Biggest chamber?"], "Thick wall\nAcronym SL: L is for Left ventricle.")
        self.assertEqual(hooks["x"], "")
        self.assertEqual(self.store.add_technique_hooks("Heart", "acronym"), 0)

    def test_damaged_details_are_skipped(self):
        self.store.apply_raw({"decks": [{"id": "  "}, "nope", {"name": "A", "about": "x" * 2000}, {"id": "B"}, {"id": "A", "about": "second"}]})
        self.assertEqual([(info.id, info.about) for info in self.store.deck_infos], [("A", "second")])


if __name__ == "__main__":
    unittest.main()
