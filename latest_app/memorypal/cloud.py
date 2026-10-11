"""Accounts and sync with the MemoryPal cloud (Supabase), using only the standard library.

- CloudClient talks to Supabase Auth (email + password, 6-digit email codes
  for confirming an account and resetting a password, so no web page or
  domain is needed) and to the sync_records table (supabase/schema.sql).
- TokenStore keeps the sign-in (never the password) in the profile folder,
  encrypted with Windows DPAPI so only this Windows user can read it.
- SyncState remembers, per profile and account, the device id, the last
  pull position, and the records as of the last sync (see sync.py).

Network calls block; the desktop runs them on a worker thread.
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from . import cloud_config, security, sync

TIMEOUT = 20
PAGE_SIZE = 1000
PUSH_BATCH = 400
MIN_PASSWORD = security.MIN_PASSWORD


def config():
    """(url, publishable key); empty strings when the cloud isn't set up in this build."""
    url = os.environ.get("MEMORYPAL_SUPABASE_URL") or cloud_config.SUPABASE_URL
    key = os.environ.get("MEMORYPAL_SUPABASE_KEY") or cloud_config.SUPABASE_PUBLISHABLE_KEY
    return url.rstrip("/"), key


def configured():
    url, key = config()
    return bool(url and key)


class CloudError(Exception):
    """A failure with a message that can be shown to people as it is."""

    def __init__(self, message, code=""):
        super().__init__(message)
        self.message = message
        self.code = code


FRIENDLY = {
    "invalid_credentials": "That email and password don't match. Check them, or reset your password.",
    "invalid_grant": "That email and password don't match. Check them, or reset your password.",
    "email_not_confirmed": "Confirm your email first: enter the 6-digit code we sent you.",
    "user_already_exists": "There's already an account with this email. Sign in instead.",
    "email_exists": "There's already an account with this email. Sign in instead.",
    "weak_password": f"Choose a longer password: at least {MIN_PASSWORD} characters, ideally a few words.",
    "over_email_send_rate_limit": "Too many emails were sent just now. Wait a few minutes and try again.",
    "over_request_rate_limit": "Too many tries in a short time. Wait a minute and try again.",
    "otp_expired": "That code is wrong or has expired. Ask for a new one.",
    "validation_failed": "Check the email address and try again.",
    "email_address_invalid": "That doesn't look like an email address.",
    "signup_disabled": "New accounts can't be made right now.",
    "refresh_token_not_found": "You've been signed out. Please sign in again.",
    "session_not_found": "You've been signed out. Please sign in again.",
    "mfa_verification_failed": "That authenticator code isn't right. Check the time on this device and try the newest code.",
    "mfa_challenge_expired": "That took too long. Try again with a fresh code.",
    "insufficient_aal": "Finish two-step sign-in first: enter the code from your authenticator app.",
    "mfa_factor_not_found": "Two-step sign-in isn't set up for this account any more.",
    "too_many_enrolled_mfa_factors": "Two-step sign-in is already set up. Turn it off first to set it up again.",
    # Row Level Security refused the request (for two-step accounts: no second step yet).
    "42501": "MemoryPal couldn't reach your cloud data. Sign out and sign in again (with your authenticator code if you use one).",
}


def jwt_claims(token):
    """The (unverified) claims inside an access token, to read its assurance level."""
    try:
        part = token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)).decode("utf-8"))
    except (IndexError, ValueError, UnicodeDecodeError):
        return {}


class Session:
    def __init__(self, access_token, refresh_token, expires_at, user_id, email, factors=()):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = float(expires_at or 0)
        self.user_id = user_id
        self.email = email
        # Verified authenticator-app factors on the account: [{id, friendly_name}]
        self.factors = list(factors)

    @classmethod
    def from_auth(cls, data):
        user = data.get("user") or {}
        expires_at = data.get("expires_at") or (time.time() + float(data.get("expires_in") or 3600))
        factors = [
            {"id": factor.get("id", ""), "friendly_name": factor.get("friendly_name", "")}
            for factor in user.get("factors") or []
            if factor.get("status") == "verified" and factor.get("factor_type") == "totp"
        ]
        return cls(data.get("access_token", ""), data.get("refresh_token", ""), expires_at, user.get("id", ""), user.get("email", ""), factors)

    @property
    def level(self):
        """'aal1' after a password, 'aal2' after the second step too."""
        return jwt_claims(self.access_token).get("aal", "aal1")

    @property
    def needs_second_step(self):
        return bool(self.factors) and self.level != "aal2"

    def expiring(self, margin=60):
        return time.time() > self.expires_at - margin

    def to_dict(self):
        return {"refresh_token": self.refresh_token, "user_id": self.user_id, "email": self.email}


