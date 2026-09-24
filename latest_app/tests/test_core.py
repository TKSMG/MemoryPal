import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal.core import answer_assessment  # noqa: E402

BACK = "Reviewing information at increasing intervals so recall strengthens over time."
FRONT = "What is spaced repetition?"


class AnswerAssessmentTests(unittest.TestCase):
    def assertBucket(self, response, expected, bucket, context=""):
        result = answer_assessment(response, expected, context)
        self.assertEqual(result["bucket"], bucket, f"{response!r} vs {expected!r}: {result}")
        return result

    def test_exact_answer_is_easy_even_with_context(self):
        self.assertBucket(BACK, BACK, "Easy")
        self.assertBucket(BACK, BACK, "Easy", context=FRONT)
        self.assertBucket(BACK, BACK, "Easy", context=f"{FRONT} Dashboard > Review association media")

    def test_short_exact_answers_are_easy(self):
        for answer in ("42", "7", "B12", "Dr Lee", "Room 4"):
            self.assertBucket(answer, answer, "Easy")
            self.assertBucket(answer.lower() + ".", answer, "Easy")

    def test_wrong_short_answer_is_again(self):
        self.assertBucket("41", "42", "Again")
        self.assertBucket("no", "yes", "Again")

    def test_small_typos_and_abbreviations_get_credit(self):
        self.assertIn(self.assertBucket("recieve", "receive", "Easy")["bucket"], {"Easy"})
        result = answer_assessment("reviewing info at increasing intervals over time", BACK)
        self.assertIn(result["bucket"], {"Easy", "Good"})

    def test_partial_answer_is_not_rated_strong(self):
        result = answer_assessment("increasing intervals", BACK)
        self.assertIn(result["bucket"], {"Review", "Again"})
        self.assertIn("Missing key cues", result["detail"])

    def test_empty_response_needs_response(self):
        self.assertEqual(answer_assessment("   ", BACK)["label"], "Needs response")

    def test_context_is_used_when_there_is_no_saved_answer(self):
        result = answer_assessment("the blue pill after breakfast", "", context="Blue pill after breakfast")
        self.assertEqual(result["bucket"], "Easy")


if __name__ == "__main__":
    unittest.main()
