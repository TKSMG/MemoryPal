import os
import sys
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import ai, aiflow, cloud, questions, setbuilder  # noqa: E402
from memorypal.models import Card, Capture  # noqa: E402

QUESTIONS = [
    {"type": "short", "question": "Which organelle releases energy?", "answer": "Mitochondria", "options": [], "page": 2},
    {"type": "short", "question": "What does the diagram show?", "answer": "A plant cell", "options": [], "page": None},
    {"type": "truefalse", "question": "Osmosis moves water.", "answer": "True", "options": ["True", "False"], "page": None},
]


class ConsentTests(unittest.TestCase):
    def test_on_by_default_but_a_saved_answer_is_kept(self):
        prefs = aiflow.normalize_preferences(None)
        self.assertTrue(aiflow.has_consent(prefs))
        self.assertEqual(aiflow.gate(prefs, signed_in=True), "ok")
        self.assertTrue(aiflow.has_consent(aiflow.normalize_preferences({"quiz_deck": "Bio"})))
        off = aiflow.normalize_preferences(aiflow.withdraw_consent(prefs))
        self.assertFalse(aiflow.has_consent(off))
        self.assertEqual(aiflow.gate(off, signed_in=True), "consent")

    def test_sign_in_comes_first(self):
        allowed = aiflow.give_consent(aiflow.normalize_preferences(None), "2026-10-19T10:00:00")
        self.assertEqual(aiflow.gate(allowed, signed_in=False), "sign_in")
        self.assertEqual(aiflow.gate(aiflow.normalize_preferences(None), signed_in=False), "sign_in")
        self.assertEqual(aiflow.gate(allowed, signed_in=True, configured=False), "not_configured")

    def test_allowed_then_withdrawn(self):
        allowed = aiflow.give_consent({}, "2026-10-19T10:00:00")
        self.assertTrue(aiflow.has_consent(allowed))
        self.assertEqual(allowed["ai_consent_at"], "2026-10-19T10:00:00")
        self.assertEqual(aiflow.gate(allowed, signed_in=True), "ok")
        withdrawn = aiflow.withdraw_consent(allowed)
        self.assertFalse(aiflow.has_consent(withdrawn))
        self.assertEqual(withdrawn["ai_consent_at"], "")
        # Turning the switch back on without the screen isn't consent.
        self.assertFalse(aiflow.has_consent(dict(withdrawn, ai_enabled=True)))

    def test_an_older_consent_screen_asks_again(self):
        old = dict(aiflow.give_consent({}), ai_consent_version=aiflow.CONSENT_VERSION - 1)
        self.assertFalse(aiflow.has_consent(old))

    def test_damaged_preferences_are_off(self):
        prefs = aiflow.normalize_preferences({"ai_enabled": "yes", "ai_consent_version": True, "quiz_recent": "x", "ai_remaining": -3})
        self.assertFalse(aiflow.has_consent(prefs))
        self.assertEqual(prefs["quiz_recent"], [])
        self.assertIsNone(prefs["ai_remaining"])


class ErrorMessageTests(unittest.TestCase):
    def test_ai_errors_keep_their_friendly_words(self):
        for code in ("offline", "limit_reached", "file_too_large", "not_configured", "busy"):
            error = ai.AIError(code)
            self.assertEqual(aiflow.error_message(error), ai.FRIENDLY[code])
            self.assertNotIn("Error", aiflow.error_title(error))

    def test_network_failures_read_as_offline(self):
        for error in (urllib.error.URLError("down"), TimeoutError(), ConnectionResetError(), OSError("socket")):
            self.assertEqual(aiflow.error_message(error), ai.FRIENDLY["offline"])
            self.assertEqual(aiflow.error_title(error), "You're offline")

    def test_unexpected_errors_never_show_python(self):
        message = aiflow.error_message(KeyError("questions"))
        self.assertNotIn("KeyError", message)
        self.assertNotIn("questions", message)
        self.assertIn("try again", message.lower())

    def test_sign_in_problems(self):
        self.assertTrue(aiflow.needs_sign_in(ai.AIError("not_signed_in")))
        self.assertTrue(aiflow.needs_sign_in(cloud.CloudError("Signed out", "signed_out")))
        self.assertFalse(aiflow.needs_sign_in(ai.AIError("offline")))


