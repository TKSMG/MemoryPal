"""Accounts and sync with the MemoryPal cloud (Supabase), using only the standard library.

- CloudClient talks to Supabase Auth (email + password, emailed codes
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


def captcha_url():
    """The CAPTCHA check page, or "" when the check is off."""
    value = os.environ.get("MEMORYPAL_CAPTCHA_URL")
    return (cloud_config.CAPTCHA_URL if value is None else value).strip()


# Requests the server refuses without a CAPTCHA token once CAPTCHA protection
# is on (refreshing a session never needs one).
CAPTCHA_PATHS = ("/auth/v1/signup", "/auth/v1/recover", "/auth/v1/resend")


def needs_captcha(path, query):
    return path in CAPTCHA_PATHS or (path == "/auth/v1/token" and (query or {}).get("grant_type") == "password")


class CloudError(Exception):
    """A failure with a message that can be shown to people as it is."""

    def __init__(self, message, code=""):
        super().__init__(message)
        self.message = message
        self.code = code


FRIENDLY = {
    "invalid_credentials": "That email and password don't match. Check them, or reset your password.",
    "invalid_grant": "That email and password don't match. Check them, or reset your password.",
    "email_not_confirmed": "Confirm your email first: enter the code we emailed you.",
    "captcha_failed": "The quick check that keeps out bots didn't work. Try again.",
    "captcha_timeout": "The quick check in your browser wasn't finished. Try again, and finish it in the browser window that opens.",
    "user_already_exists": "There's already an account with this email. Sign in instead.",
    "email_exists": "There's already an account with this email. Sign in instead.",
    "weak_password": f"Choose a stronger password: at least {MIN_PASSWORD} characters with letters and at least one number.",
    "over_email_send_rate_limit": "Too many emails were sent just now. Wait a few minutes and try again.",
    "over_request_rate_limit": "Too many tries in a short time. Wait a minute and try again.",
    "otp_expired": "That code is wrong or has expired. Ask for a new one.",
    "validation_failed": "Check the email address and try again.",
    "email_address_invalid": "That doesn't look like an email address.",
    "signup_disabled": "New accounts can't be made right now.",
    "refresh_token_not_found": "You've been signed out. Please sign in again.",
    "session_not_found": "You've been signed out. Please sign in again.",
    "refresh_token_already_used": "You've been signed out. Please sign in again.",
    "two_step_now_on": "This account now uses two-step sign-in. Sign in again with your authenticator code.",
    "other_account": "This profile last synced with a different account. Choose what to do with its cards before syncing.",
    "mfa_verification_failed": "That authenticator code isn't right. Check the time on this device and try the newest code.",
    "mfa_challenge_expired": "That took too long. Try again with a fresh code.",
    "insufficient_aal": "Finish two-step sign-in first: enter the code from your authenticator app.",
    "mfa_factor_not_found": "Two-step sign-in isn't set up for this account any more.",
    "too_many_enrolled_mfa_factors": "Two-step sign-in is already set up. Turn it off first to set it up again.",
    # The per-person storage allowance in schema.sql (sync_records_quota).
    "P0001": "Your cloud copy is full. Delete cards or notes you no longer need, then sync again.",
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


class BrowserCheck:
    """Gets a CAPTCHA token from the check page in the person's web browser.

    Tk has no web view, so this opens the page with a one-time port and state
    in the address, and waits on 127.0.0.1 for the page to hand the token
    back. Blocks, so call it from a worker thread.
    """

    DONE_PAGE = (
        "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
        "<title>MemoryPal</title><body style='font:16px system-ui,sans-serif;text-align:center;padding:48px 16px'>"
        "<h1 style='font-size:22px'>{title}</h1><p>You can close this tab and go back to MemoryPal.</p>"
    )

    def __init__(self, page_url, open_page=None, timeout=180):
        self.page_url = page_url
        self.open_page = open_page
        self.timeout = timeout

    def __call__(self):
        import http.server
        import secrets
        import threading
        import webbrowser

        state = secrets.token_urlsafe(18)
        result = {}
        answered = threading.Event()
        done_page = self.DONE_PAGE

        class Handler(http.server.BaseHTTPRequestHandler):
            timeout = 5  # a browser's idle pre-connection mustn't hold the loop

            def do_GET(self):
                parts = urllib.parse.urlsplit(self.path)
                values = urllib.parse.parse_qs(parts.query)
                if parts.path != "/done" or values.get("state", [""])[0] != state or answered.is_set():
                    self.send_error(404)
                    return
                if values.get("token", [""])[0]:
                    result["token"] = values["token"][0][:4096]
                answered.set()
                body = done_page.format(title="All set" if result.get("token") else "The check didn't work").encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        server.timeout = 0.5
        try:
            address = f"{self.page_url}#port={server.server_address[1]}&state={state}"
            if (self.open_page or webbrowser.open)(address) is False:
                raise CloudError("Couldn't open your web browser for the quick check that keeps out bots.", "captcha_failed")
            deadline = time.monotonic() + self.timeout
            while not answered.is_set() and time.monotonic() < deadline:
                server.handle_request()
        finally:
            server.server_close()
        if result.get("token"):
            return result["token"]
        if answered.is_set():
            raise CloudError(FRIENDLY["captcha_failed"], "captcha_failed")
        raise CloudError(FRIENDLY["captcha_timeout"], "captcha_timeout")


def browser_check():
    """A BrowserCheck for this build's check page, or None when the check is off."""
    url = captcha_url()
    return BrowserCheck(url) if url else None


