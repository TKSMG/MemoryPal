import os
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

os.environ.setdefault("MEMORYPAL_DATA_DIR", tempfile.mkdtemp(prefix="memorypal-tests-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import feedback  # noqa: E402
from memorypal.models import FeedbackEntry  # noqa: E402


def entries(count=2):
    return [FeedbackEntry(rating=4 + index % 2, category="Bug", page="Study Plan", note=f"Note {index}: buttons flash & jump") for index in range(count)]


class ReportTests(unittest.TestCase):
    def test_report_lists_notes_and_details_but_no_profile(self):
        subject, body = feedback.compose_report(entries(), feedback.system_details({"text_size": "Large", "more_time": True}, "dark"))
        self.assertIn("2 notes", subject)
        self.assertIn("average rating 4.5/5", subject)
        self.assertIn("Note 1: buttons flash & jump", body)
        self.assertIn("Text size: Large", body)
        self.assertIn("more time", body)

    def test_email_links_are_addressed_and_encoded(self):
        subject, body = feedback.compose_report(entries(), feedback.system_details())
        mail = feedback.mailto_url(subject, body)
        self.assertTrue(mail.startswith("mailto:memorypal09@gmail.com?"))
        self.assertEqual(unquote(mail.split("body=")[1]), body)
        gmail = parse_qs(urlparse(feedback.gmail_url(subject, body)).query)
        self.assertEqual(gmail["to"], ["memorypal09@gmail.com"])
        self.assertEqual(gmail["body"], [body])

    def test_long_reports_are_shortened_for_links_and_point_to_the_file(self):
        subject, body = feedback.compose_report(entries(80), feedback.system_details())
        short = feedback.link_body(body, "MemoryPal-feedback.txt")
        self.assertLessEqual(len(short), feedback.MAX_LINK_BODY + 5)
        self.assertIn("MemoryPal-feedback.txt", short)
        self.assertEqual(feedback.link_body("short", "x.txt"), "short")

    def test_saved_file_has_address_subject_and_body(self):
        subject, body = feedback.compose_report(entries(), feedback.system_details())
        with tempfile.TemporaryDirectory() as folder:
            path = feedback.save_report(Path(folder) / "report.txt", subject, body)
            text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("To: memorypal09@gmail.com\nSubject: MemoryPal feedback"))
        self.assertIn("Note 0", text)


class FakeResponse:
    def __init__(self, raw):
        self.raw = raw

    def read(self):
        return self.raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class SendTests(unittest.TestCase):
    def send_with(self, reply=None, error=None):
        seen = {}

        def opener(request, timeout):
            seen["request"] = request
            if error:
                raise error
            return FakeResponse(reply)

        subject, body = feedback.compose_report(entries(), feedback.system_details())
        return feedback.send_report(subject, body, "tester@example.com", opener=opener), seen

    def test_sends_report_as_json_to_the_feedback_address(self):
        import json

        result, seen = self.send_with(b'{"success": "true", "message": "The form was submitted successfully."}')
        self.assertTrue(result.ok)
        request = seen["request"]
        self.assertEqual(request.get_method(), "POST")
        self.assertIn(feedback.FEEDBACK_EMAIL, request.full_url)
        payload = json.loads(request.data)
        self.assertIn("Note 1", payload["message"])
        self.assertEqual(payload["email"], "tester@example.com")
        self.assertTrue(payload["_subject"].startswith("MemoryPal feedback"))

    def test_activation_and_errors_are_told_apart(self):
        result, _seen = self.send_with(b'{"success": "false", "message": "This form needs Activation. We\'ve sent you an email."}')
        self.assertEqual(result.status, "activation")
        result, _seen = self.send_with(b"<html>oops</html>")
        self.assertEqual(result.status, "error")

    def test_no_connection_is_reported_as_offline(self):
        import urllib.error

        result, _seen = self.send_with(error=urllib.error.URLError("no route"))
        self.assertEqual(result.status, "offline")
        self.assertFalse(result.ok)

    def test_email_check(self):
        self.assertTrue(feedback.looks_like_email("a.b@example.co.uk"))
        for text in ("", "not an email", "a@b", "@example.com", "a@.com", "a b@example.com"):
            self.assertFalse(feedback.looks_like_email(text), text)


if __name__ == "__main__":
    unittest.main()
