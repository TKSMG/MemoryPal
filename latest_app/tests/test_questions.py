import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import questions as q  # noqa: E402
from memorypal.core import comparable_text  # noqa: E402
from memorypal.models import Card  # noqa: E402

TODAY = "2026-10-18"


def deck():
    return [
        Card(id="fr", deck="Geo", front="Capital of France", back="Paris", next_review="2026-10-01", lapses=2),
        Card(id="es", deck="Geo", front="Capital of Spain", back="Madrid", next_review="2026-10-30"),
        Card(id="it", deck="Geo", front="Capital of Italy", back="Rome", next_review="2026-10-30"),
        Card(id="de", deck="Geo", front="Capital of Germany", back="Berlin", next_review="2026-10-30"),
        Card(id="pl", deck="Geo", front="Inner planets", back="Mercury, Venus, Earth and Mars", next_review="2026-10-30"),
        Card(id="ww2", deck="History", front="End of World War II", back="1945", next_review="2026-10-30"),
        Card(id="hast", deck="History", front="Battle of Hastings", back="1066", next_review="2026-10-30"),
        Card(id="bit", deck="History", front="Study bit 3", back="The Treaty of Versailles was signed in 1919", next_review="2026-10-30"),
        Card(id="ps", deck="Bio", front="What is photosynthesis?", back="The process plants use to turn light and water into food.", next_review="2026-10-30"),
        Card(id="sr", deck="Bio", front="What is spaced repetition?", back="Reviewing information at increasing intervals so recall strengthens over time.", next_review="2026-10-30"),
    ]


class RngTests(unittest.TestCase):
    def test_mulberry32_matches_the_reference(self):
        # Reference values from the JavaScript mulberry32 with seed 1.
        rng = q.Rng(1)
        self.assertEqual([rng.next_uint() for _ in range(3)], [2693262067, 11749833, 2265367787])

    def test_same_seed_same_sequence(self):
        self.assertEqual(q.Rng(5).shuffle(list(range(20))), q.Rng(5).shuffle(list(range(20))))
        self.assertTrue(all(0 <= q.Rng(9).below(7) < 7 for _ in range(50)))


class NoteQuestionTests(unittest.TestCase):
    def ask(self, text):
        made = q.question_for_bit(text)
        return (made["prompt"], made["answer"]) if made else None

    def test_definitions_become_what_questions(self):
        self.assertEqual(self.ask("Photosynthesis is how plants make food."), ("What is Photosynthesis?", "how plants make food"))
        self.assertEqual(self.ask("The capital of Peru is Lima"), ("What is the capital of Peru?", "Lima"))
        self.assertEqual(self.ask("Osmosis means water moving through a membrane"), ("What does Osmosis mean?", "water moving through a membrane"))
        self.assertEqual(self.ask("DNA stands for deoxyribonucleic acid"), ("What does DNA stand for?", "deoxyribonucleic acid"))
        self.assertEqual(self.ask("Primary colours: red, yellow, blue"), ("What are Primary colours?", "red, yellow, blue"))

    def test_dates_become_when_questions(self):
        self.assertEqual(self.ask("In 1492, Columbus sailed the ocean blue."), ("When did this happen? Columbus sailed the ocean blue.", "1492"))
        self.assertEqual(self.ask("The Battle of Hastings was in 1066"), ("When was the Battle of Hastings?", "1066"))
        self.assertEqual(self.ask("The war ended in 1945."), ("When did this happen? The war ended.", "1945"))

    def test_conservative_rules(self):
        self.assertIsNone(self.ask("Is this already a question?"))
        self.assertIsNone(self.ask("   "))
        # A passive "was exiled" is not a definition of Napoleon.
        prompt, answer = self.ask("Napoleon was exiled to the island of Elba")
        self.assertTrue(prompt.startswith("Fill in the blank:"))
        self.assertIn(q.BLANK, prompt)
        self.assertNotIn(answer, prompt)
        # Pronouns never become the subject of a question.
        self.assertFalse(self.ask("It is raining in the city today")[0].startswith("What is it"))
        self.assertEqual(self.ask("The heart has 4 chambers and pumps blood"), ("Fill in the blank: The heart has _____ chambers and pumps blood", "4"))

    def test_notes_never_say_bit_n(self):
        items = q.note_questions("Mitochondria means powerhouse. In 1066 the Normans invaded England. Paris")
        self.assertEqual(len(items), 3)
        for item in items:
            self.assertNotIn("bit", item["prompt"].lower())

    def test_generic_fronts(self):
        self.assertTrue(q.is_generic_front("What should I recall from bit 3?"))
        self.assertTrue(q.is_generic_front("Study bit 12"))
        self.assertTrue(q.is_generic_front("Notes: P____", "Paris", "Notes"))
        self.assertFalse(q.is_generic_front("Capital of France", "Paris", "Geo"))


