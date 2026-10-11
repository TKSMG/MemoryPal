"""Desktop <-> phone sync check, using both real implementations.

    python tools\\parity\\sync_interop.py

1. Starts a local fake Supabase over HTTP.
2. The laptop (Python, memorypal.cloud) creates the account, adds a card,
   reviews twice, changes a setting, and syncs.
3. The phone (TypeScript, mobile/src/cloud via Jest) signs in, syncs, checks
   what arrived, adds a card, reviews the laptop's card, and syncs again.
4. The laptop syncs and checks the phone's changes arrived intact.
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "latest_app" / "tests"))

from fake_supabase import FakeSupabase  # noqa: E402
from fake_supabase_server import serve  # noqa: E402
from memorypal import cloud  # noqa: E402
from memorypal.core import today_iso  # noqa: E402
from memorypal.models import Card, sample_cards  # noqa: E402
from memorypal.store import default_payload  # noqa: E402

EMAIL, PASSWORD = "pat@example.com", "correct horse battery"


def check(condition, message):
    print(("  ok   " if condition else "  FAIL ") + message)
    if not condition:
        raise SystemExit(1)


def main():
    fake = FakeSupabase(confirm_email=False)
    server, url = serve(fake)
    client = cloud.CloudClient(url, fake.key)
    client.sign_up(EMAIL, PASSWORD)

    folder = Path(tempfile.mkdtemp(prefix="memorypal-laptop-"))
    account = cloud.Account(folder, client)
    account.remember(client.sign_in(EMAIL, PASSWORD))
    payload = default_payload()
    payload["cards"] = [asdict(card) for card in sample_cards()]
    payload["cards"].insert(0, asdict(Card(id="from-laptop", deck="Geography", front="Capital of France?", back="Paris")))
    payload["activity"] = {today_iso(): 2}
    payload["practiced"] = 2
    payload["daily_goal"] = 25
    box = {"payload": payload}

    def write(new_payload):
        box["payload"] = new_payload

    print("laptop: first sync")
    account.sync(lambda: copy.deepcopy(box["payload"]), write)

    print("phone: sync, check, change, sync (Jest)")
    env = dict(os.environ, MEMORYPAL_INTEROP_URL=url, MEMORYPAL_INTEROP_STEP="phone")
    result = subprocess.run("npx jest __tests__/cloud.interop.test.ts --ci", cwd=ROOT / "mobile", env=env, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    if result.returncode != 0:
        print(output[-3000:])
    check(result.returncode == 0 and "1 passed" in output, "phone test passed")

    print("laptop: sync again and check")
    account.sync(lambda: copy.deepcopy(box["payload"]), write)
    final = box["payload"]
    cards = {card["id"]: card for card in final["cards"]}
    check("from-phone" in cards and cards["from-phone"]["back"] == "Hello", "the phone's new card arrived on the laptop")
    check(cards["from-laptop"]["repetitions"] == 2, "the phone's two reviews of the laptop's card arrived")
    check(final["activity"].get(today_iso()) == 5, "today's reviews add up across both devices (2 + 3)")
    check(final["practiced"] == 5, "total reviews add up")
    check(sum(1 for card_id in cards if card_id.startswith("sample-")) == 4, "starter cards were merged, not duplicated")
    check(final["daily_goal"] == 25, "the laptop's setting survived the round trip")
    server.shutdown()
    print("desktop <-> phone sync: all checks passed")


if __name__ == "__main__":
    main()
