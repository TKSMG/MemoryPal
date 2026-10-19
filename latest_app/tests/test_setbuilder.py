import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import setbuilder  # noqa: E402


class NotesToItemsTests(unittest.TestCase):
    def test_question_answer_lines_become_cards(self):
        items = setbuilder.notes_to_items("Capital of France => Paris\nH2O :: water\nhola\thello")
        self.assertEqual([(i["prompt"], i["answer"], i["kind"]) for i in items], [
            ("Capital of France", "Paris", "qa"), ("H2O", "water", "qa"), ("hola", "hello", "qa"),
        ])

    def test_plain_notes_use_the_prompt_template_in_order(self):
        items = setbuilder.notes_to_items("Mitochondria release energy\nQ => A\nRibosomes make proteins", "Recall fact {n} of {total}")
        self.assertEqual([i["prompt"] for i in items], ["Recall fact 1 of 2", "Q", "Recall fact 2 of 2"])
        self.assertEqual(items[2]["answer"], "Ribosomes make proteins")
        self.assertEqual(items[0]["kind"], "note")

    def test_template_without_number_gets_a_counter(self):
        items = setbuilder.notes_to_items("one\ntwo", "What is this?")
        self.assertEqual([i["prompt"] for i in items], ["What is this? (1/2)", "What is this? (2/2)"])

    def test_single_paragraph_splits_into_sentences(self):
        items = setbuilder.notes_to_items("Water boils at 100 C. Ice melts at 0 C.")
        self.assertEqual([i["answer"] for i in items], ["Water boils at 100 C", "Ice melts at 0 C"])

    def test_blank_template_falls_back(self):
        items = setbuilder.notes_to_items("only note", "  ")
        self.assertEqual(items[0]["prompt"], "What should I recall from bit 1?")

    def test_empty_text(self):
        self.assertEqual(setbuilder.notes_to_items("   "), [])


class TypedItemTests(unittest.TestCase):
    def test_needs_a_question(self):
        self.assertIsNone(setbuilder.typed_item("  ", "answer"))

    def test_tidies_spacing(self):
        self.assertEqual(setbuilder.typed_item(" Who  wrote Hamlet? ", " Shakespeare "), {"prompt": "Who wrote Hamlet?", "answer": "Shakespeare", "kind": "qa"})

    def test_clean_set_name(self):
        self.assertEqual(setbuilder.clean_set_name("  Chapter   3  "), "Chapter 3")
        self.assertEqual(setbuilder.clean_set_name(None), "")


if __name__ == "__main__":
    unittest.main()
