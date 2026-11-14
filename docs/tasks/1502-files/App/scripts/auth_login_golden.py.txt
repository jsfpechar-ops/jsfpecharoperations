"""Records Python's answers to the login pages for go/internal/web/auth (brief 1502).

Run from App/: .venv/bin/python scripts/auth_login_golden.py
Writes go/internal/web/auth/testdata/login.json and the catalog
go/internal/web/auth/authpage/i18n.json (from its i18n_keys.txt, as
go_host_i18n.py does). Every case starts from the same seed rows on a fresh
SQLite database and goes through the real FastAPI app with the case's
environment applied to config. Recorded per case: status, the headers that
matter, the page HTML (normalised: whitespace runs, form tokens), every
Set-Cookie (attributes, the session and device payloads with times as
offsets, the language value), a 2FA pending token's payload, whether the
bootstrap login file survived, and the watched tables afterwards. The Go test
(login_test.go) replays each case on Postgres and compares.
"""
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock
from urllib.parse import urlencode

APP_DIR = Path(__file__).resolve().parents[1]
REPO = APP_DIR.parent
PKG = REPO / "go" / "internal" / "web" / "auth"
OUT = PKG / "testdata" / "login.json"
PAGES = PKG / "authpage"
SECRET = "auth-login-golden-secret-0123456789-abcdef"
NONCE = "golden-csrf-nonce"
TMP = Path(tempfile.mkdtemp(prefix="auth-login-golden-"))
ENV = {
    "UBYHOST_SECRET_KEY": SECRET,
    "UBYHOST_MAIL_BACKEND": "console",
    "UBYHOST_UBYPORT_ENV": "mock",
}
os.environ.update(ENV)
os.environ.update({
    "UBYHOST_DB": str(TMP / "golden.db"),
    "UBYHOST_DATA_DIR": str(TMP),
    "UBYHOST_ENABLE_SCHEDULER": "0",
    "UBYHOST_BOOTSTRAP_ADMIN": "0",
    "UBYHOST_GUEST_PIN": "0",
})
for key in ("UBYHOST_DATABASE_URL", "UBYHOST_TEST_DATABASE_URL", "UBYHOST_DEPLOYMENT",
            "TURNSTILE_SITE_KEY", "TURNSTILE_SECRET", "TURNSTILE_HOSTNAMES",
            "UBYHOST_STAGING_LOGIN_PASSWORD", "UBYHOST_PUBLIC_BASE_URL", "UBYHOST_APP_BASE_URL",
            "UBYHOST_TRUSTED_PROXY_CIDRS", "UBYHOST_OPERATOR_EMAIL", "UBYHOST_ADMIN_USERNAME",
            "UBYHOST_ADMIN_EMAIL"):
    os.environ.pop(key, None)
sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(APP_DIR / "scripts"))

import requests  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from itsdangerous import URLSafeTimedSerializer  # noqa: E402

from app import auth, client_ip, config, db, security, turnstile  # noqa: E402
from app.main import app  # noqa: E402
from app.templating import templates  # noqa: E402
import go_host_i18n  # noqa: E402

OLD = "2001-01-01T00:00:00+00:00"
FAR = "2099-01-01T00:00:00+00:00"
PAST = "2001-01-02T00:00:00+00:00"
STAMP = re.compile(r"^\d{4}-\d\d-\d\dT")
LINK_KEY = re.compile(r"^(login_link:\d+:)[0-9a-f]{24}$")
TS_HOST = "ubyhost.test"
TURNSTILE = {"UBYHOST_DEPLOYMENT": "production", "TURNSTILE_SITE_KEY": "1x00000000000000000000AA",
             "TURNSTILE_SECRET": "golden-turnstile-secret", "TURNSTILE_HOSTNAMES": TS_HOST}
STAGING = {"UBYHOST_DEPLOYMENT": "staging", "UBYHOST_STAGING_LOGIN_PASSWORD": ' "open sesame" '}


