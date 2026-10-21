"""Syncing a profile through the person's own Google Drive, using only the standard library.

The cards, notes, settings and review counts live in the person's Drive, in
the hidden app folder only MemoryPal can see (scope ``drive.appdata``), not
on MemoryPal's servers. Each device keeps one file there,
``memorypal-<device id>.json``, holding all its records with a stamp each;
sync.py explains how the files are combined.

- GoogleSignIn connects a Google account in the browser (loopback redirect
  with PKCE, the flow Google recommends for desktop apps).
- DriveFiles lists, reads and writes the files; FolderFiles does the same
  in a local folder, for tests.
- DriveLink keeps the connection for one profile (the refresh token is
  stored like the MemoryPal sign-in: DPAPI, Keychain or an owner-only file).
- sync_files runs one sync against either.

Network calls block; the desktop runs them on a worker thread.
"""

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from . import cloud, cloud_config, sync

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
FILES_URL = "https://www.googleapis.com/drive/v3/files"
UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.appdata"
SCOPES = f"openid email {DRIVE_SCOPE}"
TIMEOUT = 30
# One device's file is a few MB even with thousands of cards; anything far
# bigger is not ours to read.
MAX_FILE_BYTES = 64 * 1024 * 1024

MESSAGES = {
    "drive_signed_out": "Google Drive was disconnected. Connect it again in Settings to keep syncing.",
    "drive_scope": "MemoryPal needs permission to keep its sync file in your Google Drive. Connect again and leave the Google Drive box ticked.",
    "drive_full": "Your Google Drive is full, so MemoryPal can't save your cards there. Free up space in Google Drive, then sync again.",
    "drive_busy": "Google Drive is busy right now. MemoryPal will try again in a few minutes.",
    "drive_offline": "Couldn't reach Google Drive. Check the internet connection and try again.",
    "drive_cancelled": "Google Drive wasn't connected. Try again when you're ready.",
    "drive_timeout": "Connecting Google Drive wasn't finished. Try again, and finish it in the browser window that opens.",
    "drive_not_linked": "Connect Google Drive in Settings to sync your cards.",
}


def drive_error(code):
    return cloud.CloudError(MESSAGES[code], code)


def client_config():
    """(client id, client secret) of this build's Google sign-in, or empty strings.

    Google calls the secret of a desktop app "not secret" (it ships inside
    every copy), but it is still kept out of the repository: the release
    build writes it into google_client.py.
    """
    client_id = os.environ.get("MEMORYPAL_GOOGLE_CLIENT_ID", cloud_config.GOOGLE_DESKTOP_CLIENT_ID)
    secret = os.environ.get("MEMORYPAL_GOOGLE_CLIENT_SECRET", cloud_config.GOOGLE_DESKTOP_CLIENT_SECRET)
    return client_id.strip(), secret.strip()


def configured():
    return bool(client_config()[0])


def _claims(id_token):
    """The id token's payload (it came straight from Google over TLS, so no signature check)."""
    try:
        payload = id_token.split(".")[1]
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError, AttributeError):
        return {}
    return data if isinstance(data, dict) else {}


