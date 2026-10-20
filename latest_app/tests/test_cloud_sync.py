"""Accounts and two-device sync, against an in-memory Supabase."""

import base64
import copy
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

os.environ.setdefault("MEMORYPAL_DATA_DIR", tempfile.mkdtemp(prefix="memorypal-tests-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dataclasses import asdict  # noqa: E402

from fake_supabase import FakeSupabase  # noqa: E402
from memorypal import cloud, sync  # noqa: E402
from memorypal.core import today_iso  # noqa: E402
from memorypal.models import Card, sample_cards  # noqa: E402
from memorypal.store import default_payload  # noqa: E402

EMAIL, PASSWORD = "pat@example.com", "correct horse battery 7"


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

    def sync(self, mode=None):
        def write(payload):
            self.payload = payload

        return cloud.sync_profile(self.client, self.session, self.state, lambda: copy.deepcopy(self.payload), write, mode=mode)

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
        self.assertIn("code we emailed", caught.exception.message)
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

    def test_rate_limits_are_explained(self):
        def error(status, body):
            return cloud.CloudClient.error_from(urllib.error.HTTPError("u", status, "x", {}, io.BytesIO(json.dumps(body).encode())))

        too_soon = error(429, {"error_code": "over_email_send_rate_limit", "msg": "For security purposes, you can only request this after 42 seconds."})
        self.assertEqual(too_soon.code, "email_too_soon")
        self.assertIn("Wait 42 seconds", too_soon.message)
        self.assertEqual(error(429, {"error_code": "over_email_send_rate_limit", "msg": "Email rate limit exceeded"}).code, "over_email_send_rate_limit")
        self.assertEqual(error(429, {"error_code": "over_request_rate_limit"}).code, "over_request_rate_limit")
        self.assertEqual(error(429, {}).code, "rate_limited")

    def test_password_reset_by_code(self):
        self.client.sign_up(EMAIL, PASSWORD)
        self.client.verify_code(EMAIL, "123456")
        self.client.request_password_reset(EMAIL)
        session = self.client.verify_code(EMAIL, "654321", kind="recovery")
        self.client.set_password(session, "a brand new password 9")
        self.assertTrue(self.client.sign_in(EMAIL, "a brand new password 9").access_token)

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
        # A build without a project: cloud_config.py ships the real one now.
        with mock.patch.object(cloud, "config", return_value=("", "")), self.assertRaises(cloud.CloudError) as caught:
            cloud.CloudClient().sign_in(EMAIL, PASSWORD)
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


class SessionRefreshTests(unittest.TestCase):
    """How the remembered sign-in reacts to what a refresh brings back."""

    def account(self, refresh):
        client = mock.Mock()
        client.refresh.side_effect = refresh
        account = cloud.Account(tempfile.mkdtemp(), client=client)
        account.remember(cloud.Session("old-access", "old-refresh", 0, "u1", EMAIL))
        return account

    def test_reused_refresh_token_signs_out(self):
        account = self.account(cloud.CloudError("Invalid Refresh Token: Already Used", "refresh_token_already_used"))
        with self.assertRaises(cloud.CloudError):
            account.active_session()
        self.assertFalse(account.signed_in)

    def test_two_step_turned_on_elsewhere_signs_out_with_a_reason(self):
        account = self.account(lambda _token: cloud.Session("new-access", "new-refresh", 0, "u1", EMAIL, [{"id": "f1"}]))
        with self.assertRaises(cloud.CloudError) as caught:
            account.active_session()
        self.assertEqual(caught.exception.code, "two_step_now_on")
        self.assertFalse(account.signed_in)

    def test_sign_out_during_a_refresh_stays_signed_out(self):
        def refresh(_token):
            account.forget()  # Sign out pressed while the refresh was on its way
            return cloud.Session("new-access", "new-refresh", 9e12, "u1", EMAIL)

        account = self.account(refresh)
        with self.assertRaises(cloud.CloudError):
            account.active_session()
        self.assertFalse(account.signed_in)
        self.assertIsNone(account.tokens.load())


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
        self.assertEqual(security.password_problems("correct horse battery 7"), [])
        self.assertEqual(security.password_strength("correct horse battery 7 staple"), 4)
        self.assertTrue(any("one number" in p for p in security.password_problems("correct horse battery staple")))
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


class AgeAndConsentTests(unittest.TestCase):
    """Accounts are 13+; the check keeps no birth date; consent is recorded with the account."""

    def test_age_check_is_conservative_around_the_birthday(self):
        from memorypal import security

        check = lambda month, year: security.account_age_check(month, year, 2026, 10)  # noqa: E731
        self.assertEqual(check(9, 2013), ("", False))   # turned 13 last month
        self.assertTrue(check(10, 2013)[1])               # birthday month: treated as not yet 13
        self.assertTrue(check(11, 2013)[1])               # turns 13 next month
        self.assertTrue(check(1, 2020)[1])
        self.assertEqual(check(6, 1950), ("", False))
        for month, year in ((13, 2000), (0, 2000), ("", "2000"), ("x", "2000"), (5, 2027), (5, 1890), ("1_0", "2000")):
            message, under = check(month, year)
            self.assertEqual((message, under), (security.AGE_FORMAT_MESSAGE, False), (month, year))

    def test_a_refusal_holds_on_this_device_for_a_day(self):
        now = [5000.0]
        folder = tempfile.mkdtemp(prefix="memorypal-age-")
        gate = cloud.AgeGate(folder, clock=lambda: now[0])
        self.assertFalse(gate.blocked())
        gate.refuse()
        self.assertTrue(cloud.AgeGate(folder, clock=lambda: now[0]).blocked())
        now[0] += 24 * 60 * 60 + 1
        self.assertFalse(gate.blocked())
        Path(folder, "age-check.json").write_text("not json")
        self.assertFalse(gate.blocked())

    def test_consent_is_kept_with_the_account_without_a_birth_date(self):
        from memorypal import security

        server = FakeSupabase()
        client = cloud.CloudClient("https://example.supabase.co", server.key, opener=server.open)
        client.sign_up(EMAIL, PASSWORD, cloud.consent_record(now=0))
        metadata = server.users[EMAIL]["metadata"]
        self.assertEqual(metadata, {"age_confirmed": "13+", "terms_version": security.TERMS_VERSION, "terms_accepted_at": "1970-01-01T00:00:00Z"})
        self.assertFalse(any("birth" in key for key in metadata))

    @unittest.skipUnless(sys.platform == "darwin", "Mac Keychain")
    def test_mac_keeps_the_sign_in_in_the_keychain(self):
        folder = tempfile.mkdtemp(prefix="memorypal-token-")
        store = cloud.TokenStore(folder)
        store.save(cloud.Session("a", "refresh-secret", 0, "u", EMAIL))
        blob = Path(folder, "account.bin").read_bytes()
        self.assertTrue(blob.startswith(b"KEYCH1"), blob[:6])
        self.assertNotIn(b"refresh-secret", blob)
        self.assertNotIn(base64.b64encode(b"refresh-secret")[:8], blob)
        self.assertEqual(cloud.TokenStore(folder).load()["refresh_token"], "refresh-secret")
        store.clear()
        self.assertIsNone(cloud.TokenStore(folder).load())

    @unittest.skipUnless(sys.platform.startswith("win"), "Windows only")
    def test_windows_ignores_a_planted_plain_sign_in(self):
        folder = tempfile.mkdtemp(prefix="memorypal-token-")
        Path(folder, "account.bin").write_bytes(b"PLAIN1" + base64.b64encode(json.dumps({"refresh_token": "planted"}).encode()))
        self.assertIsNone(cloud.TokenStore(folder).load())

    @unittest.skipIf(sys.platform.startswith("win"), "Windows uses DPAPI instead of file permissions")
    def test_saved_sign_in_is_owner_only_off_windows(self):
        folder = tempfile.mkdtemp(prefix="memorypal-token-")
        cloud.TokenStore(folder).save(cloud.Session("a", "r", 0, "u", EMAIL))
        self.assertEqual(os.stat(Path(folder, "account.bin")).st_mode & 0o777, 0o600)


class DeviceSyncOptionTests(unittest.TestCase):
    def test_auto_sync_is_on_and_sign_in_prompt_unanswered_by_default(self):
        state = cloud.SyncState(tempfile.mkdtemp(prefix="memorypal-options-"))
        self.assertTrue(state.auto_sync)
        self.assertFalse(state.account_prompted)

    def test_options_survive_a_restart_and_a_start_over(self):
        folder = tempfile.mkdtemp(prefix="memorypal-options-")
        state = cloud.SyncState(folder)
        state.auto_sync = False
        state.account_prompted = True
        state.save()
        state.start_over()
        again = cloud.SyncState(folder)
        self.assertFalse(again.auto_sync)
        self.assertTrue(again.account_prompted)


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

    def test_switching_accounts_asks_before_sending_anything(self):
        self.laptop.payload["cards"].insert(0, asdict(Card(id="mine", front="Private", back="Mine")))
        self.laptop.sync()
        client = self.laptop.client
        client.sign_up("other@example.com", PASSWORD)
        self.laptop.session = client.sign_in("other@example.com", PASSWORD)
        with self.assertRaises(cloud.CloudError) as caught:
            self.laptop.sync()
        self.assertEqual(caught.exception.code, "other_account")
        self.assertEqual(client.pull(self.laptop.session), [])  # nothing leaked into the new account

    def test_replace_swaps_in_the_other_accounts_cards(self):
        self.phone.payload["cards"].insert(0, asdict(Card(id="theirs", front="Other account", back="Card")))
        self.phone.sync()
        other = Device(self.server)
        other.client.sign_up("other@example.com", PASSWORD)
        other.session = other.client.sign_in("other@example.com", PASSWORD)
        other.payload["cards"].insert(0, asdict(Card(id="mine", front="Only in B", back="Card")))
        other.review("mine")
        other.sync()
        other.session = self.phone.session  # this profile now signs in to the first account
        with self.assertRaises(cloud.CloudError):
            other.sync()
        other.sync(mode="replace")
        self.assertIsNotNone(other.card("theirs"))
        self.assertIsNone(other.card("mine"))
        self.assertEqual(other.payload["practiced"], self.phone.payload["practiced"])
        keys = [key for key, _data, _at in self.phone.client.pull(self.phone.session)]
        self.assertNotIn("card:mine", keys)
        other.sync()  # and from then on it syncs normally
        self.assertIsNone(other.card("mine"))

    def test_merge_adds_this_profiles_cards_to_the_new_account(self):
        self.laptop.payload["cards"].insert(0, asdict(Card(id="mine", front="Private", back="Mine")))
        self.laptop.sync()
        self.laptop.client.sign_up("other@example.com", PASSWORD)
        self.laptop.session = self.laptop.client.sign_in("other@example.com", PASSWORD)
        self.laptop.sync(mode="merge")
        keys = [key for key, _data, _at in self.laptop.client.pull(self.laptop.session)]
        self.assertIn("card:mine", keys)

    def test_signing_out_ends_the_session_on_the_server_even_before_a_sync(self):
        account = cloud.Account(self.laptop.folder, client=self.laptop.client)
        account.remember(self.laptop.session)
        later = cloud.Account(self.laptop.folder, client=self.laptop.client)  # a fresh launch: no session in memory
        with mock.patch.object(later.client, "sign_out", wraps=later.client.sign_out) as sign_out:
            later.sign_out()
        sign_out.assert_called_once()
        self.assertFalse(later.signed_in)

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

    def test_unknown_kinds_from_the_cloud_are_ignored(self):
        record = {"card:a": {"id": "a", "front": "Q"}}
        remote = {"evil:x": {"a": 1}, "__proto__": {"card:a": None}, "settings": {"daily_goal": 1}, 7: {"x": 1}, "card:b": {"id": "b"}}
        plan = sync.plan_sync(record, record, remote)
        self.assertEqual(sorted(plan.final), ["card:a", "card:b"])
        self.assertEqual((plan.push, sorted(plan.apply)), ({}, ["card:b"]))

    def test_an_unknown_key_already_in_the_base_is_never_pushed(self):
        # Older versions kept such keys, then pushed a delete for them on
        # every sync, which the database refuses: sync stopped for good.
        record = {"card:a": {"id": "a", "front": "Q"}}
        plan = sync.plan_sync(record, {**record, "evil:x": {"a": 1}}, {})
        self.assertEqual((plan.push, plan.apply, sorted(plan.final)), ({}, {}, ["card:a"]))


class CaptchaTests(unittest.TestCase):
    def setUp(self):
        self.server = FakeSupabase()
        self.server.captcha = True
        self.issued = []

        def check():
            token = f"turnstile-{len(self.issued)}"
            self.issued.append(token)
            self.server.captcha_tokens.add(token)
            return token

        self.client = cloud.CloudClient("https://example.supabase.co", self.server.key, opener=self.server.open, captcha=check)

    def test_without_a_check_the_server_refuses(self):
        self.client.captcha = None
        with self.assertRaises(cloud.CloudError) as caught:
            self.client.sign_up(EMAIL, PASSWORD)
        self.assertEqual(caught.exception.code, "captcha_failed")
        self.assertEqual(caught.exception.message, cloud.FRIENDLY["captcha_failed"])

    def test_every_protected_request_gets_its_own_token(self):
        self.assertIsNone(self.client.sign_up(EMAIL, PASSWORD))
        self.client.resend_confirmation(EMAIL)
        session = self.client.verify_code(EMAIL, "123456")
        self.client.sign_in(EMAIL, PASSWORD)
        self.client.request_password_reset(EMAIL)
        self.client.refresh(session.refresh_token)  # no check for a refresh
        self.assertEqual(len(self.issued), 4)

    def test_the_browser_check_hands_back_the_token(self):
        import threading
        import urllib.request

        def browser(address):
            port, state = (part.split("=", 1)[1] for part in address.split("#", 1)[1].split("&"))
            base = f"http://127.0.0.1:{port}/done"

            def visit():
                with self.assertRaises(urllib.error.HTTPError):
                    urllib.request.urlopen(f"{base}?state=wrong&token=planted", timeout=5)
                with urllib.request.urlopen(f"{base}?state={state}&token=tok-123", timeout=5) as reply:
                    self.page = reply.read().decode()
            self.visit = threading.Thread(target=visit, daemon=True)
            self.visit.start()
            return True

        check = cloud.BrowserCheck("https://tksmg.github.io/MemoryPal/verify/", open_page=browser, timeout=10)
        self.assertEqual(check(), "tok-123")
        self.visit.join(5)  # the browser finishes reading the "All set" page
        self.assertIn("All set", self.page)

    def test_the_browser_check_reports_a_failed_or_unfinished_check(self):
        import threading
        import urllib.request

        def failing(address):
            port, state = (part.split("=", 1)[1] for part in address.split("#", 1)[1].split("&"))
            threading.Thread(target=lambda: urllib.request.urlopen(f"http://127.0.0.1:{port}/done?state={state}&error=110200", timeout=5).read(), daemon=True).start()
            return True

        with self.assertRaises(cloud.CloudError) as caught:
            cloud.BrowserCheck("https://example.test/verify/", open_page=failing, timeout=10)()
        self.assertEqual(caught.exception.code, "captcha_failed")
        with self.assertRaises(cloud.CloudError) as caught:
            cloud.BrowserCheck("https://example.test/verify/", open_page=lambda _address: True, timeout=0.6)()
        self.assertEqual(caught.exception.code, "captcha_timeout")
        with self.assertRaises(cloud.CloudError) as caught:
            cloud.BrowserCheck("https://example.test/verify/", open_page=lambda _address: False)()
        self.assertEqual(caught.exception.code, "captcha_failed")

    def test_the_check_page_setting(self):
        with mock.patch.dict(os.environ, {"MEMORYPAL_CAPTCHA_URL": ""}):
            self.assertIsNone(cloud.browser_check())
        with mock.patch.dict(os.environ, {"MEMORYPAL_CAPTCHA_URL": "https://example.test/verify/"}):
            self.assertEqual(cloud.browser_check().page_url, "https://example.test/verify/")


if __name__ == "__main__":
    unittest.main()