def account(uid, username, role="host", active=1, email=None, **extra):
    row = {
        "id": uid, "username": username, "password_hash": "", "role": role, "active": active,
        "must_change_password": 0, "session_version": 1, "created_at": OLD, "email": email,
        "email_verified_at": PAST,
    }
    row.update(extra)
    return ["user_account", row]


def base_seed():
    return [
        account(1, "admin", "admin", email="admin@example.test", email_verified_at=None),
        account(2, "host", email="host@example.test"),
        # The login pages only read totp_enabled; the secret is never decrypted here.
        account(3, "totp", email="totp@example.test", totp_enabled=1, totp_secret_enc="golden-unused"),
        account(4, "gone", active=0, email="gone@example.test"),
        account(5, "fresh", email="fresh@example.test", email_verified_at=""),
    ]


TABLES = ["alert", "console_mail_log", "email_outbox", "rate_limit_event", "audit", "login_token", "user_account"]

WATCH = {
    "audit": "SELECT action, actor, detail, owner_user_id, actor_user_id, impersonator_user_id FROM audit ORDER BY id",
    "rate_limit_event": "SELECT scope, key FROM rate_limit_event ORDER BY id",
    "login_token": "SELECT user_account_id, purpose, email, remember, next_path, used_at FROM login_token ORDER BY id",
    "user_account": "SELECT id, last_login_at, email_verified_at FROM user_account ORDER BY id",
    "email_outbox": (
        "SELECT idempotency_key, kind, owner_user_id, to_email, subject, state, "
        "json_extract(payload, '$.lang') FROM email_outbox ORDER BY id"
    ),
    "alert": "SELECT level, kind, dedupe_key, resolved_at FROM alert ORDER BY id",
}


def norm(value):
    if value is None:
        return None
    text = str(value)
    if STAMP.match(text) and not text.startswith(("2001-", "2099-")):
        return "<now>"
    return LINK_KEY.sub(r"\1<key>", text)


def dump():
    return {name: [[norm(v) for v in tuple(row)] for row in db.query(sql)] for name, sql in WATCH.items()}


def load_seed(seed, extra, now):
    with db.connect() as conn:
        for table in TABLES:
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM sqlite_sequence")
        for table, row in seed + extra:
            row = {k: (now if v == "<now-epoch>" else v) for k, v in row.items()}
            cols = ", ".join(row)
            marks = ", ".join("?" for _ in row)
            conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(row.values()))


def link_row(token, uid, email, purpose="login", remember=1, next_path="/", expires=FAR, used=None):
    import hashlib

    return ["login_token", {"token_hash": hashlib.sha256(token.encode()).hexdigest(), "user_account_id": uid,
                            "purpose": purpose, "email": email, "remember": remember, "next_path": next_path,
                            "created_at": OLD, "expires_at": expires, "used_at": used}]


def rate_rows(scope, key, n):
    return [["rate_limit_event", {"scope": scope, "key": key, "at": "<now-epoch>"}]] * n