class CloudClient:
    def __init__(self, url=None, key=None, opener=None, timeout=TIMEOUT, captcha=None):
        default_url, default_key = config()
        self.url = (url or default_url).rstrip("/")
        self.key = key or default_key
        self.opener = opener or urllib.request.urlopen
        self.timeout = timeout
        # Called for a CAPTCHA token before sign-in, sign-up and emailed codes.
        self.captcha = captcha

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
        if self.captcha and body is not None and needs_captcha(path, query):
            body = dict(body, gotrue_meta_security={"captcha_token": self.captcha()})
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
        except (ValueError, RecursionError):  # garbled, or nested deeply enough to crash the parser
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
    def sign_up(self, email, password, consent=None):
        """Create an account. Returns a Session, or None when the email must be confirmed first.

        `consent` (see consent_record) is kept with the account as a record
        that the person confirmed their age and accepted the Terms.
        """
        check_password(password, email)
        body = {"email": email.strip(), "password": password}
        if consent:
            body["data"] = dict(consent)
        data = self.request("POST", "/auth/v1/signup", body) or {}
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

    def delete_sync_records(self, session):
        """Remove this account's synced records once they have moved to the person's own drive."""
        self.request("POST", "/rest/v1/rpc/delete_my_sync_records", {}, token=session.access_token)

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
                data = None if row.get("deleted") else row.get("data")
                if not row.get("deleted") and not isinstance(data, dict):
                    continue  # a malformed row is skipped, never read as a delete
                rows.append((row["key"], data, row.get("updated_at")))
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


def consent_record(now=None):
    """What a new account keeps about consent: no birth date, just the outcome."""
    moment = time.gmtime(now if now is not None else time.time())
    return {
        "age_confirmed": f"{security.MIN_ACCOUNT_AGE}+",
        "terms_version": security.TERMS_VERSION,
        "terms_accepted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", moment),
    }


class AgeGate:
    """Remembers, on this device, that an age check refused an account (for a day)."""

    def __init__(self, folder, clock=time.time):
        self.path = Path(folder) / "age-check.json"
        self.clock = clock

    def blocked(self):
        try:
            until = float(json.loads(self.path.read_text(encoding="utf-8")).get("refused_until", 0))
        except (OSError, ValueError, AttributeError, TypeError):
            return False
        return self.clock() < until

    def refuse(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"refused_until": self.clock() + security.AGE_RETRY_SECONDS}), encoding="utf-8")
        except OSError:
            pass


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


KEYCHAIN_SERVICE = "app.memorypal.sign-in"