class JobTests(unittest.TestCase):
    def test_result_after_the_worker_finishes(self):
        gate = threading.Event()
        job = aiflow.Job(lambda: (gate.wait(5), {"remaining": 4})[1]).start()
        self.assertEqual(job.state(), "running")
        gate.set()
        job.thread.join(5)
        self.assertEqual(job.state(), "done")
        self.assertEqual(job.result, {"remaining": 4})

    def test_failure_is_kept_for_the_message(self):
        def boom():
            raise ai.AIError("busy")
        job = aiflow.Job(boom)
        job.run()  # the worker's body, without a thread
        self.assertEqual(job.state(), "failed")
        self.assertEqual(aiflow.error_message(job.error), ai.FRIENDLY["busy"])

    def test_cancel_throws_the_answer_away(self):
        job = aiflow.Job(lambda: {"questions": []})
        job.cancel()
        job.run()
        self.assertEqual(job.state(), "cancelled")

    def test_uses_the_given_thread_factory(self):
        made = []

        class FakeThread:
            def __init__(self, target, daemon):
                made.append(daemon)
                self.target = target

            def start(self):
                self.target()

        job = aiflow.Job(lambda: 7, thread_factory=FakeThread).start()
        self.assertEqual(made, [True])
        self.assertEqual((job.state(), job.result), ("done", 7))

    def test_progress_text_reassures_as_it_runs(self):
        self.assertEqual(aiflow.progress_text("notes", 1), "Making notes…")
        self.assertIn("minute", aiflow.progress_text("questions", 12))
        self.assertIn("cancel", aiflow.progress_text("questions", 45))


class RemainingTests(unittest.TestCase):
    def test_only_today_counts(self):
        prefs = aiflow.remember_remaining({}, 3, "2026-10-19")
        self.assertEqual(aiflow.remaining_today(prefs, "2026-10-19"), 3)
        self.assertIsNone(aiflow.remaining_today(prefs, "2026-10-20"))
        self.assertEqual(aiflow.remember_remaining(prefs, None, "2026-10-19")["ai_remaining"], 3)

    def test_wording(self):
        self.assertEqual(aiflow.remaining_text(None), "")
        self.assertEqual(aiflow.remaining_text(1), "1 AI use left today")
        self.assertEqual(aiflow.remaining_text(9), "9 AI uses left today")
        self.assertIn("reset tomorrow", aiflow.remaining_text(0))


class StagingTests(unittest.TestCase):
    def test_rows_are_ai_cards(self):
        rows = aiflow.staged_from_questions(QUESTIONS, "Biology", "Chapter 3")
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(aiflow.is_ai_item(row) for row in rows))
        self.assertTrue(all(row["association"].startswith(ai.AI_NOTE) for row in rows))
        self.assertEqual(rows[2]["prompt"], "True or false: Osmosis moves water.")
        card = Card(deck="Biology", front=rows[0]["prompt"], back=rows[0]["answer"], pathway=rows[0]["pathway"], association=rows[0]["association"])
        self.assertTrue(questions.is_ai_card(card))
        self.assertTrue(ai.is_ai_card(card))
        self.assertFalse(questions.is_ai_card(Card(deck="Biology", front="Q", back="A", pathway="Set > Biology > Card 1")))
        self.assertFalse(aiflow.is_ai_item({"prompt": "Q", "answer": "A", "kind": "qa"}))

    def test_typed_notes_have_no_pages(self):
        rows = aiflow.staged_from_questions(QUESTIONS, "Biology")
        self.assertIsNone(rows[0]["page"])
        self.assertNotIn("From page", rows[0]["association"])
        self.assertEqual((rows[0]["image"], rows[0]["text_file"]), ("", ""))

    def test_picture_source_goes_on_every_card(self):
        rows = aiflow.staged_from_questions(QUESTIONS, "Biology", source="/attachments/cell.png")
        self.assertTrue(rows)
        self.assertTrue(all(row["image"] == "/attachments/cell.png" for row in rows))
        self.assertTrue(all(row["text_file"] == "" for row in rows))

    def test_pdf_page_picture_or_page_note(self):
        rows = aiflow.staged_from_questions(QUESTIONS, "Biology", source="/attachments/notes.pdf", pictures={2: "/attachments/notes-page2.png"})
        self.assertEqual(rows[0]["image"], "/attachments/notes-page2.png")
        self.assertTrue(all(row["text_file"] == "/attachments/notes.pdf" for row in rows))
        rows = aiflow.staged_from_questions(QUESTIONS, "Biology", source="/attachments/notes.pdf")
        self.assertEqual(rows[0]["image"], "")
        self.assertIn("From page 2.", rows[0]["association"])

    def test_notes_capture(self):
        notes = {"title": "Cells", "sections": [{"heading": "Organelles", "bullets": ["Mitochondria make ATP."]}], "key_terms": [{"term": "ATP", "definition": "Energy carrier"}]}
        fields = aiflow.notes_capture_fields(notes, "Biology", "/attachments/notes.pdf")
        self.assertEqual((fields["title"], fields["deck"]), ("Cells", "Biology"))
        self.assertEqual(fields["chunks"], ["Organelles: Mitochondria make ATP.", "ATP => Energy carrier"])
        self.assertEqual(fields["text_file"], "/attachments/notes.pdf")
        capture = Capture(**fields)
        self.assertTrue(aiflow.is_ai_capture(capture))
        self.assertFalse(aiflow.is_ai_capture(Capture(title="Mine", notes="My own notes")))

    def test_report_note(self):
        note = aiflow.report_note("card", "Q: x\nA: y")
        self.assertTrue(note.startswith(aiflow.REPORT_CATEGORY))
        self.assertIn("Q: x", note)
        self.assertLess(len(aiflow.report_note("notes", "z" * 5000)), 1700)