def apply_env(env):
    """config as config.py would have read it at import with env set."""
    values = {
        "DEPLOYMENT": env.get("UBYHOST_DEPLOYMENT", "local").lower(),
        "MAIL_BACKEND": env.get("UBYHOST_MAIL_BACKEND", "disabled").strip().lower(),
        "UBYPORT_ENV": env.get("UBYHOST_UBYPORT_ENV", "mock").lower(),
        "TURNSTILE_SITE_KEY": env.get("TURNSTILE_SITE_KEY", "0x4AAAAAAE0LDM2eoIjssN00").strip(),
        "TURNSTILE_SECRET": env.get("TURNSTILE_SECRET", "").strip(),
        "TURNSTILE_HOSTNAMES": {v.strip().lower() for v in env.get("TURNSTILE_HOSTNAMES", "").split(",") if v.strip()},
        "PUBLIC_BASE_URL": env.get("UBYHOST_PUBLIC_BASE_URL", "http://127.0.0.1:8080").rstrip("/"),
        "APP_BASE_URL": env.get("UBYHOST_APP_BASE_URL", "").strip().rstrip("/"),
        "TRUSTED_PROXY_CIDRS": env.get("UBYHOST_TRUSTED_PROXY_CIDRS", "").strip(),
        "OPERATOR_EMAIL": env.get("UBYHOST_OPERATOR_EMAIL", "").strip() or "support@ubyhost.com",
        "ADMIN_USERNAME": env.get("UBYHOST_ADMIN_USERNAME", "admin").strip().lower(),
        "ADMIN_EMAIL": env.get("UBYHOST_ADMIN_EMAIL", "").strip(),
    }
    values["TURNSTILE_ENABLED"] = bool(values["TURNSTILE_SITE_KEY"] and values["TURNSTILE_SECRET"]
                                       and values["TURNSTILE_HOSTNAMES"])
    saved = {k: getattr(config, k) for k in values}
    for k, v in values.items():
        setattr(config, k, v)
    saved_globals = {k: templates.env.globals[k] for k in ("deployment_tier", "ubyport_env", "turnstile_site_key")}
    templates.env.globals.update(
        deployment_tier=config.DEPLOYMENT, ubyport_env=config.UBYPORT_ENV,
        turnstile_site_key=config.TURNSTILE_SITE_KEY if config.TURNSTILE_ENABLED else "",
    )
    saved_environ = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    client_ip.reset_trusted_proxy_cache()

    def restore():
        for k, v in saved.items():
            setattr(config, k, v)
        templates.env.globals.update(saved_globals)
        for k, v in saved_environ.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        client_ip.reset_trusted_proxy_cache()

    return restore


class FakeSiteverify:
    """requests.post for turnstile.verify: the answer depends on the token only."""

    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return json.loads(self._body)


SITEVERIFY = {
    "good": (200, json.dumps({"success": True, "action": "host_login", "hostname": TS_HOST})),
    "other-action": (200, json.dumps({"success": True, "action": "guest_claim", "hostname": TS_HOST})),
    "down": (503, "unavailable"),
}


def fake_post(url, data=None, timeout=None):
    status, body = SITEVERIFY.get(data["response"], (200, json.dumps({"success": False})))
    return FakeSiteverify(status, body)


def session_cookie(spec, now):
    if not spec:
        return ""
    return auth.issue_session(
        spec["uid"], spec.get("sv", 1), remember=bool(spec.get("rm")),
        issued_at=int(now + spec.get("iat", -60)),
    )


def device_cookie(spec):
    return URLSafeTimedSerializer(SECRET, salt="ubyhost-device").dumps(
        {"uid": spec["uid"], "sv": spec.get("sv", 1), "did": "golden-device"})


def parse_cookie(line, now):
    parts = [p.strip() for p in line.split(";")]
    name, _, value = parts[0].partition("=")
    attrs = {}
    for part in parts[1:]:
        key, _, val = part.partition("=")
        key = key.lower()
        if key == "expires":
            attrs[key] = "set"
        elif key in ("httponly", "secure"):
            attrs[key] = "true"
        else:
            attrs[key] = val.lower() if key == "samesite" else val
    out = {"name": name, "attrs": attrs, "empty": value in ("", '""')}
    if name == auth.SESSION_COOKIE and not out["empty"]:
        payload = URLSafeTimedSerializer(SECRET, salt="ubyhost-session").loads(value)
        for key in ("iat", "rf", "ast"):
            if key in payload:
                offset = int(round(payload[key] - now))
                # A time written by the request itself is 0, so the file is
                # the same on every run; the Go test allows 2 seconds.
                payload[key] = 0 if abs(offset) <= 5 else offset
        out["payload"] = payload
    if name == auth.DEVICE_COOKIE and not out["empty"]:
        payload = URLSafeTimedSerializer(SECRET, salt="ubyhost-device").loads(value)
        payload["did"] = len(payload["did"])
        out["payload"] = payload
    if name == "ubyhost_lang":
        out["value"] = value
    return out


PENDING = re.compile(r'name="pending" value="([^"]*)"')


