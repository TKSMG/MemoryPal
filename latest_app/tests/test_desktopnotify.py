import os
import plistlib
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from xml.dom import minidom

os.environ.setdefault("MEMORYPAL_DATA_DIR", tempfile.mkdtemp(prefix="memorypal-tests-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import desktopnotify  # noqa: E402


def entry(title, body, minutes=0, open_="review"):
    return {"kind": "cards_due", "at": datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=minutes), "title": title, "body": body, "open": open_, "due": 1}


class DesktopNotifyTests(unittest.TestCase):
    def test_toast_xml_is_escaped(self):
        xml = desktopnotify.toast_xml(entry("Tom & Jerry's <test>", 'Say "hi"', open_='deck:A "set"'))
        parsed = minidom.parseString(xml)
        texts = [node.firstChild.data for node in parsed.getElementsByTagName("text")]
        self.assertEqual(texts, ["Tom & Jerry's <test>", 'Say "hi"'])
        self.assertEqual(parsed.documentElement.getAttribute("launch"), 'memorypal:deck:A "set"')

    def test_windows_payload_has_local_offsets_and_short_tags(self):
        payload = desktopnotify.windows_payload([entry("A", "B", 60), entry("C", "D", 120)])
        self.assertEqual([item["tag"] for item in payload["items"]], ["mp0", "mp1"])
        self.assertRegex(payload["items"][0]["at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")
        self.assertEqual(payload["group"], "memorypal")

    def test_signature_changes_with_content(self):
        one = [entry("A", "B", 60)]
        self.assertEqual(desktopnotify.signature(one), desktopnotify.signature(list(one)))
        self.assertNotEqual(desktopnotify.signature(one), desktopnotify.signature([dict(one[0], body="C")]))

    def test_mac_plist_lists_each_time_once(self):
        first = entry("A", "B", 60)
        plist = desktopnotify.mac_plist([first, dict(first, title="Other"), entry("C", "D", 180)], Path("/tmp/notify.sh"))
        self.assertEqual(len(plist["StartCalendarInterval"]), 2)
        plistlib.dumps(plist)

    @unittest.skipIf(sys.platform == "win32", "needs a POSIX shell")
    def test_mac_script_shows_due_ones_once_with_quotes_intact(self):
        folder = Path(tempfile.mkdtemp(prefix="memorypal-notify-"))
        planned = [entry("It's \"due\" $HOME", "Body `x` 'y'", 0), entry("Later", "Not yet", 120), entry("Old", "Too late", -180)]
        script = desktopnotify.mac_script(planned, folder).replace("/usr/bin/osascript -e 'on run argv' -e 'display notification (item 2 of argv) with title \"MemoryPal\" subtitle (item 1 of argv)' -e 'end run'", "printf '%s|%s\\n'")
        path = folder / "notify.sh"
        path.write_text(script, encoding="utf-8")
        first = subprocess.run(["/bin/sh", str(path)], capture_output=True, text=True, check=True).stdout
        self.assertEqual(first, "It's \"due\" $HOME|Body `x` 'y'\n")
        again = subprocess.run(["/bin/sh", str(path)], capture_output=True, text=True, check=True).stdout
        self.assertEqual(again, "")

    @unittest.skipUnless(desktopnotify.supported() and os.environ.get("CI"), "schedules real notifications: CI on Windows or Mac only")
    def test_system_takes_the_week_and_lets_it_go(self):
        folder = Path(tempfile.mkdtemp(prefix="memorypal-notify-"))
        planned = [entry("MemoryPal CI check", "Scheduled by the desktop tests", 24 * 60 * 3)]
        try:
            self.assertTrue(desktopnotify.schedule(planned, folder, wait=True))
        finally:
            self.assertTrue(desktopnotify.schedule([], folder, wait=True))
        if sys.platform == "darwin":
            self.assertFalse(desktopnotify.mac_agent_path().exists())

    def test_unsupported_platform_does_nothing(self):
        if desktopnotify.supported():
            self.skipTest("this platform schedules for real")
        self.assertFalse(desktopnotify.schedule([entry("A", "B", 60)], tempfile.mkdtemp()))


if __name__ == "__main__":
    unittest.main()