class CloudClient:
    def __init__(self, url=None, key=None, opener=None, timeout=TIMEOUT):
        default_url, default_key = config()
        self.url = (url or default_url).rstrip("/")
        self.key = key or default_key
        self.opener = opener or urllib.request.urlopen
        self.timeout = timeout

    # ------------------------------------------------------------ transport
    def request(self, method, path, body=None, token=None, query=None, prefer=None):
        if not self.url or not self.key:
            raise CloudError("Sync isn't set up in this copy of MemoryPal yet.", "not_configured")
        url = f"{self.url}{path}"
        if query:
            url += "?" + urllib.parse.urlencode(query, safe=",.:()")
        headers = {"apikey": self.key, "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if prefer:
            headers["Prefer"] = prefer
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise self.error_from(exc) from None
        except (urllib.error.URLError, OSError, TimeoutError):
            raise CloudError("Couldn't reach the MemoryPal cloud. Check the internet connection and try again.", "offline") from None
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            return None

    @staticmethod
    def error_from(exc):
        try:
            detail = json.loads(exc.read().decode("utf-8", "replace") or "{}")
        except (ValueError, OSError):
            detail = {}
        code = str(detail.get("error_code") or detail.get("error") or detail.get("code") or "")
        text = str(detail.get("msg") or detail.get("error_description") or detail.get("message") or "")
        if code in FRIENDLY:
            return CloudError(FRIENDLY[code], code)
        if "Invalid login credentials" in text:
            return CloudError(FRIENDLY["invalid_credentials"], "invalid_credentials")
        if exc.code == 401:
            return CloudError(FRIENDLY["session_not_found"], "unauthorized")
        if exc.code == 429:
            return CloudError(FRIENDLY["over_request_rate_limit"], "rate_limited")
        return CloudError(text or f"The MemoryPal cloud answered with an error ({exc.code}).", code or str(exc.code))

    # ----------------------------------------------------------------- auth
    def sign_up(self, email, password):
        """Create an account. Returns a Session, or None when the email must be confirmed first."""
        check_password(password, email)
        data = self.request("POST", "/auth/v1/signup", {"email": email.strip(), "password": password}) or {}
        return Session.from_auth(data) if data.get("access_token") else None

    def verify_code(self, email, code, kind="signup"):
        """Confirm a sign-up ("signup") or a password reset ("recovery") with the emailed code."""
        code = "".join(ch for ch in str(code) if ch.isdigit())
        data = self.request("POST", "/auth/v1/verify", {"type": kind, "email": email.strip(), "token": code}) or {}
        if not data.get("access_token"):
            raise CloudError(FRIENDLY["otp_expired"], "otp_expired")
        return Session.from_auth(data)

    def resend_confirmation(self, email):
        self.request("POST", "/auth/v1/resend", {"type": "signup", "email": email.strip()})

    def sign_in(self, email, password):
        data = self.request("POST", "/auth/v1/token", {"email": email.strip(), "password": password}, query={"grant_type": "password"})
        return Session.from_auth(data or {})

    def refresh(self, refresh_token):
        data = self.request("POST", "/auth/v1/token", {"refresh_token": refresh_token}, query={"grant_type": "refresh_token"})
        return Session.from_auth(data or {})

    def request_password_reset(self, email):
        self.request("POST", "/auth/v1/recover", {"email": email.strip()})

    def set_password(self, session, password):
        check_password(password, session.email)
        self.request("PUT", "/auth/v1/user", {"password": password}, token=session.access_token)

    def sign_out(self, session):
        try:
            self.request("POST", "/auth/v1/logout", {}, token=session.access_token)
        except CloudError:
            pass  # signing out locally still works when offline

    def delete_account(self, session):
        self.request("POST", "/rest/v1/rpc/delete_my_account", {}, token=session.access_token)

    # ------------------------------------------------- two-step sign-in (TOTP)
    def factors(self, session):
        """The account's verified authenticator-app factors (fresh from the server)."""
        user = self.request("GET", "/auth/v1/user", token=session.access_token) or {}
        return Session.from_auth({"access_token": session.access_token, "user": user}).factors

    def enroll_authenticator(self, session):
        """Start adding an authenticator app: {factor_id, secret, uri} to show the person."""
        data = self.request("POST", "/auth/v1/factors", {"factor_type": "totp", "friendly_name": f"Authenticator {time.strftime('%Y-%m-%d %H:%M')}", "issuer": "MemoryPal"}, token=session.access_token) or {}
        totp = data.get("totp") or {}
        return {"factor_id": data.get("id", ""), "secret": totp.get("secret", ""), "uri": totp.get("uri", "")}

    def verify_authenticator(self, session, factor_id, code):
        """Prove a 6-digit authenticator code; returns the upgraded (aal2) Session."""
        code = "".join(ch for ch in str(code) if ch.isdigit())
        challenge = self.request("POST", f"/auth/v1/factors/{factor_id}/challenge", {}, token=session.access_token) or {}
        data = self.request("POST", f"/auth/v1/factors/{factor_id}/verify", {"challenge_id": challenge.get("id", ""), "code": code}, token=session.access_token) or {}
        upgraded = Session.from_auth(data)
        if not upgraded.access_token:
            raise CloudError(FRIENDLY["mfa_verification_failed"], "mfa_verification_failed")
        return upgraded

    def remove_authenticator(self, session, factor_id):
        self.request("DELETE", f"/auth/v1/factors/{factor_id}", token=session.access_token)

    # ----------------------------------------------------------------- data
    def pull(self, session, since=None):
        """Records changed since `since` (inclusive), oldest first: [(key, data|None, updated_at)]."""
        rows, offset = [], 0
        while True:
            query = {"select": "key,kind,data,deleted,updated_at", "order": "updated_at.asc,key.asc", "limit": PAGE_SIZE, "offset": offset}
            if since:
                query["updated_at"] = f"gte.{since}"
            page = self.request("GET", "/rest/v1/sync_records", token=session.access_token, query=query) or []
            for row in page:
                rows.append((row["key"], None if row.get("deleted") else row.get("data"), row.get("updated_at")))
            if len(page) < PAGE_SIZE:
                return rows
            offset += PAGE_SIZE

    def push(self, session, changes):
        """Upload changed records (key -> data, or None to mark deleted)."""
        rows = [{"key": key, "kind": sync.kind_of(key), "data": data, "deleted": data is None} for key, data in sorted(changes.items())]
        for start in range(0, len(rows), PUSH_BATCH):
            self.request(
                "POST", "/rest/v1/sync_records", rows[start:start + PUSH_BATCH], token=session.access_token,
                query={"on_conflict": "user_id,key"}, prefer="resolution=merge-duplicates,return=minimal",
            )


def check_password(password, email=""):
    """Refuse weak passwords before they reach the server (which checks again)."""
    problems = security.password_problems(password, email)
    if problems:
        raise CloudError(problems[0], "weak_password")


def looks_like_email(text):
    text = (text or "").strip()
    name, _at, domain = text.partition("@")
    return bool(name) and "." in domain and " " not in text and not domain.startswith(".") and not domain.endswith(".")


# ---------------------------------------------------------------------------
# Remembering the sign-in
# ---------------------------------------------------------------------------
def _dpapi(data, protect):
    """Encrypt/decrypt bytes for the current Windows user (CryptProtectData)."""
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buffer = ctypes.create_string_buffer(data, len(data))
    source = Blob(len(data), buffer)
    target = Blob()
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(source), None, None, None, None, 0x1, ctypes.byref(target))  # CRYPTPROTECT_UI_FORBIDDEN
    if not ok:
        raise OSError("DPAPI failed")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel32.LocalFree(target.pbData)