def normalize(html):
    html = re.sub(r'(name="_csrf" value=")[^"]*"', r'\1<csrf>"', html)
    html = re.sub(r'(name="csrf-token" content=")[^"]*"', r'\1<csrf>"', html)
    html = PENDING.sub(r'name="pending" value="<pending>"', html)
    html = re.sub(r"(/login/link\?t=)[A-Za-z0-9_-]+", r"\1<token>", html)
    html = re.sub(r"[ \t\n\r\f\v]+", " ", html)
    return html.replace("> <", "><").strip()


CSRF_TOKEN = URLSafeTimedSerializer(SECRET, salt="ubyhost-csrf").dumps({"nonce": security._nonce_binding(NONCE)})


def run(case, seed):
    now = time.time()
    load_seed(seed, case.get("seed", []), now)
    admin_file = TMP / "initial_admin_login"
    admin_file.unlink(missing_ok=True)
    if case.get("admin_file"):
        admin_file.write_text("golden\n", encoding="utf-8")
    restore = apply_env({**ENV, **case.get("env", {})})
    try:
        cookies = []
        token = session_cookie(case.get("session"), now)
        if token:
            cookies.append(f"{auth.SESSION_COOKIE}={token}")
        if case.get("device"):
            cookies.append(f"{auth.DEVICE_COOKIE}={device_cookie(case['device'])}")
        if case.get("csrf", True):
            cookies.append(f"{security.CSRF_COOKIE}={NONCE}")
        if case.get("lang"):
            cookies.append(f"ubyhost_lang={case['lang']}")
        headers = {"cookie": "; ".join(cookies)} if cookies else {}
        headers.update(case.get("headers", {}))
        pairs = [tuple(p) for p in case.get("form", [])]
        if case.get("csrf", True) and case["method"] == "POST":
            pairs.append(("_csrf", CSRF_TOKEN))
        client = TestClient(app, base_url="http://testserver", client=(case.get("client", "testclient"), 50000))
        url = case["path"] + (("?" + case["query"]) if case.get("query") else "")
        with mock.patch.object(turnstile.requests, "post", side_effect=fake_post):
            if case["method"] == "POST":
                headers["content-type"] = "application/x-www-form-urlencoded"
                response = client.post(url, content=urlencode(pairs), headers=headers, follow_redirects=False)
            else:
                response = client.get(url, headers=headers, follow_redirects=False)
        body = None if 300 <= response.status_code < 400 else response.text
        pending = None
        if body:
            found = PENDING.search(body)
            if found:
                pending = auth.read_two_factor_pending(found.group(1))
        want = {
            "status": response.status_code,
            "location": response.headers.get("location"),
            "content_type": response.headers.get("content-type"),
            "cache_control": response.headers.get("cache-control"),
            "referrer_policy": response.headers.get("referrer-policy"),
            "body": normalize(body) if body is not None else None,
            "cookies": [parse_cookie(line, now) for line in response.headers.get_list("set-cookie")],
            "pending": pending,
            "admin_file": admin_file.exists(),
            "db": dump(),
        }
    finally:
        restore()
    case = dict(case)
    case["want"] = want
    return case