def _keychain(*args, secret=None):
    """Run the Mac `security` tool; the secret goes in on stdin, never in argv."""
    import subprocess

    try:
        if secret is not None:
            # Interactive mode reads the command from stdin, so the token never
            # shows in the process list. Base64 has no quotes or spaces to escape.
            command = " ".join(args) + f" -w {secret}\n"
            result = subprocess.run(["/usr/bin/security", "-i"], input=command, capture_output=True, text=True, timeout=10)
        else:
            result = subprocess.run(["/usr/bin/security", *args], capture_output=True, text=True, timeout=10)
    except subprocess.SubprocessError as error:
        raise OSError(str(error)) from error
    if result.returncode != 0:
        raise OSError(result.stderr.strip() or "Keychain refused")
    return result.stdout


class TokenStore:
    """The refresh token for one profile: DPAPI-encrypted on Windows, in the
    login Keychain on a Mac, and an owner-only file elsewhere.

    On a Mac the file only names the Keychain item (a random id, so renaming
    the profile folder keeps the sign-in).
    """

    def __init__(self, folder, name="account.bin"):
        self.path = Path(folder) / name

    def save(self, session):
        raw = json.dumps(session if isinstance(session, dict) else session.to_dict()).encode("utf-8")
        if sys.platform.startswith("win"):
            blob = b"DPAPI1" + _dpapi(raw, True)
        elif sys.platform == "darwin" and self._save_to_keychain(raw):
            blob = b"KEYCH1" + self._keychain_item.encode("ascii")
        else:
            blob = b"PLAIN1" + base64.b64encode(raw)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(self.path.name + ".tmp")
        try:
            temp.unlink()
        except OSError:
            pass
        # Owner-only from the moment it exists (matters off Windows, where
        # there is no DPAPI and the file itself is the protection).
        handle = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o600)
        with os.fdopen(handle, "wb") as file:
            file.write(blob)
        os.replace(temp, self.path)

    _keychain_item = ""

    def _existing_item(self):
        try:
            blob = self.path.read_bytes()
        except OSError:
            return ""
        item = blob[6:].decode("ascii", "ignore") if blob.startswith(b"KEYCH1") else ""
        return item if item.isalnum() else ""

    def _save_to_keychain(self, raw):
        item = self._existing_item() or uuid.uuid4().hex
        secret = base64.b64encode(raw).decode("ascii")
        try:
            _keychain("add-generic-password", "-U", "-s", KEYCHAIN_SERVICE, "-a", item, secret=secret)
            # Interactive mode doesn't report a failed command in its exit
            # status, so read it back before trusting it.
            if _keychain("find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", item, "-w").strip() != secret:
                return False
        except (OSError, ValueError):
            return False
        self._keychain_item = item
        return True

    def load(self):
        """{refresh_token, user_id, email} or None."""
        try:
            blob = self.path.read_bytes()
            if blob.startswith(b"DPAPI1"):
                raw = _dpapi(blob[6:], False)
            elif blob.startswith(b"KEYCH1"):
                item = self._existing_item()
                raw = base64.b64decode(_keychain("find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", item, "-w").strip()) if item else b""
            elif blob.startswith(b"PLAIN1") and not sys.platform.startswith("win"):
                # Windows always encrypts, so a plain file there was planted.
                raw = base64.b64decode(blob[6:])
            else:
                raw = b""
            data = json.loads(raw.decode("utf-8")) if raw else None
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) and data.get("refresh_token") else None

    def clear(self):
        item = self._existing_item()
        if item:
            try:
                _keychain("delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", item)
            except (OSError, ValueError):
                pass
        try:
            self.path.unlink()
        except OSError:
            pass


