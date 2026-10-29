import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import iconcache  # noqa: E402


class IconCacheTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "sub" / "icon-cache.bin"
        self.key = iconcache.shapes_key({"close": [("seg", 6, 6, 18, 18)]}, 0.9)

    def tearDown(self):
        self.folder.cleanup()

    def test_round_trip(self):
        icons = {("close", 2): bytearray(b"\x00\xff\x10\x20"), ("search", 1): bytearray(b"\x7f")}
        self.assertTrue(iconcache.save(self.path, self.key, icons))
        self.assertEqual(iconcache.load(self.path, self.key), icons)

    def test_changed_shapes_ignore_old_file(self):
        iconcache.save(self.path, self.key, {("close", 1): bytearray(b"\x01")})
        other = iconcache.shapes_key({"close": [("seg", 5, 6, 18, 18)]}, 0.9)
        self.assertNotEqual(other, self.key)
        self.assertEqual(iconcache.load(self.path, other), {})

    def test_missing_or_damaged_file_is_empty(self):
        self.assertEqual(iconcache.load(self.path, self.key), {})
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b"not a cache")
        self.assertEqual(iconcache.load(self.path, self.key), {})

    def test_wrong_sized_entries_are_skipped(self):
        iconcache.save(self.path, self.key, {("close", 2): bytearray(b"\x01"), ("search", 1): bytearray(b"\x02")})
        self.assertEqual(iconcache.load(self.path, self.key), {("search", 1): bytearray(b"\x02")})


if __name__ == "__main__":
    unittest.main()