class GoogleSignIn:
    """Connects a Google account: opens Google's page in the browser and waits on
    127.0.0.1 for the answer. Blocks, so call it from a worker thread."""

    DONE_PAGE = cloud.BrowserCheck.DONE_PAGE

    def __init__(self, client_id=None, client_secret=None, opener=None, open_page=None, timeout=300):
        default_id, default_secret = client_config()
        self.client_id = client_id or default_id
        self.client_secret = client_secret if client_secret is not None else default_secret
        self.opener = opener or urllib.request.urlopen
        self.open_page = open_page
        self.timeout = timeout

    def __call__(self):
        import http.server
        import threading
        import webbrowser

        if not self.client_id:
            raise cloud.CloudError("Google Drive sync isn't set up in this copy of MemoryPal yet.", "not_configured")
        state = secrets.token_urlsafe(18)
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
        result = {}
        answered = threading.Event()
        done_page = self.DONE_PAGE

        class Handler(http.server.BaseHTTPRequestHandler):
            timeout = 5

            def do_GET(self):
                parts = urllib.parse.urlsplit(self.path)
                values = urllib.parse.parse_qs(parts.query)
                if parts.path != "/" or values.get("state", [""])[0] != state or answered.is_set():
                    self.send_error(404)
                    return
                result["code"] = values.get("code", [""])[0][:2048]
                result["error"] = values.get("error", [""])[0][:200]
                answered.set()
                title = "Google Drive is connected" if result["code"] else "Google Drive wasn't connected"
                body = done_page.format(title=title).encode("utf-8")
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
        redirect = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            address = AUTH_URL + "?" + urllib.parse.urlencode({
                "client_id": self.client_id, "redirect_uri": redirect, "response_type": "code", "scope": SCOPES,
                "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
                "access_type": "offline", "prompt": "consent select_account",
            })
            if (self.open_page or webbrowser.open)(address) is False:
                raise cloud.CloudError("Couldn't open your web browser to connect Google Drive.", "drive_cancelled")
            deadline = time.monotonic() + self.timeout
            while not answered.is_set() and time.monotonic() < deadline:
                server.handle_request()
        finally:
            server.server_close()
        if not answered.is_set():
            raise drive_error("drive_timeout")
        if not result.get("code"):
            raise drive_error("drive_cancelled")
        tokens = self.token({
            "code": result["code"], "client_id": self.client_id, "client_secret": self.client_secret,
            "redirect_uri": redirect, "grant_type": "authorization_code", "code_verifier": verifier,
        })
        return self.link_from(tokens)

    @staticmethod
    def link_from(tokens):
        """What a profile keeps from a new connection."""
        if DRIVE_SCOPE not in str(tokens.get("scope", "")).split():
            raise drive_error("drive_scope")
        claims = _claims(tokens.get("id_token", ""))
        if not tokens.get("refresh_token") or not claims.get("sub"):
            raise drive_error("drive_cancelled")
        return {
            "refresh_token": tokens["refresh_token"], "user_id": str(claims["sub"]), "email": str(claims.get("email", "")),
            "access_token": tokens.get("access_token", ""), "expires_at": time.time() + float(tokens.get("expires_in", 0) or 0),
        }

    def token(self, form):
        request = urllib.request.Request(
            TOKEN_URL, data=urllib.parse.urlencode(form).encode("ascii"), method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        )
        try:
            with self.opener(request, timeout=TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8", "replace") or "{}")
            except (ValueError, OSError):
                detail = {}
            if detail.get("error") in ("invalid_grant", "unauthorized_client", "invalid_client"):
                raise drive_error("drive_signed_out") from None
            raise drive_error("drive_busy") from None
        except (urllib.error.URLError, OSError, TimeoutError, ValueError):
            raise drive_error("drive_offline") from None

    def refresh(self, refresh_token):
        """A fresh access token: (token, expires_at)."""
        data = self.token({
            "refresh_token": refresh_token, "client_id": self.client_id, "client_secret": self.client_secret,
            "grant_type": "refresh_token",
        })
        if not data.get("access_token"):
            raise drive_error("drive_signed_out")
        return data["access_token"], time.time() + float(data.get("expires_in", 0) or 0)

    def revoke(self, token):
        """Take back MemoryPal's access to the Drive (best effort: the link is forgotten either way)."""
        request = urllib.request.Request(
            REVOKE_URL, data=urllib.parse.urlencode({"token": token}).encode("ascii"), method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with self.opener(request, timeout=TIMEOUT) as response:
                response.read()
        except (urllib.error.URLError, OSError, TimeoutError):
            pass


class DriveFiles:
    """The device files in the Drive's hidden app folder."""

    def __init__(self, access_token, opener=None):
        # access_token() returns a fresh token; access_token(True) gets a new one.
        self.access_token = access_token
        self.opener = opener or urllib.request.urlopen

    def request(self, method, url, body=None, content_type=None, retry=True):
        headers = {"Authorization": f"Bearer {self.access_token()}", "Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with self.opener(request, timeout=TIMEOUT) as response:
                return response.read(MAX_FILE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if exc.code == 401 and retry:
                self.access_token(True)
                return self.request(method, url, body, content_type, retry=False)
            try:
                text = exc.read().decode("utf-8", "replace")
            except OSError:
                text = ""
            if exc.code == 401:
                raise drive_error("drive_signed_out") from None
            if exc.code == 404:
                raise cloud.CloudError("That file is no longer in Google Drive.", "drive_missing") from None
            if "storageQuotaExceeded" in text:
                raise drive_error("drive_full") from None
            if exc.code == 403 and "insufficientPermissions" in text:
                raise drive_error("drive_scope") from None
            raise drive_error("drive_busy") from None
        except (urllib.error.URLError, OSError, TimeoutError):
            raise drive_error("drive_offline") from None

    def list(self):
        """[{"id", "name", "version"}] for every MemoryPal file in the app folder."""
        files, page = [], ""
        while True:
            query = {"spaces": "appDataFolder", "pageSize": 1000, "fields": "nextPageToken,files(id,name,version,size)"}
            if page:
                query["pageToken"] = page
            data = json.loads(self.request("GET", FILES_URL + "?" + urllib.parse.urlencode(query)) or b"{}")
            for item in data.get("files", []):
                name = str(item.get("name", ""))
                if name.startswith(sync.FILE_PREFIX) and int(item.get("size") or 0) <= MAX_FILE_BYTES:
                    files.append({"id": str(item["id"]), "name": name, "version": str(item.get("version", ""))})
            page = data.get("nextPageToken")
            if not page:
                return files

    def read(self, file_id):
        return self.request("GET", f"{FILES_URL}/{urllib.parse.quote(file_id)}?alt=media")

    def write(self, name, body, file_id=None):
        """Create or overwrite a file; returns {"id", "version"}."""
        if file_id:
            url = f"{UPLOAD_URL}/{urllib.parse.quote(file_id)}?uploadType=media&fields=id,version"
            data = self.request("PATCH", url, body, "application/json")
        else:
            boundary = uuid.uuid4().hex
            meta = json.dumps({"name": name, "parents": ["appDataFolder"], "mimeType": "application/json"}).encode("utf-8")
            multipart = b"".join([
                f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode("ascii"), meta,
                f"\r\n--{boundary}\r\nContent-Type: application/json\r\n\r\n".encode("ascii"), body,
                f"\r\n--{boundary}--".encode("ascii"),
            ])
            data = self.request("POST", f"{UPLOAD_URL}?uploadType=multipart&fields=id,version", multipart, f"multipart/related; boundary={boundary}")
        info = json.loads(data or b"{}")
        return {"id": str(info.get("id", file_id or "")), "version": str(info.get("version", ""))}


class FolderFiles:
    """DriveFiles' twin in a local folder (tests, and a stand-in drive)."""

    def __init__(self, folder):
        self.folder = Path(folder)

    def list(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        return [
            {"id": path.name, "name": path.name, "version": str(path.stat().st_mtime_ns)}
            for path in sorted(self.folder.glob(sync.FILE_PREFIX + "*"))
        ]

    def read(self, file_id):
        try:
            return (self.folder / file_id).read_bytes()
        except OSError:
            raise cloud.CloudError("That file is no longer in Google Drive.", "drive_missing") from None

    def write(self, name, body, file_id=None):
        path = self.folder / (file_id or name)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".tmp")
        temp.write_bytes(body)
        os.replace(temp, path)
        stat = path.stat()
        # Two writes within the clock's resolution must still look different.
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1))
        return {"id": path.name, "version": str(path.stat().st_mtime_ns)}


class DriveLink:
    """The Google Drive connection for one profile."""

    def __init__(self, folder, sign_in=None):
        self.tokens = cloud.TokenStore(folder, "drive.bin")
        self.sign_in = sign_in or GoogleSignIn()
        self.saved = self.tokens.load()
        self.access = ("", 0.0)

    @property
    def linked(self):
        return bool(self.saved)

    @property
    def email(self):
        return (self.saved or {}).get("email", "")

    @property
    def user_id(self):
        return (self.saved or {}).get("user_id", "")

    def connect(self):
        """Connect a Google account in the browser (blocks; run it on a worker thread)."""
        link = self.sign_in()
        self.remember(link)
        return link

    def remember(self, link):
        self.saved = {key: link[key] for key in ("refresh_token", "user_id", "email")}
        self.access = (link.get("access_token", ""), float(link.get("expires_at", 0) or 0))
        self.tokens.save(self.saved)

    def access_token(self, renew=False):
        token, expires_at = self.access
        if token and not renew and expires_at - 60 > time.time():
            return token
        if not self.saved:
            raise drive_error("drive_signed_out")
        try:
            self.access = self.sign_in.refresh(self.saved["refresh_token"])
        except cloud.CloudError as error:
            if error.code == "drive_signed_out":
                self.forget()
            raise
        return self.access[0]

    def files(self, opener=None):
        return DriveFiles(self.access_token, opener)

    def forget(self):
        self.tokens.clear()
        self.saved = None
        self.access = ("", 0.0)

    def disconnect(self):
        """Forget the connection here and take back MemoryPal's access to the Drive."""
        refresh = (self.saved or {}).get("refresh_token")
        self.forget()
        if refresh:
            self.sign_in.revoke(refresh)


def read_entries(files, file_id):
    try:
        return sync.entries_of(json.loads(files.read(file_id).decode("utf-8")))
    except cloud.CloudError as error:
        if error.code == "drive_missing":
            return {}  # removed between listing and reading
        raise
    except (ValueError, UnicodeDecodeError, RecursionError):
        return {}  # a damaged file is skipped, never read as deletions


def sync_files(files, state, user_id, read_payload, write_payload, on_ui=None, now_label=None, mode=None, now_ms=None):
    """One full sync through the device files: read what changed, merge here, write this device's file.

    Only files that changed since the last sync are read: this device's own
    file already holds the newest copy of everything it saw then. As with
    cloud.sync_profile, a profile that last synced with another Google
    account asks first (CloudError "other_account").
    """
    if state.drive_user and state.drive_user != user_id and mode not in ("merge", "replace"):
        raise cloud.CloudError(cloud.FRIENDLY["other_account"], "other_account")
    state.use_drive(user_id)
    listing = files.list()
    own_name = sync.file_name(state.device_id)
    own_file = state.drive_file if any(item["id"] == state.drive_file for item in listing) else ""
    if not own_file:
        own_file = next((item["id"] for item in listing if item["name"] == own_name), "")
    seen = dict(state.drive_seen)
    entries = [state.entries]
    for item in listing:
        if item["id"] == own_file or seen.get(item["id"]) == item["version"]:
            continue
        entries.append(read_entries(files, item["id"]))
        seen[item["id"]] = item["version"]
    remote, stamps = sync.remote_from_files(entries)
    plan = cloud.merge_into(remote, state, read_payload, write_payload, on_ui, mode)
    stamp = sync.next_stamp(sync.newest_stamp(stamps), state.device_id, time.time() * 1000 if now_ms is None else now_ms)
    own = sync.entries_after(state.entries, plan, remote, stamps, stamp)
    if own != state.entries or not own_file:
        body = json.dumps(sync.file_content(state.device_id, own, stamp), separators=(",", ":")).encode("utf-8")
        try:
            written = files.write(own_name, body, own_file or None)
        except cloud.CloudError as error:
            if error.code != "drive_missing":
                raise
            written = files.write(own_name, body)  # the file was removed: make it again
        own_file = written["id"]
        seen[own_file] = written["version"]
    present = {item["id"] for item in listing} | {own_file}
    state.drive_seen = {file_id: version for file_id, version in seen.items() if file_id in present}
    state.drive_file = own_file
    state.entries = own
    state.base = plan.final
    state.last_synced = now_label() if now_label else time.strftime("%Y-%m-%d %H:%M")
    state.save()
    return {"pulled": len(remote), "pushed": len(plan.push), "applied": len(plan.apply)}
