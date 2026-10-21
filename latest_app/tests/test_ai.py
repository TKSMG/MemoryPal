import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import ai, cloud  # noqa: E402


class Reply:
    def __init__(self, body):
        self.body = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeOpener:
    """Records requests and answers with a canned reply or HTTP error."""

    def __init__(self, body=None, status=200):
        self.body, self.status, self.requests = body, status, []

    def __call__(self, request, timeout=None):
        self.requests.append((request, timeout))
        if self.status != 200:
            raw = self.body if isinstance(self.body, bytes) else json.dumps(self.body or {}).encode("utf-8")
            raise urllib.error.HTTPError(request.full_url, self.status, "error", {}, io.BytesIO(raw))
        return Reply(self.body)

    def sent(self):
        return json.loads(self.requests[-1][0].data.decode("utf-8"))


ENV = {"MEMORYPAL_SUPABASE_URL": "https://proj.supabase.co/", "MEMORYPAL_SUPABASE_KEY": "sb_publishable_x"}


@mock.patch.dict(os.environ, ENV)
class CallTests(unittest.TestCase):
    def test_notes_request_and_parsing(self):
        opener = FakeOpener({"ok": True, "action": "notes", "remaining": 19, "result": {
            "title": " Cells ", "sections": [{"heading": "Parts", "bullets": ["Nucleus", "", 4]}, {"heading": "", "bullets": []}],
            "key_terms": [{"term": "Cell", "definition": "Unit of life"}, {"term": "Lonely"}],
        }})
        notes = ai.make_notes("token-1", text=" Cells are small. ", title="Bio", opener=opener)
        request, timeout = opener.requests[0]
        self.assertEqual(request.full_url, "https://proj.supabase.co/functions/v1/ai")
        self.assertEqual(request.get_header("Authorization"), "Bearer token-1")
        self.assertEqual(request.get_header("Apikey"), "sb_publishable_x")
        self.assertEqual(timeout, ai.TIMEOUT)
        self.assertEqual(opener.sent(), {"action": "notes", "text": "Cells are small.", "title": "Bio"})
        self.assertEqual(notes, {"title": "Cells", "sections": [{"heading": "Parts", "bullets": ["Nucleus"]}], "key_terms": [{"term": "Cell", "definition": "Unit of life"}], "remaining": 19})
        self.assertIn("Nucleus", ai.notes_text(notes))

    def test_questions_with_a_file_are_validated(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = Path(folder) / "lecture.PDF"
            pdf.write_bytes(b"%PDF-1.4 tiny")
            opener = FakeOpener({"ok": True, "remaining": 3, "result": {"questions": [
                {"type": "short", "question": "What is a cell?", "answer": "Unit of life", "page": 2},
                {"type": "choice", "question": "Powerhouse?", "answer": "Mitochondria", "options": ["Nucleus", "mitochondria", "Ribosome", "Golgi", "Wall"]},
                {"type": "choice", "question": "Too few?", "answer": "A", "options": ["B"]},
                {"type": "truefalse", "question": "Cells have walls", "answer": "FALSE"},
                {"type": "cloze", "question": "The nucleus holds DNA", "answer": "DNA"},
                {"type": "essay", "question": "Write", "answer": "No"},
                {"type": "short", "question": "Existing front", "answer": "x"},
            ]}})
            result = ai.make_questions("t", file_path=pdf, count=50, avoid=["existing FRONT"], opener=opener)
        sent = opener.sent()
        self.assertEqual(sent["file"]["mime_type"], "application/pdf")
        self.assertEqual(sent["count"], 30)
        self.assertEqual(sent["avoid"], ["existing FRONT"])
        questions = result["questions"]
        self.assertEqual([q["type"] for q in questions], ["short", "choice", "truefalse", "cloze"])
        self.assertEqual(questions[0]["page"], 2)
        self.assertEqual(questions[1]["options"], ["Mitochondria", "Nucleus", "Ribosome", "Golgi"])
        self.assertEqual(questions[2]["answer"], "False")
        self.assertEqual(questions[3]["question"], "The nucleus holds _____")
        self.assertEqual(result["remaining"], 3)

        made = ai.questions_to_cards(questions, "Biology", title="Lecture 1")
        self.assertEqual(made[0]["page"], 2)
        card = made[0]["card"]
        self.assertEqual((card.deck, card.front, card.back), ("Biology", "What is a cell?", "Unit of life"))
        self.assertTrue(ai.is_ai_card(card))
        self.assertIn("check it", card.association)
        self.assertIn("page 2", card.association)
        self.assertEqual(made[2]["card"].front, "True or false: Cells have walls")

    def test_error_codes_become_friendly_messages(self):
        cases = [
            (401, {"ok": False, "error": "not_signed_in"}, "not_signed_in"),
            (429, {"ok": False, "error": "limit_reached"}, "limit_reached"),
            (503, {"ok": False, "error": "busy"}, "busy"),
            (503, {"ok": False, "error": "busy_today"}, "busy_today"),
            (413, b"not json", "file_too_large"),
            (415, {"ok": False, "error": "unsupported_file"}, "unsupported_file"),
            (502, {"ok": False, "error": "provider_error"}, "provider_error"),
            (422, {"ok": False, "error": "blocked"}, "blocked"),
            (500, {"error": "something new"}, "provider_error"),
        ]
        for status, body, code in cases:
            with self.assertRaises(ai.AIError) as caught:
                ai.make_notes("t", text="x", opener=FakeOpener(body, status))
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(caught.exception.message, ai.FRIENDLY[code])

    def test_offline_and_garbled(self):
        def offline(_request, timeout=None):
            raise urllib.error.URLError("down")

        with self.assertRaises(ai.AIError) as caught:
            ai.make_notes("t", text="x", opener=offline)
        self.assertEqual(caught.exception.code, "offline")
        with self.assertRaises(ai.AIError) as caught:
            ai.make_notes("t", text="x", opener=FakeOpener(b"<html>"))
        self.assertEqual(caught.exception.code, "bad_answer")

    def test_checks_before_sending(self):
        opener = FakeOpener({"ok": True})
        for call, code in [
            (lambda: ai.make_notes("", text="x", opener=opener), "not_signed_in"),
            (lambda: ai.make_notes("t", text="   ", opener=opener), "bad_request"),
            (lambda: ai.make_notes("t", file_path="notes.docx", opener=opener), "unsupported_file"),
        ]:
            with self.assertRaises(ai.AIError) as caught:
                call()
            self.assertEqual(caught.exception.code, code)
        with tempfile.TemporaryDirectory() as folder:
            big = Path(folder) / "big.png"
            with open(big, "wb") as handle:
                handle.truncate(ai.MAX_FILE_BYTES + 1)
            with self.assertRaises(ai.AIError) as caught:
                ai.make_notes("t", file_path=big, opener=opener)
            self.assertEqual(caught.exception.code, "file_too_large")
        self.assertEqual(opener.requests, [])

    def test_account_and_session_tokens(self):
        session = cloud.Session("abc", "refresh", 9e12, "u1", "a@b.co")
        self.assertEqual(ai.access_token(session), "abc")

        class SignedOut:
            def active_session(self):
                raise cloud.CloudError("Sign in to sync your cards.", "signed_out")

        with self.assertRaises(ai.AIError) as caught:
            ai.access_token(SignedOut())
        self.assertEqual(caught.exception.code, "signed_out")

    @mock.patch.dict(os.environ, {"MEMORYPAL_SUPABASE_URL": "", "MEMORYPAL_SUPABASE_KEY": ""})
    def test_not_configured(self):
        with mock.patch.object(cloud.cloud_config, "SUPABASE_URL", ""):
            with self.assertRaises(ai.AIError) as caught:
                ai.make_notes("t", text="x", opener=FakeOpener({}))
        self.assertEqual(caught.exception.code, "not_configured")


if __name__ == "__main__":
    unittest.main()
