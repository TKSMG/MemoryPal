"""Regression tests for the v70 correctness, data-safety and security fixes."""

import json
import os
import sys
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path

# Point the store at a throwaway data folder before memorypal.paths is imported.
os.environ.setdefault("MEMORYPAL_DATA_DIR", tempfile.mkdtemp(prefix="memorypal-tests-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import paths, techniques  # noqa: E402
from memorypal.core import (  # noqa: E402
    add_days,
    answer_assessment,
    extract_document_text,
    parse_prompt_answer_lines,
    powershell_exe,
    split_study_bits,
    today_iso,
)
from memorypal.models import Card  # noqa: E402
from memorypal.pdftext import PdfText, PdfTooLarge, inflate  # noqa: E402
from memorypal.planning import build_multi_day_plan  # noqa: E402
from memorypal.store import MemoryStore, backup_path  # noqa: E402


class StoreCase(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.store.reset()


class DataSafetyTests(StoreCase):
    def test_damaged_file_falls_back_to_last_good_save_and_is_kept(self):
        self.store.add_card(Card(front="Keep me", back="Please"))
        self.store.save()  # the backup now holds "Keep me"
        self.store.data_file.write_text("{ this is not json", encoding="utf-8")
        reloaded = MemoryStore()
        self.assertIn("Keep me", [card.front for card in reloaded.cards])
        self.assertIsNotNone(reloaded.recovered_from)
        self.assertTrue(Path(reloaded.recovered_from).exists(), "the damaged file must be kept for recovery")

    def test_only_a_backup_left_after_a_crash_is_still_loaded(self):
        self.store.add_card(Card(front="Survivor", back="Yes"))
        self.store.save()
        self.store.data_file.unlink()
        self.assertTrue(backup_path(self.store.data_file).exists())
        self.assertIn("Survivor", [card.front for card in MemoryStore().cards])

    def test_damaged_fields_do_not_crash_loading(self):
        raw = json.loads(self.store.data_file.read_text(encoding="utf-8"))
        raw.update({"activity": [1, 2], "daily_goal": 0, "nav_order": "oops", "cards": {"not": "a list"}})
        self.store.data_file.write_text(json.dumps(raw), encoding="utf-8")
        reloaded = MemoryStore()
        self.assertEqual(reloaded.activity, {})
        self.assertEqual(reloaded.daily_goal, 1)
        self.assertEqual(reloaded.nav_order, [])
        self.assertEqual(reloaded.cards, [])


class CardEditingTests(StoreCase):
    def test_edit_keeps_schedule(self):
        card = self.store.cards[0]
        self.store.schedule(card, 4)
        before = (card.interval, card.next_review, card.repetitions)
        self.store.update_card(card, front="New question", back="New answer", deck="  ", next_review="1999-01-01")
        saved = next(c for c in MemoryStore().cards if c.id == card.id)
        self.assertEqual((saved.front, saved.back, saved.deck), ("New question", "New answer", "General"))
        self.assertEqual((saved.interval, saved.next_review, saved.repetitions), before)

    def test_deleted_card_stays_deleted(self):
        doomed = self.store.cards[0].id
        self.assertEqual(self.store.delete_cards([doomed]), 1)
        self.assertNotIn(doomed, [card.id for card in MemoryStore().cards])

    def test_card_deleted_here_is_not_revived_by_another_window(self):
        other = MemoryStore()
        doomed = self.store.cards[0].id
        other.schedule(other.cards[1], 4)  # the other window writes first
        self.store.delete_cards([doomed])  # so this save has to merge
        self.assertNotIn(doomed, [card.id for card in MemoryStore().cards])
        # ...and the other window's review survived the merge.
        self.assertEqual(MemoryStore().practiced, 1)

    def test_reset_progress_makes_cards_new(self):
        card = self.store.cards[0]
        self.store.schedule(card, 1)
        self.store.reset_progress([card.id])
        self.assertEqual((card.repetitions, card.lapses, card.last_result, card.next_review), (0, 0, "New", today_iso()))


class SchedulerTests(StoreCase):
    def test_spreading_never_shrinks_a_successful_interval(self):
        for suffix in range(60):
            card = Card(id=f"card-{suffix}", front="Q", back="A", repetitions=3, interval=6, next_review=today_iso())
            self.store.cards.append(card)
            self.assertGreater(self.store.next_interval(card, 3), 6, card.id)

    def test_buried_cards_are_not_counted_due_in_deck_summary(self):
        card = self.store.cards[0]
        card.next_review = today_iso()
        self.store.bury_card(card)
        deck = card.deck or "General"
        due_ids = {c.id for c in self.store.due_cards(deck)}
        self.assertNotIn(card.id, due_ids)
        self.assertEqual(self.store.deck_summary()[deck]["due"], len(due_ids))


class MultiDayPlanTests(StoreCase):
    def test_todays_backlog_is_not_counted_again_on_later_days(self):
        self.store.cards = [Card(front=f"Q{n}", back="A", repetitions=2, interval=5, next_review=add_days(-3)) for n in range(40)]
        self.store.save()
        days = build_multi_day_plan(self.store, 5, "All decks", set(), "long_term")
        self.assertEqual(days[0]["due"], 40)
        self.assertTrue(all(day["due"] == 0 for day in days[1:]), [day["due"] for day in days])


class TextSplittingTests(unittest.TestCase):
    def test_years_and_decimals_survive(self):
        self.assertEqual(split_study_bits("1945 was the end of the war\n1066 was the Norman conquest"),
                         ["1945 was the end of the war", "1066 was the Norman conquest"])
        self.assertEqual(split_study_bits("Pi is about 3.14. It never ends."), ["Pi is about 3.14", "It never ends"])

    def test_list_markers_are_still_removed(self):
        self.assertEqual(split_study_bits("1. apples 2. pears 3. plums"), ["apples", "pears", "plums"])
        self.assertEqual(split_study_bits("- one\n* two\n• three"), ["one", "two", "three"])

    def test_slash_n_inside_words_is_not_a_line_break(self):
        self.assertEqual(split_study_bits("salt/nitrogen"), ["salt/nitrogen"])
        self.assertEqual(split_study_bits("first /n second"), ["first", "second"])

    def test_tab_separated_cards_import(self):
        self.assertEqual(parse_prompt_answer_lines("mitochondria\tpowerhouse of the cell"),
                         [{"prompt": "mitochondria", "answer": "powerhouse of the cell"}])

    def test_numbered_prompt_keeps_its_year(self):
        self.assertEqual(parse_prompt_answer_lines("1984 :: Orwell"), [{"prompt": "1984", "answer": "Orwell"}])


class SmartCheckTests(unittest.TestCase):
    def test_wrong_year_is_not_a_typo(self):
        result = answer_assessment("The war ended in 1954", "The war ended in 1945")
        self.assertNotIn(result["bucket"], ("Easy", "Good"))
        self.assertIn("1945", result["detail"])

    def test_right_number_in_other_words_passes(self):
        self.assertIn(answer_assessment("1945", "It ended in 1945")["bucket"], ("Again", "Review", "Good", "Easy"))
        self.assertIn(answer_assessment("in 1945 the war ended", "The war ended in 1945")["bucket"], ("Easy", "Good"))

    def test_negated_answer_does_not_pass(self):
        result = answer_assessment("the reaction is reversible", "the reaction is not reversible")
        self.assertIn(result["bucket"], ("Again", "Review"))

    def test_matching_negation_still_passes(self):
        self.assertEqual(answer_assessment("it is not reversible", "the reaction is not reversible")["bucket"] in ("Easy", "Good"), True)


class TechniqueWordingTests(unittest.TestCase):
    def test_slash_words_keep_their_letters(self):
        self.assertEqual(techniques.parse_ideas("salt/nitrogen"), ["salt", "nitrogen"])

    def test_pegs_read_naturally(self):
        text = techniques.peg_list([f"idea{n}" for n in range(1, 8)])
        self.assertIn("a bundle of sticks", text)
        self.assertNotIn("a sticks", text)
        self.assertNotIn("a heaven", text)


class ProfileFolderTests(unittest.TestCase):
    def test_names_sharing_a_folder_are_refused(self):
        name = "Clash Test Person"
        ok, _ = paths.create_profile(name)
        self.assertTrue(ok)
        try:
            for twin in ("clash-test-person", "Clash  Test Person!", "CLASH TEST PERSON"):
                ok, message = paths.create_profile(twin)
                self.assertFalse(ok, twin)
                self.assertIn("too close", message)
        finally:
            paths.delete_profile(name)


class UntrustedFileTests(unittest.TestCase):
    def test_inflate_refuses_a_decompression_bomb(self):
        bomb = zlib.compress(b"\0" * (40 * 1024 * 1024))
        with self.assertRaises(PdfTooLarge):
            inflate(bomb)

    def test_pdf_with_a_bomb_stream_is_refused(self):
        bomb = zlib.compress(b"\0" * (40 * 1024 * 1024))
        data = b"%PDF-1.5\n1 0 obj\n<< /Filter /FlateDecode >>\nstream\n" + bomb + b"\nendstream\nendobj\n"
        pdf = PdfText(data)
        with self.assertRaises(PdfTooLarge):
            pdf.stream_data(pdf.objects[1])

    def test_oversized_docx_is_refused(self):
        folder = Path(tempfile.mkdtemp(prefix="memorypal-docx-"))
        path = folder / "huge.docx"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("word/document.xml", b"<w/>" + b" " * (65 * 1024 * 1024))
        with self.assertRaises(RuntimeError):
            extract_document_text(path)

    def test_powershell_is_called_by_full_path_on_windows(self):
        if sys.platform.startswith("win"):
            self.assertTrue(Path(powershell_exe()).is_absolute())


if __name__ == "__main__":
    unittest.main()
