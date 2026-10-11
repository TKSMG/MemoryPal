"""Accounts and two-device sync, against an in-memory Supabase."""

import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("MEMORYPAL_DATA_DIR", tempfile.mkdtemp(prefix="memorypal-tests-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dataclasses import asdict  # noqa: E402

from fake_supabase import FakeSupabase  # noqa: E402
from memorypal import cloud, sync  # noqa: E402
from memorypal.core import today_iso  # noqa: E402
from memorypal.models import Card, sample_cards  # noqa: E402
from memorypal.store import default_payload  # noqa: E402

EMAIL, PASSWORD = "pat@example.com", "correct horse battery"


def new_payload(*cards):
    payload = default_payload()
    payload["cards"] = [asdict(card) for card in (cards or sample_cards())]
    return payload


class Device:
    """One installed copy of MemoryPal: its own data, sync state and sign-in."""

    def __init__(self, server, payload=None):
        self.folder = Path(tempfile.mkdtemp(prefix="memorypal-device-"))
        self.client = cloud.CloudClient("https://example.supabase.co", server.key, opener=server.open)
        self.state = cloud.SyncState(self.folder)
        self.payload = payload or new_payload()
        self.session = None

    def sign_in(self):
        self.session = self.client.sign_in(EMAIL, PASSWORD)

    def sync(self):
        def write(payload):
            self.payload = payload

        return cloud.sync_profile(self.client, self.session, self.state, lambda: copy.deepcopy(self.payload), write)

    def card(self, card_id):
        return next((card for card in self.payload["cards"] if card["id"] == card_id), None)

    def review(self, card_id, **fields):
        self.card(card_id).update(fields)
        day = today_iso()
        self.payload["activity"][day] = self.payload["activity"].get(day, 0) + 1
        self.payload["practiced"] += 1


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.server = FakeSupabase()
        self.client = cloud.CloudClient("https://example.supabase.co", self.server.key, opener=self.server.open)

    def test_sign_up_needs_the_emailed_code_then_signs_in(self):
        self.assertIsNone(self.client.sign_up(EMAIL, PASSWORD))
        with self.assertRaises(cloud.CloudError) as caught:
            self.client.sign_in(EMAIL, PASSWORD)
        self.assertIn("6-digit code", caught.exception.message)
        with self.assertRaises(cloud.CloudError):
            self.client.verify_code(EMAIL, "000000")
        session = self.client.verify_code(EMAIL, "123 456")
        self.assertEqual(session.email, EMAIL)
        self.assertTrue(self.client.sign_in(EMAIL, PASSWORD).access_token)

    def test_friendly_messages(self):
        self.client.sign_up(EMAIL, PASSWORD)
        self.client.verify_code(EMAIL, "123456")
        with self.assertRaises(cloud.CloudError) as caught:
            self.client.sign_in(EMAIL, "wrong password")
        self.assertIn("don't match", caught.exception.message)
        with self.assertRaises(cloud.CloudError) as caught:
            self.client.sign_up(EMAIL, PASSWORD)
        self.assertIn("Sign in instead", caught.exception.message)
        with self.assertRaises(cloud.CloudError) as caught:
            self.client.sign_up("new@example.com", "short")
        self.assertIn("at least 10", caught.exception.message)

    def test_password_reset_by_code(self):
        self.client.sign_up(EMAIL, PASSWORD)
        self.client.verify_code(EMAIL, "123456")
        self.client.request_password_reset(EMAIL)
        session = self.client.verify_code(EMAIL, "654321", kind="recovery")
        self.client.set_password(session, "a brand new password")
        self.assertTrue(self.client.sign_in(EMAIL, "a brand new password").access_token)

    def test_refresh_and_offline(self):
        self.client.sign_up(EMAIL, PASSWORD)
        session = self.client.verify_code(EMAIL, "123456")
        renewed = self.client.refresh(session.refresh_token)
        self.assertNotEqual(renewed.access_token, session.access_token)
        self.server.offline = True
        with self.assertRaises(cloud.CloudError) as caught:
            self.client.sign_in(EMAIL, PASSWORD)
        self.assertEqual(caught.exception.code, "offline")

    def test_not_configured(self):
        with self.assertRaises(cloud.CloudError) as caught:
            cloud.CloudClient("", "").sign_in(EMAIL, PASSWORD)
        self.assertEqual(caught.exception.code, "not_configured")

    def test_delete_account_removes_cloud_data(self):
        self.client.sign_up(EMAIL, PASSWORD)
        session = self.client.verify_code(EMAIL, "123456")
        self.client.push(session, {"card:x": {"id": "x"}})
        self.client.delete_account(session)
        self.assertEqual(self.server.rows, {})
        with self.assertRaises(cloud.CloudError):
            self.client.sign_in(EMAIL, PASSWORD)

    def test_sign_in_is_remembered_encrypted_and_never_the_password(self):
        self.client.sign_up(EMAIL, PASSWORD)
        session = self.client.verify_code(EMAIL, "123456")
        store = cloud.TokenStore(tempfile.mkdtemp())
        store.save(session)
        raw = store.path.read_bytes()
        self.assertNotIn(session.refresh_token.encode(), raw)
        self.assertNotIn(PASSWORD.encode(), raw)
        self.assertEqual(store.load()["refresh_token"], session.refresh_token)
        store.clear()
        self.assertIsNone(store.load())


class TwoStepSignInTests(unittest.TestCase):
    def setUp(self):
        self.server = FakeSupabase(confirm_email=False)
        self.client = cloud.CloudClient("https://example.supabase.co", self.server.key, opener=self.server.open)
        self.client.sign_up(EMAIL, PASSWORD)
        self.session = self.client.sign_in(EMAIL, PASSWORD)

    def turn_on(self):
        setup = self.client.enroll_authenticator(self.session)
        self.assertTrue(setup["secret"] and setup["uri"].startswith("otpauth://"))
        with self.assertRaises(cloud.CloudError) as caught:
            self.client.verify_authenticator(self.session, setup["factor_id"], "000000")
        self.assertIn("authenticator code", caught.exception.message)
        return setup, self.client.verify_authenticator(self.session, setup["factor_id"], FakeSupabase.TOTP_CODE)

    def test_setting_up_upgrades_the_session(self):
        _setup, upgraded = self.turn_on()
        self.assertEqual(upgraded.level, "aal2")
        self.assertFalse(upgraded.needs_second_step)

    def test_password_alone_is_not_enough_once_turned_on(self):
        setup, _upgraded = self.turn_on()
        pending = self.client.sign_in(EMAIL, PASSWORD)
        self.assertTrue(pending.needs_second_step)
        # The database itself refuses the data without the second step...
        with self.assertRaises(cloud.CloudError):
            self.client.pull(pending)
        # ...and a pending sign-in is never saved on the device.
        account = cloud.Account(tempfile.mkdtemp(), self.client)
        with self.assertRaises(cloud.CloudError):
            account.remember(pending)
        self.assertFalse(account.signed_in)
        full = self.client.verify_authenticator(pending, pending.factors[0]["id"], FakeSupabase.TOTP_CODE)
        self.assertEqual(self.client.pull(full), [])
        account.remember(full)
        # Refreshing keeps the second step.
        self.assertEqual(self.client.refresh(full.refresh_token).level, "aal2")

    def test_turning_off_needs_the_second_step(self):
        setup, upgraded = self.turn_on()
        pending = self.client.sign_in(EMAIL, PASSWORD)
        with self.assertRaises(cloud.CloudError):
            self.client.remove_authenticator(pending, setup["factor_id"])
        self.client.remove_authenticator(upgraded, setup["factor_id"])
        self.assertFalse(self.client.sign_in(EMAIL, PASSWORD).needs_second_step)


class PasswordAndLimitTests(unittest.TestCase):
    def test_weak_passwords_are_explained(self):
        from memorypal import security

        self.assertTrue(security.password_problems("short"))
        self.assertTrue(any("most common" in p for p in security.password_problems("password123")))
        self.assertTrue(any("email name" in p for p in security.password_problems("patricia-garden-77", "patricia@example.com")))
        self.assertTrue(any("1234" in p for p in security.password_problems("abcdefghijkl")))
        self.assertEqual(security.password_problems("correct horse battery"), [])
        self.assertEqual(security.password_strength("correct horse battery staple"), 4)
        self.assertLessEqual(security.password_strength("qwertyuiop"), 1)

    def test_leaked_password_check_sends_only_a_hash_prefix(self):
        import hashlib
        import io

        from memorypal import security

        digest = hashlib.sha1(b"hunter2hunter2").hexdigest().upper()
        seen = {}

        def opener(request, timeout=None):
            seen["url"] = request.full_url
            return io.BytesIO(f"{digest[5:]}:4321\r\n0000000000000000000000000000000000A:1".encode())

        self.assertEqual(security.pwned_count("hunter2hunter2", opener=opener), 4321)
        self.assertTrue(seen["url"].endswith("/range/" + digest[:5]))
        self.assertNotIn("hunter2", seen["url"])

    def test_attempt_limiter_backs_off_then_forgives(self):
        from memorypal import security

        now = [1000.0]
        limiter = security.AttemptLimiter(clock=lambda: now[0])
        for _ in range(5):
            self.assertEqual(limiter.wait_seconds("Pat@Example.com"), 0)
            limiter.failed("pat@example.com")
        self.assertEqual(limiter.wait_seconds("pat@example.com"), 30)
        now[0] += 31
        limiter.failed("pat@example.com")
        self.assertEqual(limiter.wait_seconds("pat@example.com"), 60)
        limiter.succeeded("pat@example.com")
        self.assertEqual(limiter.wait_seconds("pat@example.com"), 0)


class TwoDeviceSyncTests(unittest.TestCase):
    def setUp(self):
        self.server = FakeSupabase(confirm_email=False)
        cloud.CloudClient("https://example.supabase.co", self.server.key, opener=self.server.open).sign_up(EMAIL, PASSWORD)
        self.laptop = Device(self.server)
        self.phone = Device(self.server)
        self.laptop.sign_in()
        self.phone.sign_in()

    def both_sync(self):
        self.laptop.sync()
        self.phone.sync()
        self.laptop.sync()

    def test_a_new_card_reaches_the_other_device(self):
        self.laptop.payload["cards"].insert(0, asdict(Card(id="c1", front="Capital of France?", back="Paris")))
        self.both_sync()
        self.assertEqual(self.phone.card("c1")["back"], "Paris")

    def test_starter_cards_are_not_duplicated(self):
        self.both_sync()
        self.assertEqual(len(self.phone.payload["cards"]), 4)
        self.assertEqual(len(self.laptop.payload["cards"]), 4)

    def test_edit_here_and_review_there_both_survive(self):
        self.laptop.payload["cards"].insert(0, asdict(Card(id="c1", front="Q", back="A")))
        self.both_sync()
        self.laptop.card("c1")["back"] = "A, but clearer"
        self.phone.review("c1", repetitions=1, interval=3, next_review="2030-01-01", last_result="Good")
        self.both_sync()
        for device in (self.laptop, self.phone):
            card = device.card("c1")
            self.assertEqual((card["back"], card["repetitions"], card["interval"]), ("A, but clearer", 1, 3))

    def test_reviews_on_both_devices_add_up(self):
        self.laptop.review("sample-chunking", repetitions=1)
        self.laptop.review("sample-chunking", repetitions=2)
        self.laptop.review("sample-chunking", repetitions=3)
        self.phone.review("sample-media-cues", repetitions=1)
        self.phone.review("sample-media-cues", repetitions=2)
        self.both_sync()
        self.phone.sync()
        for device in (self.laptop, self.phone):
            self.assertEqual(device.payload["activity"][today_iso()], 5)
            self.assertEqual(device.payload["practiced"], 5)
        # Syncing again doesn't count anything twice.
        self.both_sync()
        self.assertEqual(self.phone.payload["activity"][today_iso()], 5)

    def test_more_reviews_win_a_schedule_conflict(self):
        self.both_sync()
        self.laptop.review("sample-chunking", repetitions=1, interval=1, next_review="2026-10-11")
        self.phone.review("sample-chunking", repetitions=1, interval=1, next_review="2026-10-11")
        self.phone.review("sample-chunking", repetitions=2, interval=3, next_review="2026-10-14")
        self.both_sync()
        self.assertEqual(self.laptop.card("sample-chunking")["repetitions"], 2)
        self.assertEqual(self.phone.card("sample-chunking")["interval"], 3)

    def test_deleting_reaches_the_other_device_but_an_edit_beats_a_delete(self):
        self.both_sync()
        self.laptop.payload["cards"] = [c for c in self.laptop.payload["cards"] if c["id"] != "sample-chunking"]
        self.both_sync()
        self.assertIsNone(self.phone.card("sample-chunking"))
        self.laptop.payload["cards"] = [c for c in self.laptop.payload["cards"] if c["id"] != "sample-media-cues"]
        self.phone.card("sample-media-cues")["front"] = "Edited on the phone"
        self.both_sync()
        self.assertEqual(self.laptop.card("sample-media-cues")["front"], "Edited on the phone")

    def test_settings_sync(self):
        self.laptop.payload["daily_goal"] = 30
        self.both_sync()
        self.assertEqual(self.phone.payload["daily_goal"], 30)

    def test_a_dropped_upload_is_retried_next_time(self):
        self.laptop.payload["cards"].insert(0, asdict(Card(id="c2", front="Q2", back="A2")))
        self.server.fail_next_push = True
        with self.assertRaises(cloud.CloudError):
            self.laptop.sync()
        self.laptop.sync()
        self.phone.sync()
        self.assertIsNotNone(self.phone.card("c2"))

    def test_another_account_cannot_see_the_data(self):
        self.laptop.payload["cards"].insert(0, asdict(Card(id="secret", front="Private", back="Mine")))
        self.laptop.sync()
        client = cloud.CloudClient("https://example.supabase.co", self.server.key, opener=self.server.open)
        client.sign_up("other@example.com", PASSWORD)
        stranger = client.sign_in("other@example.com", PASSWORD)
        self.assertEqual(client.pull(stranger), [])

    def test_feedback_notes_stay_on_the_device(self):
        self.laptop.payload["feedback"] = [{"id": "f1", "note": "local only"}]
        self.both_sync()
        self.assertEqual(self.phone.payload["feedback"], [])
        self.assertFalse(any(key.startswith("feedback") for key in self.server.rows_for(EMAIL)))


class PlanTests(unittest.TestCase):
    def test_untouched_records_need_nothing(self):
        record = {"card:a": {"id": "a", "front": "Q"}}
        plan = sync.plan_sync(record, record, {})
        self.assertEqual((plan.push, plan.apply), ({}, {}))

    def test_own_echo_from_the_cloud_changes_nothing(self):
        record = {"card:a": {"id": "a", "front": "Q"}}
        plan = sync.plan_sync(record, record, dict(record))
        self.assertEqual((plan.push, plan.apply), ({}, {}))

    def test_same_field_changed_on_both_sides_takes_the_cloud_copy(self):
        base = {"card:a": {"id": "a", "front": "Q", "back": "old"}}
        local = {"card:a": {"id": "a", "front": "Q", "back": "mine"}}
        remote = {"card:a": {"id": "a", "front": "Q", "back": "theirs"}}
        plan = sync.plan_sync(local, base, remote)
        self.assertEqual(plan.final["card:a"]["back"], "theirs")
        self.assertNotIn("card:a", plan.push)


if __name__ == "__main__":
    unittest.main()
