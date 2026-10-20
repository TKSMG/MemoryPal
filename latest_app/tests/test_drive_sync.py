"""Sync through the person's own Google Drive: device files, stamps, and the move off the MemoryPal cloud."""

import copy
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from dataclasses import asdict
from pathlib import Path
from unittest import mock

os.environ.setdefault("MEMORYPAL_DATA_DIR", tempfile.mkdtemp(prefix="memorypal-tests-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_supabase import FakeSupabase  # noqa: E402
from memorypal import cloud, drive, sync  # noqa: E402
from memorypal.core import today_iso  # noqa: E402
from memorypal.models import Card, sample_cards  # noqa: E402
from memorypal.store import default_payload  # noqa: E402

EMAIL, PASSWORD = "pat@example.com", "correct horse battery 7"


def new_payload(*cards):
    payload = default_payload()
    payload["cards"] = [asdict(card) for card in (cards or sample_cards())]
    return payload


class Clock:
    """Milliseconds that only move when told to, shared by every device in a test."""

    def __init__(self):
        self.ms = 1_800_000_000_000

    def __call__(self):
        self.ms += 1000
        return self.ms


class Device:
    """One installed copy of MemoryPal syncing through a (folder) drive."""

    def __init__(self, drive_folder, clock, payload=None, google_user="google-1"):
        self.folder = Path(tempfile.mkdtemp(prefix="memorypal-device-"))
        self.files = drive.FolderFiles(drive_folder)
        self.state = cloud.SyncState(self.folder)
        self.payload = payload or new_payload()
        self.clock = clock
        self.google_user = google_user

    def sync(self, mode=None):
        def write(payload):
            self.payload = payload

        return drive.sync_files(self.files, self.state, self.google_user, lambda: copy.deepcopy(self.payload), write, mode=mode, now_ms=self.clock())

    def card(self, card_id):
        return next((card for card in self.payload["cards"] if card["id"] == card_id), None)

    def review(self, card_id, **fields):
        self.card(card_id).update(fields)
        day = today_iso()
        self.payload["activity"][day] = self.payload["activity"].get(day, 0) + 1
        self.payload["practiced"] += 1


class StampTests(unittest.TestCase):
    def test_stamps_follow_the_clock_and_never_go_back(self):
        first = sync.next_stamp("", "laptop", 5000)
        self.assertEqual(first, "0000000005000:000000:laptop")
        # A phone whose clock is behind still makes a newer stamp.
        behind = sync.next_stamp(first, "phone", 1000)
        self.assertGreater(behind, first)
        self.assertEqual(behind, "0000000005000:000001:phone")

    def test_malformed_file_content_is_skipped(self):
        content = {"records": {
            "card:a": ["0000000005000:000000:x", {"front": "ok"}],
            "card:b": ["yesterday", {"front": "bad stamp"}],
            "card:c": ["0000000005000:000000:x", "not an object"],
            "virus:d": ["0000000005000:000000:x", {}],
            "card:e": ["0000000005000:000000:x", None],
        }}
        self.assertEqual(sync.entries_of(content), {"card:a": ["0000000005000:000000:x", {"front": "ok"}], "card:e": ["0000000005000:000000:x", None]})
        self.assertEqual(sync.entries_of(["not", "a", "dict"]), {})

    def test_newest_copy_wins_across_files(self):
        old = {"card:a": ["0000000001000:000000:p", {"v": 1}]}
        new = {"card:a": ["0000000002000:000000:l", {"v": 2}]}
        remote, stamps = sync.remote_from_files([new, old])
        self.assertEqual(remote, {"card:a": {"v": 2}})
        self.assertEqual(stamps["card:a"], new["card:a"][0])


class TwoDeviceDriveTests(unittest.TestCase):
    def setUp(self):
        self.drive = Path(tempfile.mkdtemp(prefix="memorypal-drive-"))
        self.clock = Clock()
        self.laptop = Device(self.drive, self.clock)
        self.phone = Device(self.drive, self.clock)

    def both_sync(self):
        self.laptop.sync()
        self.phone.sync()
        self.laptop.sync()

    def test_each_device_writes_only_its_own_file(self):
        self.both_sync()
        names = sorted(path.name for path in self.drive.iterdir())
        self.assertEqual(names, sorted([sync.file_name(self.laptop.state.device_id), sync.file_name(self.phone.state.device_id)]))

    def test_a_new_card_reaches_the_other_device(self):
        self.laptop.payload["cards"].insert(0, asdict(Card(id="c1", front="Capital of France?", back="Paris")))
        self.both_sync()
        self.assertEqual(self.phone.card("c1")["back"], "Paris")

    def test_starter_cards_are_not_duplicated(self):
        self.both_sync()
        self.assertEqual(len(self.phone.payload["cards"]), 4)
        self.assertEqual(len(self.laptop.payload["cards"]), 4)

    def test_edit_here_and_review_there_both_survive(self):
        self.both_sync()
        card_id = self.laptop.payload["cards"][0]["id"]
        self.laptop.card(card_id)["back"] = "Edited on the laptop"
        self.phone.review(card_id, repetitions=1, interval=1)
        self.both_sync()
        self.phone.sync()
        for device in (self.laptop, self.phone):
            self.assertEqual(device.card(card_id)["back"], "Edited on the laptop")
            self.assertEqual(device.card(card_id)["repetitions"], 1)

    def test_reviews_on_both_devices_add_up(self):
        self.both_sync()
        card_id = self.laptop.payload["cards"][0]["id"]
        self.laptop.review(card_id, repetitions=1)
        self.phone.review(self.phone.payload["cards"][1]["id"], repetitions=1)
        self.both_sync()
        self.phone.sync()
        day = today_iso()
        self.assertEqual(self.laptop.payload["activity"][day], 2)
        self.assertEqual(self.phone.payload["activity"][day], 2)

    def test_deleting_reaches_the_other_device(self):
        self.both_sync()
        card_id = self.laptop.payload["cards"][0]["id"]
        self.laptop.payload["cards"] = [card for card in self.laptop.payload["cards"] if card["id"] != card_id]
        self.both_sync()
        self.assertIsNone(self.phone.card(card_id))

    def test_a_device_away_for_a_while_cant_undo_newer_changes(self):
        tablet = Device(self.drive, self.clock)
        self.both_sync()
        tablet.sync()
        card_id = self.laptop.payload["cards"][0]["id"]
        self.laptop.card(card_id)["back"] = "v2"
        self.laptop.sync()
        self.phone.sync()  # the phone takes v2 and copies it into its own file
        self.laptop.card(card_id)["back"] = "v3"
        self.laptop.sync()
        # The tablet's old copy and the phone's v2 must not beat v3.
        tablet.sync()
        self.phone.sync()
        self.assertEqual(tablet.card(card_id)["back"], "v3")
        self.assertEqual(self.phone.card(card_id)["back"], "v3")

    def test_a_deleted_card_stays_deleted_for_a_device_that_was_away(self):
        tablet = Device(self.drive, self.clock)
        self.both_sync()
        tablet.sync()
        card_id = self.laptop.payload["cards"][0]["id"]
        self.laptop.payload["cards"] = [card for card in self.laptop.payload["cards"] if card["id"] != card_id]
        self.laptop.sync()
        tablet.sync()
        self.assertIsNone(tablet.card(card_id))

    def test_unchanged_files_are_not_read_again_and_nothing_is_rewritten(self):
        self.both_sync()
        self.phone.sync()
        with mock.patch.object(self.laptop.files, "read", side_effect=AssertionError("read")), \
                mock.patch.object(self.laptop.files, "write", side_effect=AssertionError("write")):
            result = self.laptop.sync()
        self.assertEqual(result["pushed"], 0)

    def test_a_damaged_file_is_skipped_not_read_as_deletions(self):
        self.both_sync()
        (self.drive / sync.file_name("broken")).write_text("{not json")
        before = len(self.laptop.payload["cards"])
        self.laptop.sync()
        self.assertEqual(len(self.laptop.payload["cards"]), before)

    def test_a_removed_file_is_written_again(self):
        self.both_sync()
        for path in self.drive.iterdir():
            path.unlink()
        self.laptop.sync()
        fresh = Device(self.drive, self.clock, payload=new_payload(Card(id="x", front="x", back="x")))
        fresh.sync()
        self.assertEqual(len(fresh.payload["cards"]), 5)

    def test_switching_google_accounts_asks_first(self):
        self.both_sync()
        other_drive = Path(tempfile.mkdtemp(prefix="memorypal-drive-"))
        self.laptop.files = drive.FolderFiles(other_drive)
        self.laptop.google_user = "google-2"
        with self.assertRaises(cloud.CloudError) as caught:
            self.laptop.sync()
        self.assertEqual(caught.exception.code, "other_account")
        self.assertEqual(list(other_drive.iterdir()), [])
        self.laptop.sync(mode="merge")
        self.assertEqual(len(list(other_drive.iterdir())), 1)
        self.assertEqual(self.laptop.state.drive_user, "google-2")


class MoveFromCloudTests(unittest.TestCase):
    """The first Drive sync of a signed-in profile brings the MemoryPal cloud's records along, then removes them there."""

    def setUp(self):
        self.server = FakeSupabase(confirm_email=False)
        self.client = cloud.CloudClient("https://example.supabase.co", self.server.key, opener=self.server.open)
        self.client.sign_up(EMAIL, PASSWORD)
        self.drive_folder = Path(tempfile.mkdtemp(prefix="memorypal-drive-"))
        self.env = mock.patch.dict(os.environ, {"MEMORYPAL_SUPABASE_URL": "https://example.supabase.co", "MEMORYPAL_SUPABASE_KEY": self.server.key})
        self.env.start()
        self.addCleanup(self.env.stop)

    def account(self, linked=True):
        folder = Path(tempfile.mkdtemp(prefix="memorypal-device-"))
        link = drive.DriveLink(folder, sign_in=mock.Mock())
        if linked:
            link.saved = {"refresh_token": "r", "user_id": "google-1", "email": "pat@gmail.com"}
        account = cloud.Account(folder, client=self.client, drive_link=link)
        account.remember(self.client.sign_in(EMAIL, PASSWORD))
        return account

    def sync(self, account, holder):
        def write(payload):
            holder["payload"] = payload

        with mock.patch.object(drive, "configured", return_value=True):
            return account.sync(lambda: copy.deepcopy(holder["payload"]), write, files=drive.FolderFiles(self.drive_folder))

    def test_cloud_records_move_into_the_drive_and_leave_the_cloud(self):
        # A device on the old version put a card in the MemoryPal cloud.
        old = self.account(linked=False)
        old_holder = {"payload": new_payload(Card(id="cloud-only", front="From the cloud", back="yes"))}
        cloud.sync_profile(self.client, old.active_session(), old.state, lambda: copy.deepcopy(old_holder["payload"]), lambda p: old_holder.update(payload=p))
        self.assertTrue(self.server.rows_for(EMAIL))

        account = self.account()
        holder = {"payload": new_payload(Card(id="local", front="Here", back="yes"))}
        self.sync(account, holder)
        ids = {card["id"] for card in holder["payload"]["cards"]}
        self.assertIn("cloud-only", ids)
        self.assertIn("local", ids)
        self.assertEqual(self.server.rows_for(EMAIL), {})
        content = json.loads(next(self.drive_folder.iterdir()).read_text())
        self.assertIn("card:cloud-only", content["records"])
        self.assertFalse(account.state.cloud_cleanup)

        # Later syncs leave the MemoryPal cloud alone.
        with mock.patch.object(self.client, "pull", side_effect=AssertionError("pulled")):
            self.sync(account, holder)

    def test_removing_from_the_cloud_is_retried(self):
        account = self.account()
        holder = {"payload": new_payload()}
        with mock.patch.object(self.client, "delete_sync_records", side_effect=cloud.CloudError("offline", "offline")):
            self.sync(account, holder)
        self.assertTrue(account.state.cloud_cleanup)
        self.sync(account, holder)
        self.assertFalse(account.state.cloud_cleanup)

    def test_not_connected_yet_says_so(self):
        account = self.account(linked=False)
        with mock.patch.object(drive, "configured", return_value=True):
            self.assertFalse(account.can_sync)
            with self.assertRaises(cloud.CloudError) as caught:
                account.sync(lambda: new_payload(), lambda p: None)
        self.assertEqual(caught.exception.code, "drive_not_linked")


class FakeGoogle:
    """Google's token endpoint and the Drive API, in memory."""

    def __init__(self):
        self.files = {}
        self.version = 0
        self.tokens_issued = 0
        self.valid = set()
        self.fail_with = None

    def open(self, request, timeout=None):
        url = urllib.parse.urlsplit(request.full_url)
        if self.fail_with:
            status, body = self.fail_with
            self.fail_with = None
            raise urllib.error.HTTPError(request.full_url, status, "error", {}, io.BytesIO(body.encode()))
        if url.netloc == "oauth2.googleapis.com":
            form = urllib.parse.parse_qs(request.data.decode())
            if url.path == "/revoke":
                return io.BytesIO(b"")
            if form.get("refresh_token") == ["gone"]:
                raise urllib.error.HTTPError(request.full_url, 400, "bad", {}, io.BytesIO(b'{"error":"invalid_grant"}'))
            self.tokens_issued += 1
            token = f"access-{self.tokens_issued}"
            self.valid = {token}
            return io.BytesIO(json.dumps({"access_token": token, "expires_in": 3600}).encode())
        if request.get_header("Authorization") not in {f"Bearer {t}" for t in self.valid}:
            raise urllib.error.HTTPError(request.full_url, 401, "unauthorized", {}, io.BytesIO(b"{}"))
        query = urllib.parse.parse_qs(url.query)
        parts = url.path.split("/")
        method = request.get_method()
        if url.path == "/drive/v3/files" and method == "GET":
            assert query["spaces"] == ["appDataFolder"]
            listing = [{"id": i, "name": f["name"], "version": str(f["version"]), "size": str(len(f["body"]))} for i, f in self.files.items()]
            return io.BytesIO(json.dumps({"files": listing}).encode())
        if url.path.startswith("/drive/v3/files/") and query.get("alt") == ["media"]:
            return io.BytesIO(self.files[parts[-1]]["body"])
        if url.path == "/upload/drive/v3/files" and method == "POST":
            body = request.data
            boundary = request.get_header("Content-type").split("boundary=")[1].encode()
            sections = body.split(b"--" + boundary)
            meta = json.loads(sections[1].split(b"\r\n\r\n", 1)[1].rstrip(b"\r\n"))
            assert meta["parents"] == ["appDataFolder"]
            content = sections[2].split(b"\r\n\r\n", 1)[1][:-2]
            self.version += 1
            file_id = f"f{len(self.files) + 1}"
            self.files[file_id] = {"name": meta["name"], "body": content, "version": self.version}
            return io.BytesIO(json.dumps({"id": file_id, "version": str(self.version)}).encode())
        if url.path.startswith("/upload/drive/v3/files/") and method == "PATCH":
            file_id = parts[-1]
            if file_id not in self.files:
                raise urllib.error.HTTPError(request.full_url, 404, "missing", {}, io.BytesIO(b"{}"))
            self.version += 1
            self.files[file_id].update(body=request.data, version=self.version)
            return io.BytesIO(json.dumps({"id": file_id, "version": str(self.version)}).encode())
        raise AssertionError(f"unexpected {method} {url.path}")


class DriveApiTests(unittest.TestCase):
    def setUp(self):
        self.google = FakeGoogle()
        self.folder = Path(tempfile.mkdtemp(prefix="memorypal-device-"))
        sign_in = drive.GoogleSignIn("client", "secret", opener=self.google.open)
        self.link = drive.DriveLink(self.folder, sign_in=sign_in)
        self.link.remember({"refresh_token": "r", "user_id": "g1", "email": "pat@gmail.com"})

    def test_writes_reads_and_lists_through_the_api(self):
        files = self.link.files(self.google.open)
        state = cloud.SyncState(self.folder)
        holder = {"payload": new_payload()}
        drive.sync_files(files, state, "g1", lambda: copy.deepcopy(holder["payload"]), lambda p: holder.update(payload=p))
        self.assertEqual(len(self.google.files), 1)
        stored = json.loads(next(iter(self.google.files.values()))["body"])
        self.assertEqual(stored["device"], state.device_id)
        # A second device sees the cards.
        other = cloud.SyncState(Path(tempfile.mkdtemp()))
        other_holder = {"payload": new_payload(Card(id="z", front="z", back="z"))}
        drive.sync_files(files, other, "g1", lambda: copy.deepcopy(other_holder["payload"]), lambda p: other_holder.update(payload=p))
        self.assertEqual(len(other_holder["payload"]["cards"]), 5)
        # And an update goes to the same file.
        holder["payload"]["cards"][0]["back"] = "changed"
        drive.sync_files(files, state, "g1", lambda: copy.deepcopy(holder["payload"]), lambda p: holder.update(payload=p))
        self.assertEqual(len(self.google.files), 2)

    def test_an_expired_access_token_is_renewed_once(self):
        files = self.link.files(self.google.open)
        files.list()
        self.google.valid = set()  # Google expired it early
        files.list()
        self.assertEqual(self.google.tokens_issued, 2)

    def test_a_full_drive_says_so(self):
        files = self.link.files(self.google.open)
        files.list()
        self.google.fail_with = (403, '{"error":{"errors":[{"reason":"storageQuotaExceeded"}]}}')
        with self.assertRaises(cloud.CloudError) as caught:
            files.write("memorypal-x.json", b"{}")
        self.assertEqual(caught.exception.code, "drive_full")

    def test_access_taken_back_in_google_disconnects(self):
        self.link.remember({"refresh_token": "gone", "user_id": "g1", "email": "pat@gmail.com"})
        with self.assertRaises(cloud.CloudError) as caught:
            self.link.files(self.google.open).list()
        self.assertEqual(caught.exception.code, "drive_signed_out")
        self.assertFalse(self.link.linked)
        self.assertFalse(drive.DriveLink(self.folder).linked)

    def test_the_connection_is_kept_and_never_plain_on_windows(self):
        reloaded = drive.DriveLink(self.folder)
        self.assertEqual(reloaded.email, "pat@gmail.com")
        self.assertTrue((self.folder / "drive.bin").exists())
        self.assertNotIn(b"pat@gmail.com", (self.folder / "drive.bin").read_bytes()) if sys.platform.startswith("win") else None

    def test_a_connection_without_the_drive_permission_is_refused(self):
        with self.assertRaises(cloud.CloudError) as caught:
            drive.GoogleSignIn.link_from({"scope": "openid email", "refresh_token": "r", "id_token": "x.e30.y"})
        self.assertEqual(caught.exception.code, "drive_scope")
        claims = "eyJzdWIiOiIxMjMiLCJlbWFpbCI6InBhdEBnbWFpbC5jb20ifQ"  # {"sub":"123","email":"pat@gmail.com"}
        link = drive.GoogleSignIn.link_from({"scope": f"openid {drive.DRIVE_SCOPE}", "refresh_token": "r", "id_token": f"x.{claims}.y", "expires_in": 3599})
        self.assertEqual((link["user_id"], link["email"]), ("123", "pat@gmail.com"))

    def test_browser_sign_in_exchanges_the_code_with_pkce(self):
        seen = {}

        def browser(address):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(address).query)
            seen.update(query)
            self.assertEqual(query["code_challenge_method"], ["S256"])
            self.assertIn(drive.DRIVE_SCOPE, query["scope"][0].split())
            redirect = query["redirect_uri"][0]
            import threading
            from urllib.request import ProxyHandler, build_opener

            direct = build_opener(ProxyHandler({}))
            threading.Thread(target=lambda: direct.open(f"{redirect}/?state={query['state'][0]}&code=the-code").read(), daemon=True).start()
            return True

        claims = "eyJzdWIiOiIxMjMiLCJlbWFpbCI6InBhdEBnbWFpbC5jb20ifQ"

        def token_endpoint(request, timeout=None):
            form = urllib.parse.parse_qs(request.data.decode())
            self.assertEqual(form["code"], ["the-code"])
            self.assertTrue(form["code_verifier"][0])
            return io.BytesIO(json.dumps({"access_token": "a", "refresh_token": "r", "expires_in": 3600, "scope": f"openid email {drive.DRIVE_SCOPE}", "id_token": f"x.{claims}.y"}).encode())

        link = drive.GoogleSignIn("client", "secret", opener=token_endpoint, open_page=browser, timeout=10)()
        self.assertEqual(link["email"], "pat@gmail.com")
        self.assertEqual(seen["client_id"], ["client"])


if __name__ == "__main__":
    unittest.main()