class TokenStore:
    """The refresh token for one profile, encrypted at rest on Windows."""

    def __init__(self, folder):
        self.path = Path(folder) / "account.bin"

    def save(self, session):
        raw = json.dumps(session.to_dict()).encode("utf-8")
        if sys.platform.startswith("win"):
            blob = b"DPAPI1" + _dpapi(raw, True)
        else:
            blob = b"PLAIN1" + base64.b64encode(raw)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(self.path.name + ".tmp")
        temp.write_bytes(blob)
        os.replace(temp, self.path)

    def load(self):
        """{refresh_token, user_id, email} or None."""
        try:
            blob = self.path.read_bytes()
            raw = _dpapi(blob[6:], False) if blob.startswith(b"DPAPI1") else base64.b64decode(blob[6:]) if blob.startswith(b"PLAIN1") else b""
            data = json.loads(raw.decode("utf-8")) if raw else None
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) and data.get("refresh_token") else None

    def clear(self):
        try:
            self.path.unlink()
        except OSError:
            pass


class SyncState:
    """Per profile: device id, account it syncs with, pull position, and the last synced records."""

    def __init__(self, folder):
        self.path = Path(folder) / "sync-state.json"
        self.device_id = ""
        self.user_id = ""
        self.cursor = None
        self.base = {}
        self.last_synced = ""
        self.load()

    def load(self):
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        self.device_id = str(raw.get("device_id") or uuid.uuid4())
        self.user_id = str(raw.get("user_id") or "")
        self.cursor = raw.get("cursor") or None
        self.base = raw.get("base") if isinstance(raw.get("base"), dict) else {}
        self.last_synced = str(raw.get("last_synced") or "")

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(self.path.name + ".tmp")
        temp.write_text(json.dumps({"device_id": self.device_id, "user_id": self.user_id, "cursor": self.cursor, "base": self.base, "last_synced": self.last_synced}), encoding="utf-8")
        os.replace(temp, self.path)

    def use_account(self, user_id):
        """Switching to a different account starts its sync from scratch (a merge, never a wipe)."""
        if user_id != self.user_id:
            self.user_id = user_id
            self.cursor = None
            self.base = {}