class PdfPageTests(unittest.TestCase):
    def make_pdf(self, folder):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow isn't installed")
        page1 = Image.new("RGB", (400, 300), (255, 255, 255))
        page2 = Image.new("RGB", (400, 300), (30, 120, 200))
        path = Path(folder) / "slides.pdf"
        page1.save(path, "PDF", save_all=True, append_images=[page2])
        return path

    def test_page_picture_with_pypdf(self):
        try:
            import pypdf  # noqa: F401
        except ImportError:
            self.skipTest("pypdf isn't installed")
        with tempfile.TemporaryDirectory() as folder:
            pdf = self.make_pdf(folder)
            with mock.patch.dict(sys.modules, {"pypdfium2": None}):
                saved = aiflow.page_images(pdf, [2, 9], folder, "slides")
            self.assertEqual(list(saved), [2])
            self.assertTrue(Path(saved[2]).exists())
            self.assertIsNone(aiflow.render_pdf_page(pdf, 0, Path(folder) / "x.png"))

    def test_missing_or_broken_pdf_gives_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            broken = Path(folder) / "broken.pdf"
            broken.write_bytes(b"not a pdf")
            self.assertIsNone(aiflow.render_pdf_page(broken, 1, Path(folder) / "out.png"))
            self.assertEqual(aiflow.page_images(Path(folder) / "missing.pdf", [1], folder, "m"), {})


class QuizHistoryTests(unittest.TestCase):
    def test_next_round_avoids_the_last(self):
        cards = [Card(id=f"c{i}", deck="Capitals", front=f"Country {i}", back=f"City {i}") for i in range(12)]
        first = questions.build_quiz(cards, 5, questions.Rng(1))
        prefs = aiflow.remember_round({}, [item["id"] for item in first])
        self.assertEqual(prefs["quiz_recent"], [item["id"] for item in first])
        second = questions.build_quiz(cards, 5, questions.Rng(2), recent_ids=prefs["quiz_recent"])
        self.assertFalse({item["card_id"] for item in first} & {item["card_id"] for item in second})

    def test_history_is_capped(self):
        prefs = aiflow.remember_round({}, [f"c{i}:choice" for i in range(500)])
        self.assertEqual(len(prefs["quiz_recent"]), aiflow.QUIZ_RECENT_MAX)


class StorePreferencesTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.patch = mock.patch.dict(os.environ, {"MEMORYPAL_DATA_DIR": self.folder.name})
        self.patch.start()
        from memorypal import paths
        import importlib
        importlib.reload(paths)
        from memorypal import store
        importlib.reload(store)
        self.store_module = store

    def tearDown(self):
        self.patch.stop()
        from memorypal import paths, store
        import importlib
        importlib.reload(paths)
        importlib.reload(store)
        self.folder.cleanup()

    def test_preferences_are_saved_and_survive_a_sync(self):
        store = self.store_module.MemoryStore()
        store.preferences = aiflow.give_consent(store.preferences, "2026-10-19T10:00:00")
        store.save()
        again = self.store_module.MemoryStore()
        self.assertTrue(aiflow.has_consent(again.preferences))
        # A synced payload carries no preferences: this device keeps its own.
        payload = again.payload()
        payload.pop("preferences")
        again.replace_with(payload)
        self.assertTrue(aiflow.has_consent(again.preferences))


class SetBuilderQuestionTests(unittest.TestCase):
    def test_notes_become_real_questions(self):
        items = setbuilder.notes_to_items("In 1066, the Normans invaded England\nhello there", make_questions=True)
        self.assertEqual(items[0]["prompt"], "When did this happen? The Normans invaded England.")
        self.assertEqual(items[0]["answer"], "1066")
        self.assertEqual(items[1]["prompt"], "What should I recall from bit 2?")


if __name__ == "__main__":
    unittest.main()