class HelperTests(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(q.answer_kind("1945"), "date")
        self.assertEqual(q.answer_kind("4 July 1776"), "date")
        self.assertEqual(q.answer_kind("1,000 metres"), "number")
        self.assertEqual(q.answer_kind("Paris"), "word")
        self.assertEqual(q.answer_kind("Dr Lee"), "short")

    def test_list_items(self):
        self.assertEqual(q.list_items("Mercury, Venus, Earth and Mars"), ["Mercury", "Venus", "Earth", "Mars"])
        self.assertEqual(q.list_items("- a\n- b\n- c"), ["a", "b", "c"])
        self.assertEqual(q.list_items("Salt and pepper"), [])
        self.assertEqual(q.list_items("The process plants use to turn light, water, and carbon dioxide into food."), [])

    def test_distractors_same_deck_same_kind_never_the_answer(self):
        pool = [("1066", "History"), ("Paris", "History"), ("1945", "History"), ("1945.", "Geo"), ("1789", "Geo"), ("PARIS", "Geo")]
        picked = q.pick_distractors("1945", pool, 3, q.Rng(1), "History")
        self.assertEqual(picked[0], "1066")  # same deck, same kind first
        self.assertEqual(picked[1], "1789")  # then the same kind from another deck
        self.assertNotIn("1945", picked)
        self.assertNotIn("1945.", picked)
        self.assertEqual(len({comparable_text(p) for p in picked}), len(picked))


class QuestionTests(unittest.TestCase):
    def test_each_type_is_well_formed(self):
        cards = deck()
        seen = set()
        for card in cards:
            for kind in q.TYPES:
                made = q.card_question(card, kind, cards, q.Rng(3))
                if made is None:
                    continue
                seen.add(made["type"])
                self.assertEqual(made["card_id"], card.id)
                self.assertTrue(made["prompt"] and made["answer"])
                if made["options"]:
                    self.assertEqual(made["options"][made["answer_index"]], made["answer"])
                    self.assertEqual(len({comparable_text(o) for o in made["options"]}), len(made["options"]))
                    self.assertGreaterEqual(len(made["options"]), 2)
                else:
                    self.assertTrue(made["typed"])
                    self.assertEqual(made["answer_index"], -1)
                self.assertTrue(q.check_answer(made, made["answer"]))
        self.assertEqual(seen, set(q.TYPES))

    def test_match_pairs_and_order(self):
        cards = deck()
        match = q.card_question(cards[0], "match", cards, q.Rng(1))
        self.assertIn(["Capital of France", "Paris"], match["pairs"])
        self.assertEqual(sorted(match["options"]), sorted(right for _left, right in match["pairs"]))
        order = q.card_question(cards[4], "order", cards, q.Rng(2))
        self.assertIn(order["answer"], ["Mercury", "Venus", "Earth", "Mars"])

    def test_generic_note_card_gets_a_real_question(self):
        cards = deck()
        made = q.card_question(cards[7], "recall", cards, q.Rng(1))
        self.assertEqual(made["prompt"], "When did this happen? The Treaty of Versailles was signed.")
        self.assertEqual(made["answer"], "1919")


class QuizTests(unittest.TestCase):
    def test_no_repeats_and_varied_types(self):
        cards = deck()
        for seed in range(20):
            quiz = q.build_quiz(cards, 8, q.Rng(seed), today=TODAY)
            self.assertEqual(len(quiz), 8)
            ids = [item["card_id"] for item in quiz]
            self.assertEqual(len(ids), len(set(ids)))
            for a, b in zip(quiz, quiz[1:]):
                self.assertNotEqual(a["type"], b["type"])
            self.assertGreaterEqual(len({item["type"] for item in quiz}), 4)

    def test_due_and_weak_cards_come_first(self):
        quiz = q.build_quiz(deck(), 1, q.Rng(4), today=TODAY)
        self.assertEqual(quiz[0]["card_id"], "fr")

    def test_recent_cards_are_avoided(self):
        cards = deck()
        first = q.build_quiz(cards, 5, q.Rng(1), today=TODAY)
        second = q.build_quiz(cards, 5, q.Rng(2), recent_ids=[item["id"] for item in first], today=TODAY)
        self.assertFalse({item["card_id"] for item in first} & {item["card_id"] for item in second})

    def test_types_filter_and_small_decks(self):
        cards = deck()
        quiz = q.build_quiz(cards, 6, q.Rng(1), types=["choice", "truefalse"], today=TODAY)
        self.assertTrue(all(item["type"] in ("choice", "truefalse") for item in quiz))
        self.assertEqual([item["type"] for item in q.build_quiz(cards[:1], 3, q.Rng(1), today=TODAY)], ["truefalse"])
        self.assertEqual(q.build_quiz([], 3, q.Rng(1), today=TODAY), [])
        buried = Card(id="b", front="x", back="y", buried_until="2027-01-01")
        self.assertEqual(q.build_quiz([buried], 3, q.Rng(1), today=TODAY), [])

    def test_note_cards(self):
        made = q.cards_from_note_questions(q.note_questions("Gold is Au. Iron is Fe."), "Chemistry", ai=True)
        self.assertEqual([(c.front, c.back) for c in made], [("What is Gold?", "Au"), ("What is Iron?", "Fe")])
        self.assertTrue(all(q.is_ai_card(c) for c in made))


if __name__ == "__main__":
    unittest.main()
