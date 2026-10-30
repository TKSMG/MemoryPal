import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("MEMORYPAL_DATA_DIR", tempfile.mkdtemp(prefix="memorypal-tests-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import richtext, setbuilder  # noqa: E402
from memorypal.ai import AI_NOTE  # noqa: E402
from memorypal.core import split_study_bits  # noqa: E402
from memorypal.models import Capture  # noqa: E402
from memorypal.questions import question_for_bit  # noqa: E402
from memorypal.store import MemoryStore  # noqa: E402


def styled(text):
    return [(span["text"], span["bold"], span["italic"], span["highlight"]) for span in richtext.spans(text)]


class MarksTests(unittest.TestCase):
    def test_bold_italic_and_highlight(self):
        self.assertEqual(styled("**big** and _slanted_ and ==bright=="), [
            ("big", True, False, False), (" and ", False, False, False), ("slanted", False, True, False),
            (" and ", False, False, False), ("bright", False, False, True),
        ])
        self.assertEqual(styled("*one* ***two***"), [("one", False, True, False), (" ", False, False, False), ("two", True, True, False)])

    def test_ordinary_text_is_left_alone(self):
        for text in ("2 * 3 * 4", "2*3*4", "snake_case_name", "a == b", "Q ==> A", "**not closed", "x => y", "**", "== =="):
            self.assertEqual(richtext.plain(text), text, text)
            self.assertFalse(richtext.has_marks(text), text)

    def test_plain_drops_the_marks(self):
        self.assertEqual(richtext.plain("The **heart** pumps _blood_ round the ==body=="), "The heart pumps blood round the body")

    def test_marked_words_and_blanks(self):
        self.assertEqual(richtext.marked("**Paris** is in _France_, on the ==Seine=="), ["Paris", "Seine"])
        self.assertEqual(richtext.blank_marked("The capital of France is ==Paris=="), ("The capital of France is _____", "Paris"))
        self.assertIsNone(richtext.blank_marked("Only _italic_ here"))

    def test_split_keeps_marks_whole(self):
        self.assertEqual(split_study_bits("**Hi. There** now. Fine"), ["**Hi**", "**There** now", "Fine"])
        self.assertEqual(split_study_bits("a ==> b. c"), ["a ==> b", "c"])
        self.assertEqual(richtext.balance_bits(["plain", "text"]), ["plain", "text"])


class ToggleTests(unittest.TestCase):
    def test_wraps_and_unwraps_the_selection(self):
        self.assertEqual(richtext.toggle("hello world", 0, 5, "bold"), ("**hello** world", 2, 7))
        self.assertEqual(richtext.toggle("**hello** world", 2, 7, "bold"), ("hello world", 0, 5))
        self.assertEqual(richtext.toggle("**hello** world", 0, 9, "bold"), ("hello world", 0, 5))
        self.assertEqual(richtext.toggle("say hi ", 3, 7, "highlight"), ("say ==hi== ", 6, 8))
        self.assertEqual(richtext.toggle("==hi==", 2, 4, "highlight"), ("hi", 0, 2))

    def test_italic_inside_bold(self):
        self.assertEqual(richtext.toggle("**hello**", 2, 7, "italic"), ("***hello***", 3, 8))
        self.assertEqual(richtext.toggle("***hello***", 3, 8, "italic"), ("**hello**", 2, 7))
        self.assertEqual(richtext.toggle("***hello***", 3, 8, "bold"), ("*hello*", 1, 6))
        self.assertEqual(richtext.toggle("_hi_", 1, 3, "italic"), ("hi", 0, 2))

    def test_no_selection_puts_an_empty_pair_at_the_cursor(self):
        self.assertEqual(richtext.toggle("ab ", 3, 3, "bold"), ("ab ****", 5, 5))


class NotesUseTheMarksTests(unittest.TestCase):
    def test_bold_or_highlighted_words_become_the_blank(self):
        made = question_for_bit("The capital of France is ==Paris==.")
        self.assertEqual((made["prompt"], made["answer"], made["type"]), ("Fill in the blank: The capital of France is _____", "Paris", "cloze"))
        self.assertEqual(made["source"], "The capital of France is Paris.")
        # Italics alone don't pick the answer; the usual rules run on the plain words.
        self.assertEqual(question_for_bit("_Paris_ is the capital of France")["answer"], question_for_bit("Paris is the capital of France")["answer"])

    def test_cards_from_notes_have_no_marks_but_keep_the_note(self):
        items = setbuilder.notes_to_items("**Mitochondria** make energy\n_Ribosomes_ make proteins\n**Q** => _A_", "Bit {n}")
        self.assertEqual([(i["prompt"], i["answer"]) for i in items], [("Bit 1", "Mitochondria make energy"), ("Bit 2", "Ribosomes make proteins"), ("Q", "A")])
        self.assertEqual(items[0]["source"], "**Mitochondria** make energy")
        made = setbuilder.notes_to_items("**Mitochondria** make energy", make_questions=True)[0]
        self.assertEqual((made["prompt"], made["answer"]), ("Fill in the blank: _____ make energy", "Mitochondria"))


class EditNotesTests(unittest.TestCase):
    def test_update_capture_resplits_and_keeps_the_ai_label(self):
        store = MemoryStore()
        store.reset()
        store.add_capture(Capture(title="Mine", notes="old", chunks=["old"]))
        store.add_capture(Capture(title="AI", notes=f"{AI_NOTE}\nold", chunks=["old"]))
        mine, made = store.captures[1], store.captures[0]
        store.update_capture(mine.id, "  New  title ", "**One** fact\nTwo ==facts==\n")
        self.assertEqual((mine.title, mine.notes, mine.chunks), ("New title", "**One** fact\nTwo ==facts==", ["**One** fact", "Two ==facts=="]))
        store.update_capture(made.id, "", "Edited")
        self.assertEqual((made.title, made.notes), ("AI", f"{AI_NOTE}\nEdited"))
        again = MemoryStore().find_capture(mine.id)
        self.assertEqual(again.chunks, ["**One** fact", "Two ==facts=="])
        self.assertIsNone(store.update_capture("missing", "x", "y"))


if __name__ == "__main__":
    unittest.main()