class Account:
    """The sign-in for one profile: keeps the session fresh and remembers it securely."""

    SIGNED_OUT_CODES = ("refresh_token_not_found", "session_not_found", "unauthorized", "invalid_grant")

    def __init__(self, folder, client=None):
        self.client = client or CloudClient()
        self.tokens = TokenStore(folder)
        self.state = SyncState(folder)
        self.saved = self.tokens.load()
        self.session = None

    @property
    def signed_in(self):
        return bool(self.session or self.saved)

    @property
    def email(self):
        return self.session.email if self.session else (self.saved or {}).get("email", "")

    def remember(self, session):
        """Keep a fresh session (Supabase hands out a new refresh token each time).

        A sign-in still waiting for its authenticator code is never saved.
        """
        if session.needs_second_step:
            raise CloudError(FRIENDLY["insufficient_aal"], "insufficient_aal")
        self.session = session
        self.saved = session.to_dict()
        self.tokens.save(session)
        return session

    def forget(self):
        self.tokens.clear()
        self.session = None
        self.saved = None

    def active_session(self):
        if self.session and not self.session.expiring():
            return self.session
        refresh = (self.session.refresh_token if self.session else "") or (self.saved or {}).get("refresh_token")
        if not refresh:
            raise CloudError("Sign in to sync your cards.", "signed_out")
        try:
            return self.remember(self.client.refresh(refresh))
        except CloudError as error:
            if error.code in self.SIGNED_OUT_CODES:
                self.forget()
            raise

    def sign_out(self):
        if self.session:
            self.client.sign_out(self.session)
        self.forget()

    def delete_account(self):
        self.client.delete_account(self.active_session())
        self.forget()
        self.state.use_account("")
        self.state.save()

    def sync(self, read_payload, write_payload, on_ui=None):
        return sync_profile(self.client, self.active_session(), self.state, read_payload, write_payload, on_ui)


OVERLAP_SECONDS = 120


def pull_since(cursor):
    """Pull from a little before the last position.

    A row can be stamped just before our last pull yet commit just after
    it; reaching back a couple of minutes catches it. Rows already synced
    match the base and change nothing.
    """
    if not cursor:
        return None
    from datetime import datetime, timedelta

    try:
        moment = datetime.fromisoformat(str(cursor).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (moment - timedelta(seconds=OVERLAP_SECONDS)).isoformat()


def sync_profile(client, session, state, read_payload, write_payload, on_ui=None, now_label=None):
    """One full sync: pull, merge and apply here, push, then remember the new base.

    The network calls run on the calling (worker) thread. Reading, merging
    and writing the local data happen together in one step through
    `on_ui(fn)`, which the desktop uses to run them on the UI thread, so a
    review made during the network call is never overwritten; it simply
    goes up with the next sync. Returns counts: pulled, pushed, applied here.
    """
    on_ui = on_ui or (lambda fn: fn())
    state.use_account(session.user_id)
    rows = client.pull(session, pull_since(state.cursor))
    remote = {}
    cursor = state.cursor
    for key, data, updated_at in rows:
        remote[key] = data
        if updated_at and (cursor is None or updated_at > cursor):
            cursor = updated_at

    def merge_locally():
        payload = read_payload()
        local = sync.records_from_payload(payload, state.device_id, state.base)
        plan = sync.plan_sync(local, state.base, remote)
        if plan.apply:
            write_payload(sync.apply_plan(payload, local, plan))
        return plan

    plan = on_ui(merge_locally)
    if plan.push:
        client.push(session, plan.push)
    state.base = plan.final
    state.cursor = cursor
    state.last_synced = now_label() if now_label else time.strftime("%Y-%m-%d %H:%M")
    state.save()
    return {"pulled": len(remote), "pushed": len(plan.push), "applied": len(plan.apply)}