class SyncState:
    """Per profile: device id, account it syncs with, pull position, and the last synced records.

    With Google Drive sync it also keeps the Google account, this device's
    file there (its id and records with their stamps) and the versions of
    the files already read.
    """

    def __init__(self, folder):
        self.path = Path(folder) / "sync-state.json"
        self.device_id = ""
        self.user_id = ""
        self.cursor = None
        self.base = {}
        self.last_synced = ""
        self.auto_sync = True  # sync on its own after changes and every few minutes
        self.account_prompted = False  # the first-launch sign-in page was answered
        self.drive_user = ""
        self.drive_file = ""
        self.drive_seen = {}
        self.entries = {}
        self.moved_user = ""  # the MemoryPal account whose records were merged into the drive
        self.cloud_cleanup = False  # ... and still need removing from the MemoryPal cloud
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
        self.auto_sync = raw.get("auto_sync") is not False
        self.account_prompted = bool(raw.get("account_prompted"))
        self.drive_user = str(raw.get("drive_user") or "")
        self.drive_file = str(raw.get("drive_file") or "")
        self.drive_seen = raw.get("drive_seen") if isinstance(raw.get("drive_seen"), dict) else {}
        self.entries = sync.entries_of({"records": raw.get("entries")})
        self.moved_user = str(raw.get("moved_user") or "")
        self.cloud_cleanup = bool(raw.get("cloud_cleanup"))

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(self.path.name + ".tmp")
        temp.write_text(json.dumps({
            "device_id": self.device_id, "user_id": self.user_id, "cursor": self.cursor, "base": self.base,
            "last_synced": self.last_synced, "auto_sync": self.auto_sync, "account_prompted": self.account_prompted,
            "drive_user": self.drive_user, "drive_file": self.drive_file, "drive_seen": self.drive_seen,
            "entries": self.entries, "moved_user": self.moved_user, "cloud_cleanup": self.cloud_cleanup,
        }), encoding="utf-8")
        os.replace(temp, self.path)

    def start_over(self):
        """After a backup import or reset, the next sync merges as if for the first
        time, so cards missing here are fetched back rather than deleted everywhere."""
        self.cursor = None
        self.base = {}
        self.save()

    def use_account(self, user_id):
        """Switching to a different account starts its sync from scratch (a merge, never a wipe)."""
        if user_id != self.user_id:
            self.user_id = user_id
            self.cursor = None
            self.base = {}

    def use_drive(self, user_id):
        """The same for a Google account: a new Drive starts with a fresh file for this device."""
        if user_id != self.drive_user:
            self.drive_user = user_id
            self.drive_file = ""
            self.drive_seen = {}
            self.entries = {}
            self.base = {}


class Account:
    """The sign-in for one profile: keeps the session fresh and remembers it securely."""

    SIGNED_OUT_CODES = ("refresh_token_not_found", "refresh_token_already_used", "session_not_found", "unauthorized", "invalid_grant")

    def __init__(self, folder, client=None, drive_link=None):
        from . import drive

        self.client = client or CloudClient()
        self.tokens = TokenStore(folder)
        self.state = SyncState(folder)
        self.drive = drive_link or drive.DriveLink(folder)
        self.saved = self.tokens.load()
        self.session = None
        # Bumped by forget(), so a refresh that finishes after Sign out
        # can't quietly sign the person back in.
        self.generation = 0

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
        self.generation += 1

    def active_session(self):
        if self.session and not self.session.expiring():
            return self.session
        refresh = (self.session.refresh_token if self.session else "") or (self.saved or {}).get("refresh_token")
        if not refresh:
            raise CloudError("Sign in to sync your cards.", "signed_out")
        generation = self.generation
        try:
            fresh = self.client.refresh(refresh)
        except CloudError as error:
            if error.code in self.SIGNED_OUT_CODES and generation == self.generation:
                self.forget()
            raise
        if generation != self.generation:
            raise CloudError("Sign in to sync your cards.", "signed_out")
        if fresh.needs_second_step:
            # Two-step sign-in was turned on from another device. This
            # session can't reach the data any more and has nowhere to type
            # the code, so sign out and let the sign-in ask for it.
            self.forget()
            raise CloudError(FRIENDLY["two_step_now_on"], "two_step_now_on")
        return self.remember(fresh)

    def sign_out(self):
        """Sign out here and end the session on the server too, so a copy
        of the saved sign-in taken earlier stops working."""
        session = self.session
        if session is None and (self.saved or {}).get("refresh_token"):
            try:
                session = self.client.refresh(self.saved["refresh_token"])
            except CloudError:
                session = None  # already ended, or offline: forget it locally anyway
        try:
            if session is not None:
                self.client.sign_out(session)
        finally:
            self.forget()

    def delete_account(self):
        self.client.delete_account(self.active_session())
        self.forget()
        self.state.use_account("")
        self.state.save()

    @staticmethod
    def uses_drive():
        """Sync goes through Google Drive when this build has it set up; the
        MemoryPal cloud then only keeps the account itself."""
        from . import drive

        return drive.configured()

    @property
    def can_sync(self):
        if self.uses_drive():
            return self.drive.linked
        return configured() and self.signed_in

    @property
    def sync_email(self):
        """The account the cards sync with."""
        return self.drive.email if self.uses_drive() else self.email

    def sync(self, read_payload, write_payload, on_ui=None, mode=None, files=None):
        if not self.uses_drive():
            return sync_profile(self.client, self.active_session(), self.state, read_payload, write_payload, on_ui, mode=mode)
        from . import drive

        if not self.drive.linked:
            raise drive.drive_error("drive_not_linked")
        account_user = self.session.user_id if self.session else (self.saved or {}).get("user_id", "")
        moving = configured() and self.signed_in and account_user != self.state.moved_user
        if moving:
            # Moving to Google Drive: bring this profile up to date with the
            # MemoryPal cloud one last time, then merge everything into the
            # drive as if new, so nothing only the cloud had is lost.
            sync_profile(self.client, self.active_session(), self.state, read_payload, write_payload, on_ui, mode=mode)
            self.state.base = {}
            mode = None  # an account choice above was about the MemoryPal cloud
        result = drive.sync_files(files or self.drive.files(), self.state, self.drive.user_id, read_payload, write_payload, on_ui, mode=mode)
        if moving or self.state.cloud_cleanup:
            # The records are in the drive now: remove them from the MemoryPal
            # cloud (tried again after later syncs until it works).
            if moving:
                self.state.moved_user = account_user
                self.state.cloud_cleanup = True
            try:
                self.client.delete_sync_records(self.active_session())
                self.state.cloud_cleanup = False
            except CloudError:
                pass
            self.state.save()
        return result


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