def cases():
    P, G = "POST", "GET"
    host = {"uid": 2}
    email = ["email", "host@example.test"]
    good = ["cf-turnstile-response", "good"]
    https = {"UBYHOST_PUBLIC_BASE_URL": "https://ubyhost.test"}
    split = {"UBYHOST_PUBLIC_BASE_URL": "https://www.ubyhost.test", "UBYHOST_APP_BASE_URL": "https://app.ubyhost.test"}
    link = lambda *a, **k: [link_row(*a, **k)]  # noqa: E731
    return [
        # GET /login
        {"name": "login_get", "method": G, "path": "/login"},
        {"name": "login_get_lang_query", "method": G, "path": "/login", "query": "lang=en&next=/reservations%3Fx%3D1&a=b+c"},
        {"name": "login_get_lang_cookie_vi", "method": G, "path": "/login", "lang": "vi", "csrf": False},
        {"name": "login_get_lang_query_same_cookie", "method": G, "path": "/login", "query": "lang=cs&lang=vi", "lang": "vi"},
        {"name": "login_get_notice", "method": G, "path": "/login", "query": "notice=logged_out"},
        {"name": "login_get_signed_in", "method": G, "path": "/login", "session": host},
        {"name": "login_get_signed_in_refresh", "method": G, "path": "/login", "session": {"uid": 2, "rm": 1, "iat": -2 * 86400}},
        {"name": "login_get_turnstile", "method": G, "path": "/login", "env": TURNSTILE},
        {"name": "login_get_turnstile_local", "method": G, "path": "/login",
         "env": {k: v for k, v in TURNSTILE.items() if k != "UBYHOST_DEPLOYMENT"}},
        {"name": "login_get_trusted_device", "method": G, "path": "/login", "env": TURNSTILE, "device": host},
        {"name": "login_get_stale_device", "method": G, "path": "/login", "env": TURNSTILE, "device": {"uid": 2, "sv": 9}},
        {"name": "login_get_passkeys", "method": G, "path": "/login", "env": https, "csrf": False},
        {"name": "login_get_operator", "method": G, "path": "/login", "env": {"UBYHOST_OPERATOR_EMAIL": " ops@example.test ", "UBYHOST_UBYPORT_ENV": "prod"}},
        {"name": "login_get_mock_production", "method": G, "path": "/login", "env": {"UBYHOST_DEPLOYMENT": "production"}},
        {"name": "login_get_staging", "method": G, "path": "/login", "env": STAGING},
        {"name": "login_get_staging_no_password", "method": G, "path": "/login", "env": {"UBYHOST_DEPLOYMENT": "staging"}},
        {"name": "login_get_public_host", "method": G, "path": "/login", "query": "next=/x", "env": split, "headers": {"host": "www.ubyhost.test"}},
        {"name": "login_get_app_host", "method": G, "path": "/login", "env": split, "headers": {"host": "app.ubyhost.test"}},
        # POST /login
        {"name": "post_known", "method": P, "path": "/login", "form": [["email", " Host@Example.test "], ["next", "/reservations?x=1"]]},
        {"name": "post_known_vi", "method": P, "path": "/login", "form": [email], "lang": "vi"},
        {"name": "post_known_query_lang", "method": P, "path": "/login", "query": "lang=en", "form": [email], "lang": "cs"},
        {"name": "post_unknown", "method": P, "path": "/login", "form": [["email", "nobody@example.test"]]},
        {"name": "post_inactive", "method": P, "path": "/login", "form": [["email", "gone@example.test"]]},
        {"name": "post_invalid", "method": P, "path": "/login", "form": [["email", "not an address"], ["next", "//evil.test"]]},
        {"name": "post_empty", "method": P, "path": "/login"},
        {"name": "post_email_limit", "method": P, "path": "/login", "form": [email],
         "seed": rate_rows("login_link_email", "host@example.test", 3)},
        {"name": "post_day_limit", "method": P, "path": "/login", "form": [email],
         "seed": rate_rows("login_link_email_day", "host@example.test", 10)},
        {"name": "post_ip_limit", "method": P, "path": "/login", "form": [["email", "x@example.test"]],
         "seed": rate_rows("login_link_ip", "testclient", 10)},
        {"name": "post_proxy_ip", "method": P, "path": "/login", "form": [email], "client": "10.0.0.5",
         "headers": {"cf-connecting-ip": "203.0.113.9"}, "env": {"UBYHOST_TRUSTED_PROXY_CIDRS": "10.0.0.0/8"}},
        {"name": "post_untrusted_proxy_ip", "method": P, "path": "/login", "form": [email], "client": "10.0.0.5",
         "headers": {"cf-connecting-ip": "203.0.113.9"}},
        {"name": "post_signed_in", "method": P, "path": "/login", "form": [email], "session": {"uid": 3}},
        {"name": "post_no_mail", "method": P, "path": "/login", "form": [email], "env": {"UBYHOST_MAIL_BACKEND": "disabled"}},
        {"name": "post_no_csrf", "method": P, "path": "/login", "form": [email], "csrf": False},
        {"name": "post_turnstile_missing", "method": P, "path": "/login", "form": [email], "env": TURNSTILE},
        {"name": "post_turnstile_bad", "method": P, "path": "/login", "form": [email, ["cf-turnstile-response", "nope"]], "env": TURNSTILE, "device": {"uid": 3}},
        {"name": "post_turnstile_action", "method": P, "path": "/login", "form": [email, ["cf-turnstile-response", "other-action"]], "env": TURNSTILE},
        {"name": "post_turnstile_good", "method": P, "path": "/login", "form": [email, good], "env": TURNSTILE},
        {"name": "post_turnstile_down", "method": P, "path": "/login", "form": [email, ["cf-turnstile-response", "down"]], "env": TURNSTILE},
        {"name": "post_turnstile_down_spent", "method": P, "path": "/login", "form": [email, ["cf-turnstile-response", "down"]], "env": TURNSTILE,
         "seed": rate_rows("turnstile_unreachable", "testclient:host_login", 5)},
        {"name": "post_trusted_device", "method": P, "path": "/login", "form": [email], "env": TURNSTILE, "device": host},
        {"name": "post_trusted_device_other_email", "method": P, "path": "/login", "form": [["email", "totp@example.test"]], "env": TURNSTILE, "device": host},
        {"name": "post_trusted_device_limited", "method": P, "path": "/login", "form": [email], "env": TURNSTILE, "device": host,
         "seed": rate_rows("login_link_email", "host@example.test", 3)},
        {"name": "post_turnstile_invalid_email", "method": P, "path": "/login", "form": [["email", "bad"], good], "env": TURNSTILE},
        {"name": "post_staging_ok", "method": P, "path": "/login", "env": STAGING,
         "form": [["username", "HOST"], ["staging_password", "open sesame"], ["next", "/settings"]]},
        {"name": "post_staging_email", "method": P, "path": "/login", "env": STAGING,
         "form": [["email", "totp@example.test"], ["staging_password", "'open sesame'"]]},
        {"name": "post_staging_first_admin", "method": P, "path": "/login", "env": STAGING,
         "form": [["username", "nobody"], ["staging_password", "open sesame"]]},
        {"name": "post_staging_wrong", "method": P, "path": "/login", "env": STAGING,
         "form": [["username", "host"], ["staging_password", "open sesamE"]]},
        {"name": "post_staging_no_password", "method": P, "path": "/login", "env": STAGING, "form": [email]},
        {"name": "post_staging_without_secret", "method": P, "path": "/login", "env": {"UBYHOST_DEPLOYMENT": "staging"}, "form": [email]},
        # GET /login/link
        {"name": "link_get", "method": G, "path": "/login/link", "query": "t=tok-login", "seed": link("tok-login", 2, "host@example.test")},
        {"name": "link_get_invite", "method": G, "path": "/login/link", "query": "t=tok-invite", "lang": "en",
         "seed": link("tok-invite", 5, "fresh@example.test", purpose="invite")},
        {"name": "link_get_expired", "method": G, "path": "/login/link", "query": "t=tok-old",
         "seed": link("tok-old", 2, "host@example.test", expires=PAST)},
        {"name": "link_get_unknown", "method": G, "path": "/login/link", "query": "t=nothing&lang=vi"},
        {"name": "link_get_no_token", "method": G, "path": "/login/link"},
        {"name": "link_get_changed_email", "method": G, "path": "/login/link", "query": "t=tok-moved",
         "seed": link("tok-moved", 2, "old@example.test")},
        {"name": "link_get_email_change_purpose", "method": G, "path": "/login/link", "query": "t=tok-ec",
         "seed": link("tok-ec", 2, "new@example.test", purpose="email_change")},
        {"name": "link_get_signed_in_same", "method": G, "path": "/login/link", "query": "t=tok-login", "session": host,
         "seed": link("tok-login", 2, "host@example.test")},
        {"name": "link_get_signed_in_spent", "method": G, "path": "/login/link", "query": "t=tok-login", "session": host},
        {"name": "link_get_signed_in_other", "method": G, "path": "/login/link", "query": "t=tok-login", "session": {"uid": 3},
         "seed": link("tok-login", 2, "host@example.test")},
        {"name": "link_get_public_host", "method": G, "path": "/login/link", "query": "t=abc", "env": split, "headers": {"host": "WWW.ubyhost.test:443"}},
        # POST /login/link
        {"name": "link_post", "method": P, "path": "/login/link", "form": [["t", " tok-login "]],
         "seed": link("tok-login", 2, "host@example.test", next_path="/reservations?x=%C3%A1&y=1")},
        {"name": "link_post_no_remember", "method": P, "path": "/login/link", "form": [["t", "tok-login"]], "lang": "en",
         "seed": link("tok-login", 2, "host@example.test", remember=0, next_path=None)},
        {"name": "link_post_query_lang", "method": P, "path": "/login/link", "query": "lang=vi", "form": [["t", "tok-login"]], "lang": "cs",
         "seed": link("tok-login", 2, "host@example.test", next_path="")},
        {"name": "link_post_unverified", "method": P, "path": "/login/link", "form": [["t", "tok-fresh"]],
         "seed": link("tok-fresh", 5, "fresh@example.test", purpose="invite")},
        {"name": "link_post_admin_invite", "method": P, "path": "/login/link", "form": [["t", "tok-admin"]], "admin_file": True,
         "seed": link("tok-admin", 1, "admin@example.test", purpose="invite")},
        {"name": "link_post_admin_login_keeps_file", "method": P, "path": "/login/link", "form": [["t", "tok-admin"]], "admin_file": True,
         "seed": link("tok-admin", 1, "admin@example.test")},
        {"name": "link_post_totp", "method": P, "path": "/login/link", "form": [["t", "tok-totp"]],
         "seed": link("tok-totp", 3, "totp@example.test", next_path="/settings")},
        {"name": "link_post_totp_signed_in_other", "method": P, "path": "/login/link", "form": [["t", "tok-totp"]], "session": host,
         "seed": link("tok-totp", 3, "totp@example.test", remember=0)},
        {"name": "link_post_spent", "method": P, "path": "/login/link", "form": [["t", "tok-used"]],
         "seed": link("tok-used", 2, "host@example.test", used=PAST)},
        {"name": "link_post_expired", "method": P, "path": "/login/link", "form": [["t", "tok-old"]],
         "seed": link("tok-old", 2, "host@example.test", expires=PAST)},
        {"name": "link_post_inactive", "method": P, "path": "/login/link", "form": [["t", "tok-gone"]],
         "seed": link("tok-gone", 4, "gone@example.test")},
        {"name": "link_post_email_change_purpose", "method": P, "path": "/login/link", "form": [["t", "tok-ec"]],
         "seed": link("tok-ec", 2, "new@example.test", purpose="email_change")},
        {"name": "link_post_locked", "method": P, "path": "/login/link", "form": [["t", "tok-login"]],
         "seed": link("tok-login", 2, "host@example.test") + rate_rows("login_link_bad", "testclient", 20)},
        {"name": "link_post_nearly_locked", "method": P, "path": "/login/link", "form": [["t", "nothing"]],
         "seed": rate_rows("login_link_bad", "testclient", 19)},
        {"name": "link_post_no_csrf", "method": P, "path": "/login/link", "form": [["t", "tok-login"]], "csrf": False,
         "seed": link("tok-login", 2, "host@example.test")},
        {"name": "link_post_secure", "method": P, "path": "/login/link", "form": [["t", "tok-login"]], "env": https,
         "seed": link("tok-login", 2, "host@example.test")},
    ]


def main() -> int:
    db.init_db()
    seed = base_seed()
    out = {"secret": SECRET, "nonce": NONCE, "env": ENV, "seed": seed,
           "cases": [run(case, seed) for case in cases()]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")
    catalog = PAGES / "i18n.json"
    catalog.write_text(go_host_i18n.render(go_host_i18n.read_keys(PAGES / "i18n_keys.txt")), encoding="utf-8")
    print(f"wrote {catalog.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
