"""The memory puzzles: every kind makes playable rounds, scores fairly and saves results."""
import unittest

from memorypal import aiflow, puzzles


class PuzzleRounds(unittest.TestCase):
    def test_every_kind_at_every_level_can_be_answered_right(self):
        for kind in puzzles.KINDS:
            info = puzzles.puzzle(kind)
            for level in range(info["low"], info["high"] + 1):
                for seed in range(20):
                    made = puzzles.make_round(kind, level, seed)
                    if kind in ("sequence", "words", "routine"):
                        response = made["answer"]
                    elif kind == "search":
                        response = {"found": made["answer"], "wrong": 0}
                        self.assertEqual(made["tiles"].count(made["target"]), made["answer"])
                    else:
                        response = [question["answer"] for question in made["questions"]]
                        for question in made["questions"]:
                            self.assertIn(question["answer"], question["options"])
                            self.assertEqual(len(question["options"]), len(set(question["options"])), question)
                    self.assertTrue(puzzles.score(made, response)["right"], (kind, level, seed))

    def test_wrong_answers_do_not_pass(self):
        made = puzzles.make_round("words", 5, 3)
        wrong = [word for word in made["options"] if word not in made["answer"]]
        self.assertFalse(puzzles.score(made, wrong)["right"])
        # Tapping every word is not a way round it.
        self.assertFalse(puzzles.score(made, made["options"])["right"])
        seq = puzzles.make_round("sequence", 6, 3)
        self.assertFalse(puzzles.score(seq, seq["answer"][::-1] + "1")["right"])

    def test_routine_options_are_never_already_in_order(self):
        for seed in range(50):
            made = puzzles.make_round("routine", 3, seed)
            self.assertNotEqual(made["options"], made["answer"])

    def test_clue_keeps_the_answer_and_one_other(self):
        question = {"prompt": "?", "options": ["a", "b", "c", "d"], "answer": "c"}
        kept = puzzles.clue(question, 1)
        self.assertEqual(len(kept), 2)
        self.assertIn("c", kept)

    def test_set_material_is_used_when_there_is_enough(self):
        cards = [(f"Question {i}?", f"answer{i}") for i in range(8)]
        material = puzzles.material_from(cards)
        made = puzzles.make_round("words", 4, 1, material)
        self.assertTrue(all(word.startswith("answer") for word in made["answer"]))
        pairs = puzzles.make_round("pairs", 3, 1, material)
        self.assertTrue(all("→" in line for line in pairs["show"]))


class PuzzleResults(unittest.TestCase):
    def test_levels_follow_the_player_and_bests_are_kept(self):
        results = puzzles.record_game({}, "sequence", [{"level": 4, "right": True}, {"level": 5, "right": True}], "2026-11-20")
        self.assertEqual(results["kinds"]["sequence"]["level"], 6)
        self.assertEqual(results["kinds"]["sequence"]["best"], 5)
        results = puzzles.record_game(results, "sequence", [{"level": 6, "right": False}], "2026-11-21")
        self.assertEqual(results["kinds"]["sequence"]["level"], 5)
        self.assertEqual(results["kinds"]["sequence"]["best"], 5)
        self.assertEqual(puzzles.start_level(results, "sequence"), 5)
        # A success with help stays at the same level.
        self.assertEqual(puzzles.next_level("words", 5, True, helped=True), 5)

    def test_streak_never_breaks_before_the_day_is_over(self):
        results = {"days": ["2026-11-20", "2026-11-21", "2026-11-22"]}
        self.assertEqual(puzzles.streak(results, "2026-11-23"), 3)
        self.assertEqual(puzzles.streak(results, "2026-11-25"), 0)
        self.assertIn("Welcome back", puzzles.streak_text(results, "2026-11-25"))

    def test_todays_mix_mixes_skills_and_puts_the_story_first(self):
        for day in range(1, 28):
            today = f"2026-11-{day:02d}"
            mix = puzzles.todays_puzzles({}, today)
            self.assertEqual(len(set(mix)), 3)
            self.assertEqual(len({puzzles.puzzle(kind)["skill"] for kind in mix}), 3)
            self.assertEqual(mix, puzzles.todays_puzzles({}, today))
            everyday = puzzles.todays_puzzles({}, today, everyday=True)
            if "story" in everyday:
                self.assertEqual(everyday[0], "story")
            self.assertGreaterEqual(sum(puzzles.puzzle(kind)["skill"] == "everyday" for kind in everyday), 1)

    def test_played_puzzles_wait_their_turn(self):
        results = {}
        for kind in puzzles.KINDS:
            if kind != "sort":
                results = puzzles.record_game(results, kind, [{"level": 3, "right": True}], "2026-11-23")
        self.assertIn("sort", puzzles.todays_puzzles(results, "2026-11-23"))
        self.assertEqual(puzzles.weakest_puzzle(results, "2026-11-23"), "sort")

    def test_results_are_kept_with_device_preferences(self):
        prefs = aiflow.normalize_preferences({"puzzles": {"kinds": {"words": {"level": 5, "best": 6, "plays": 2, "last": "2026-11-23", "recent": [1, 0]}}}})
        self.assertEqual(prefs["puzzles"]["kinds"]["words"]["level"], 5)
        self.assertEqual(aiflow.normalize_preferences({"puzzles": "junk"})["puzzles"], {"kinds": {}, "days": []})


if __name__ == "__main__":
    unittest.main()
