import json
import re
import unittest
from pathlib import Path

from memorypal.constants import APP_VERSION

ROOT = Path(__file__).resolve().parents[2]


class VersionTests(unittest.TestCase):
    def test_settings_version_matches_the_release_files(self):
        pyproject = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)
        phone = json.loads((ROOT / "mobile" / "app.json").read_text(encoding="utf-8"))["expo"]["version"]
        inno = re.search(r'#define MyAppVersion "([^"]+)"', (ROOT / "installer" / "inno" / "MemoryPal.iss").read_text(encoding="utf-8")).group(1)
        self.assertEqual(APP_VERSION, pyproject)
        self.assertEqual(APP_VERSION, phone)
        self.assertEqual(APP_VERSION, inno)


if __name__ == "__main__":
    unittest.main()
