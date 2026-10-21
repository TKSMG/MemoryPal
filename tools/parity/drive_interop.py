"""Desktop <-> phone sync through a drive, using both real implementations.

    python tools/parity/drive_interop.py

The "drive" is a local folder: the laptop (Python, memorypal.drive) and the
phone (TypeScript, mobile/src/cloud/drive.ts via Jest) each write their own
device file there and read the other's.

1. The laptop adds a card, reviews twice, changes a setting, and syncs.
2. The phone syncs, checks what arrived, adds a card, reviews the laptop's
   card twice, deletes a starter card, and syncs again.
3. The laptop syncs and checks the phone's changes arrived intact.
"""

import copy
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("MEMORYPAL_DATA_DIR", tempfile.mkdtemp(prefix="memorypal-interop-"))
sys.path.insert(0, str(ROOT / "latest_app"))

from memorypal import cloud, drive  # noqa: E402
from memorypal.core import today_iso  # noqa: E402
from memorypal.models import Card, sample_cards  # noqa: E402
from memorypal.store import default_payload  # noqa: E402


def check(condition, message):
    print(("  ok   " if condition else "  FAIL ") + message)
    if not condition:
        raise SystemExit(1)


def main():
    folder = Path(tempfile.mkdtemp(prefix="memorypal-drive-"))
    files = drive.FolderFiles(folder)
    state = cloud.SyncState(Path(tempfile.mkdtemp(prefix="memorypal-laptop-")))
    payload = default_payload()
    payload["cards"] = [asdict(card) for card in sample_cards()]
    payload["cards"].insert(0, asdict(Card(id="from-laptop", deck="Geography", front="Capital of France?", back="Paris")))
    payload["activity"] = {today_iso(): 2}
    payload["practiced"] = 2
    payload["daily_goal"] = 25
    box = {"payload": payload}

    def sync_laptop():
        drive.sync_files(files, state, "google-1", lambda: copy.deepcopy(box["payload"]), lambda new: box.update(payload=new))

    print("laptop: first sync")
    sync_laptop()

    print("phone: sync, check, change, sync (Jest)")
    env = dict(os.environ, MEMORYPAL_DRIVE_FOLDER=str(folder))
    result = subprocess.run("npx jest __tests__/drive.interop.test.ts --ci", cwd=ROOT / "mobile", env=env, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    if result.returncode != 0:
        print(output[-3000:])
    check(result.returncode == 0 and "1 passed" in output, "phone test passed")

    print("laptop: sync again and check")
    sync_laptop()
    final = box["payload"]
    cards = {card["id"]: card for card in final["cards"]}
    check("from-phone" in cards and cards["from-phone"]["back"] == "Hello", "the phone's new card arrived on the laptop")
    check(cards["from-laptop"]["repetitions"] == 2, "the phone's two reviews of the laptop's card arrived")
    check("sample-chunking" not in cards, "the phone's delete arrived")
    check(final["activity"].get(today_iso()) == 4, "today's reviews add up across both devices (2 + 2)")
    check(final["daily_goal"] == 25, "the laptop's setting survived the round trip")
    check(len(list(folder.iterdir())) == 2, "one file per device")
    print("desktop <-> phone drive sync: all checks passed")


if __name__ == "__main__":
    main()
