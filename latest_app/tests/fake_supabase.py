"""An in-memory stand-in for the parts of Supabase MemoryPal uses.

It mimics Supabase Auth (sign-up with an emailed 6-digit code, password
sign-in, refresh, reset by code, password change, sign-out, account
deletion) and the sync_records table with Row Level Security, so the cloud
client and full two-device syncs can be tested without the internet.
Pass `FakeSupabase().open` as CloudClient's `opener`.
"""

import base64
import io
import itertools
import json
import secrets
import urllib.error
import urllib.parse


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()


class FakeSupabase:
    def __init__(self, key="sb_publishable_test", confirm_email=True):
        self.key = key
        self.confirm_email = confirm_email
        self.users = {}       # email -> {id, password, confirmed}
        self.codes = {}       # (email, kind) -> code
        self.tokens = {}      # access token -> user id
        self.refresh = {}     # refresh token -> user id
        self.rows = {}        # (user id, key) -> row
        self.clock = itertools.count(1)
        self.requests = []
        self.offline = False
        self.fail_next_push = False
        self.factors = {}     # factor id -> {user, status}
        self.challenges = {}  # challenge id -> factor id
        self.captcha = False  # CAPTCHA protection on: auth requests need a fresh token
        self.captcha_tokens = set()

    # --------------------------------------------------------------- helpers
    def stamp(self):
        # Real ISO timestamps that keep increasing, like Postgres's clock.
        return f"2026-10-10T12:00:00.{next(self.clock):06d}+00:00"

    TOTP_CODE = "246810"

    def session(self, user_id, aal="aal1"):
        # A JWT-shaped token whose middle part carries the assurance level.
        claims = base64.urlsafe_b64encode(json.dumps({"sub": user_id, "aal": aal}).encode()).decode().rstrip("=")
        access, refresh = f"eyJhbGciOiJIUzI1NiJ9.{claims}.{secrets.token_hex(8)}", secrets.token_hex(8)
        self.tokens[access] = (user_id, aal)
        self.refresh[refresh] = (user_id, aal)
        return {"access_token": access, "refresh_token": refresh, "expires_in": 3600, "user": self.user_json(user_id)}

    def user_json(self, user_id):
        email = next(email for email, user in self.users.items() if user["id"] == user_id)
        factors = [{"id": fid, "factor_type": "totp", "status": factor["status"], "friendly_name": "Authenticator"} for fid, factor in self.factors.items() if factor["user"] == user_id]
        return {"id": user_id, "email": email, "factors": factors}

    def has_verified_factor(self, user_id):
        return any(f["user"] == user_id and f["status"] == "verified" for f in self.factors.values())

    @staticmethod
    def error(request, status, code, msg=""):
        body = json.dumps({"code": status, "error_code": code, "msg": msg}).encode("utf-8")
        return urllib.error.HTTPError(request.full_url, status, msg or code, {}, io.BytesIO(body))

    # ---------------------------------------------------------------- server
    def open(self, request, timeout=None):
        if self.offline:
            raise urllib.error.URLError("offline")
        self.requests.append(request)
        if request.get_header("Apikey") != self.key:
            raise self.error(request, 401, "invalid_api_key")
        url = urllib.parse.urlparse(request.full_url)
        query = urllib.parse.parse_qs(url.query)
        body = json.loads(request.data) if request.data else None
        auth = request.get_header("Authorization") or ""
        user_id, aal = self.tokens.get(auth.removeprefix("Bearer "), (None, None)) if auth else (None, None)
        self.aal = aal
        result = self.route(request, request.get_method(), url.path, query, body, user_id)
        return FakeResponse(json.dumps(result).encode("utf-8") if result is not None else b"")

    def route(self, request, method, path, query, body, user_id):
        password_grant = path == "/auth/v1/token" and query.get("grant_type") == ["password"]
        if self.captcha and (path in ("/auth/v1/signup", "/auth/v1/recover", "/auth/v1/resend") or password_grant):
            token = ((body or {}).get("gotrue_meta_security") or {}).get("captcha_token")
            if token not in self.captcha_tokens:
                raise self.error(request, 400, "captcha_failed", "captcha protection: request disallowed")
            self.captcha_tokens.discard(token)  # single use, like Turnstile's
        if path == "/auth/v1/signup":
            email = body["email"].lower()
            if email in self.users:
                raise self.error(request, 422, "user_already_exists", "User already registered")
            if len(body["password"]) < 6:
                raise self.error(request, 422, "weak_password")
            self.users[email] = {"id": secrets.token_hex(6), "password": body["password"], "confirmed": not self.confirm_email, "metadata": dict(body.get("data") or {})}
            if self.confirm_email:
                self.codes[(email, "signup")] = "123456"
                return {"id": self.users[email]["id"], "email": email}
            return self.session(self.users[email]["id"])
        if path == "/auth/v1/verify":
            email = body["email"].lower()
            if self.codes.get((email, body["type"])) != body["token"]:
                raise self.error(request, 403, "otp_expired", "Token has expired or is invalid")
            del self.codes[(email, body["type"])]
            self.users[email]["confirmed"] = True
            return self.session(self.users[email]["id"])
        if path == "/auth/v1/resend":
            self.codes[(body["email"].lower(), "signup")] = "123456"
            return {}
        if path == "/auth/v1/token" and query.get("grant_type") == ["password"]:
            user = self.users.get(body["email"].lower())
            if not user or user["password"] != body["password"]:
                raise self.error(request, 400, "invalid_credentials", "Invalid login credentials")
            if not user["confirmed"]:
                raise self.error(request, 400, "email_not_confirmed")
            return self.session(user["id"])
        if path == "/auth/v1/token" and query.get("grant_type") == ["refresh_token"]:
            owner = self.refresh.pop(body["refresh_token"], None)
            if owner is None:
                raise self.error(request, 400, "refresh_token_not_found")
            return self.session(*owner)  # a refreshed session keeps its level
        if path == "/auth/v1/recover":
            if body["email"].lower() in self.users:
                self.codes[(body["email"].lower(), "recovery")] = "654321"
            return {}
        if user_id is None:
            raise self.error(request, 401, "no_authorization")
        if path == "/auth/v1/user" and method == "GET":
            return self.user_json(user_id)
        if path == "/auth/v1/factors" and method == "POST":
            if self.has_verified_factor(user_id):
                raise self.error(request, 422, "too_many_enrolled_mfa_factors")
            factor_id = secrets.token_hex(6)
            self.factors[factor_id] = {"user": user_id, "status": "unverified"}
            return {"id": factor_id, "type": "totp", "totp": {"secret": "JBSWY3DPEHPK3PXP", "uri": "otpauth://totp/MemoryPal:x?secret=JBSWY3DPEHPK3PXP", "qr_code": "<svg/>"}}
        if path.startswith("/auth/v1/factors/") and path.endswith("/challenge"):
            factor_id = path.split("/")[4]
            if self.factors.get(factor_id, {}).get("user") != user_id:
                raise self.error(request, 404, "mfa_factor_not_found")
            challenge_id = secrets.token_hex(6)
            self.challenges[challenge_id] = factor_id
            return {"id": challenge_id, "type": "totp"}
        if path.startswith("/auth/v1/factors/") and path.endswith("/verify"):
            factor_id = path.split("/")[4]
            if self.challenges.pop(body["challenge_id"], None) != factor_id or body["code"] != self.TOTP_CODE:
                raise self.error(request, 422, "mfa_verification_failed")
            self.factors[factor_id]["status"] = "verified"
            return self.session(user_id, "aal2")
        if path.startswith("/auth/v1/factors/") and method == "DELETE":
            factor_id = path.split("/")[4]
            if self.has_verified_factor(user_id) and self.aal != "aal2":
                raise self.error(request, 403, "insufficient_aal")
            self.factors.pop(factor_id, None)
            return {"id": factor_id}
        if path == "/auth/v1/user" and method == "PUT":
            email = next(email for email, user in self.users.items() if user["id"] == user_id)
            self.users[email]["password"] = body["password"]
            return {"id": user_id}
        if path == "/auth/v1/logout":
            for token in [t for t, owner in self.tokens.items() if owner == user_id]:
                del self.tokens[token]
            return None
        if path == "/rest/v1/rpc/delete_my_account":
            email = next(email for email, user in self.users.items() if user["id"] == user_id)
            del self.users[email]
            for key in [k for k in self.rows if k[0] == user_id]:
                del self.rows[key]
            return None
        if path.startswith("/rest/v1/") and self.has_verified_factor(user_id) and self.aal != "aal2":
            # The restrictive policy in schema.sql: two-step accounts need aal2.
            raise self.error(request, 403, "42501", "new row violates row-level security policy")
        if path == "/rest/v1/sync_records" and method == "GET":
            rows = sorted((row for (owner, _key), row in self.rows.items() if owner == user_id), key=lambda row: (row["updated_at"], row["key"]))
            since = query.get("updated_at", [""])[0]
            if since.startswith("gte."):
                rows = [row for row in rows if row["updated_at"] >= since[4:]]
            offset, limit = int(query.get("offset", ["0"])[0]), int(query.get("limit", ["1000"])[0])
            return [dict(row) for row in rows[offset:offset + limit]]
        if path == "/rest/v1/sync_records" and method == "POST":
            if self.fail_next_push:
                self.fail_next_push = False
                raise urllib.error.URLError("connection dropped")
            for row in body:
                # Row Level Security: the row always belongs to the caller.
                self.rows[(user_id, row["key"])] = {"key": row["key"], "kind": row["kind"], "data": row["data"], "deleted": row["deleted"], "updated_at": self.stamp()}
            return None
        raise self.error(request, 404, "not_found", path)

    # ------------------------------------------------------------- test aids
    def rows_for(self, email):
        user_id = self.users[email]["id"]
        return {key: row for (owner, key), row in self.rows.items() if owner == user_id}