def merge_into(remote, state, read_payload, write_payload, on_ui=None, mode=None):
    """Merge `remote` into this profile and return the plan (what to send, the new base).

    Reading, merging and writing the local data happen together in one step
    on the UI thread (see sync_profile).
    """
    on_ui = on_ui or (lambda fn: fn())

    def merge_locally():
        payload = read_payload()
        if mode == "replace":
            # Start from an empty profile (settings stay until the account's
            # own arrive), so only the account's records end up here.
            payload = dict(payload, cards=[], captures=[], activity={}, practiced=0)
        local = sync.records_from_payload(payload, state.device_id, state.base)
        plan = sync.plan_sync(local, state.base, remote)
        if plan.apply or mode == "replace":
            write_payload(sync.apply_plan(payload, local, plan))
        return plan

    return on_ui(merge_locally)


def sync_profile(client, session, state, read_payload, write_payload, on_ui=None, now_label=None, mode=None):
    """One full sync: pull, merge and apply here, push, then remember the new base.

    The network calls run on the calling (worker) thread. Reading, merging
    and writing the local data happen together in one step through
    `on_ui(fn)`, which the desktop uses to run them on the UI thread, so a
    review made during the network call is never overwritten; it simply
    goes up with the next sync. Returns counts: pulled, pushed, applied here.

    When this profile last synced with a different account, nothing is sent
    until the person chooses (CloudError "other_account"): `mode="merge"`
    adds this profile's cards to the new account, `mode="replace"` swaps
    them for the account's own. Without that, signing out of one account and
    into another quietly copied the first account's cards into the second.
    """
    on_ui = on_ui or (lambda fn: fn())
    if state.user_id and state.user_id != session.user_id and mode not in ("merge", "replace"):
        raise CloudError(FRIENDLY["other_account"], "other_account")
    state.use_account(session.user_id)
    rows = client.pull(session, pull_since(state.cursor))
    remote = {}
    cursor = state.cursor
    for key, data, updated_at in rows:
        remote[key] = data
        if updated_at and (cursor is None or updated_at > cursor):
            cursor = updated_at
    plan = merge_into(remote, state, read_payload, write_payload, on_ui, mode)
    if plan.push:
        client.push(session, plan.push)
    state.base = plan.final
    state.cursor = cursor
    state.last_synced = now_label() if now_label else time.strftime("%Y-%m-%d %H:%M")
    state.save()
    return {"pulled": len(remote), "pushed": len(plan.push), "applied": len(plan.apply)}
