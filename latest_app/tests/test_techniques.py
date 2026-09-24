import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import techniques  # noqa: E402

ITEMS = [f"idea{n}" for n in range(1, 31)]


def anchors(text, pattern):
    return re.findall(pattern, text)


class TechniqueTests(unittest.TestCase):
    def test_parse_ideas_accepts_common_separators(self):
        self.assertEqual(techniques.parse_ideas("a, b\nc; d | e / f"), list("abcdef"))

    def test_every_technique_handles_no_ideas(self):
        for name in ("acronym", "story", "peg_list", "palace", "chunk_map", "link_chain"):
            self.assertEqual(getattr(techniques, name)([]), techniques.EMPTY)

    def test_palace_never_reuses_a_location(self):
        places = anchors(techniques.palace(ITEMS), r"at the (.+?)\. Make")
        self.assertEqual(len(places), 30)
        self.assertEqual(len(set(places)), 30)

    def test_pegs_never_repeat_and_explain_the_rhyme(self):
        text = techniques.peg_list(ITEMS[:20])
        pegs = anchors(text, r"stuck to a (.+?)\.")
        self.assertEqual(len(set(pegs)), 20)
        self.assertIn("One rhymes with sun", text)

    def test_story_scenes_are_unique(self):
        scenes = anchors(techniques.story(ITEMS), r"Picture idea\d+ (.+?)\. It")
        self.assertEqual(len(set(scenes)), 30)

    def test_acronym_includes_matching_acrostic(self):
        text = techniques.acronym(["mitosis", "meiosis", "chromosomes"])
        self.assertTrue(text.startswith("MMC"))
        sentence = text.split("(acrostic): ", 1)[1].split(".")[0].split()
        self.assertEqual([word[0] for word in sentence], ["M", "M", "C"])


if __name__ == "__main__":
    unittest.main()
