"""Records Python's answers to the account setup pages for go/internal/web/auth (brief 1505).

Run from App/: .venv/bin/python scripts/auth_account_golden.py
Writes go/internal/web/auth/testdata/account_setup.json and the package's
acct_i18n.json (from acct_i18n_keys.txt). Every case starts from the same
seed rows on a fresh SQLite database and goes through the real FastAPI app,
as App/scripts/auth_routes_golden.py does. Recorded per case: status, the
headers that matter, the page (whitespace folded, the CSRF token, QR image,
fresh TOTP secret and recovery codes replaced by markers), every Set-Cookie
(attributes, and a session cookie's payload with its times as offsets), the
mail ids handed to mail.send_now, and the rows of the watched tables, with
the times the request wrote shown as "<now>". The Go test replays each case
on Postgres and compares. Brief 1506's auth_email_golden.py imports run()
and SEED from here.
"""
import json
import logging
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode

APP_DIR = Path(__file__).resolve().parents[1]
REPO = APP_DIR.parent
PKG = REPO / "go" / "internal" / "web" / "auth"
OUT = PKG / "testdata" / "account_setup.json"
SECRET = "auth-account-golden-secret-0123456789-abcdef"
NONCE = "golden-account-csrf-nonce"
TMP = Path(tempfile.mkdtemp(prefix="auth-account-golden-"))
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
            "UBYHOST_PUBLIC_BASE_URL", "UBYHOST_APP_BASE_URL", "UBYHOST_OPERATOR_EMAIL"):
    os.environ.pop(key, None)
sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(APP_DIR / "scripts"))

import pyotp  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from itsdangerous import URLSafeTimedSerializer  # noqa: E402

from app import acceptance, auth, db, mail, security  # noqa: E402
from app.main import app  # noqa: E402
import go_host_i18n  # noqa: E402

OLD = "2001-01-01T00:00:00+00:00"
FAR = "2099-01-01T00:00:00+00:00"
STAMP = re.compile(r"^\d{4}-\d\d-\d\dT")
STAGED = "JBSWY3DPEHPK3PXP"
EMAIL_TOKEN = "golden-email-change-token-0123456789"
SENT = []


def _no_send(outbox_id, *args, **kwargs):
    """mail.send_now runs as a background task; the case records the id instead."""
    SENT.append(outbox_id)


mail.send_now = _no_send
logging.disable(logging.WARNING)


def account(uid, username, role="host", active=1, email=None, **extra):
    row = {
        "id": uid, "username": username, "password_hash": "", "role": role, "active": active,
        "must_change_password": 0, "session_version": 1, "created_at": OLD, "email": email,
    }
    row.update(extra)
    return ["user_account", row]


def base_seed():
    seed = [
        account(1, "admin", "admin", email="admin@example.test"),
        account(2, "host", email="host@example.test", email_verified_at="2001-01-02T03:04:05+00:00"),
        account(3, "totp", email="totp@example.test"),
        account(4, "late", email="late@example.test"),
        account(5, "partial", email="partial@example.test"),
        account(6, "staged", email="staged@example.test"),
        account(7, "taken", email="taken@example.test"),
        account(8, "badkey", email="badkey@example.test", totp_secret_enc="not-a-fernet-token"),
        account(9, "admin2", "admin", email="admin2@example.test"),
        account(10, "gone", active=0, email="gone@example.test"),
    ]
    versions = acceptance.current_versions()
    n = 0
    for uid in (1, 2, 3, 6, 7, 8, 10):
        for doc in ("terms", "privacy", "dpa"):
            n += 1
            seed.append(["legal_acceptance", {"id": n, "user_account_id": uid, "document": doc,
                                              "version": versions[doc], "accepted_at": OLD, "method": "clickwrap"}])
    seed.append(["legal_acceptance", {"id": n + 1, "user_account_id": 5, "document": "terms",
                                      "version": versions["terms"], "accepted_at": OLD, "method": "clickwrap"}])
    seed.append(["legal_acceptance", {"id": n + 2, "user_account_id": 5, "document": "privacy",
                                      "version": "0.1", "accepted_at": OLD, "method": "clickwrap"}])
    return seed


def secret_columns():
    """Accounts 3 (on) and 6 (staged) get their secrets through Python's own helpers.

    Fernet's IV and time are fixed while they do, so the seed (and the file)
    is the same on every run; the Go side decrypts these Python tokens.
    """
    from cryptography.fernet import Fernet

    real = Fernet.encrypt_at_time
    Fernet.encrypt_at_time = lambda self, data, current_time: self._encrypt_from_parts(data, 1700000000, b"\x00" * 16)
    try:
        auth.enable_totp(3, STAGED, ["AAAA-1111", "BBBB-2222"])
        auth.stage_totp(6, STAGED)
    finally:
        Fernet.encrypt_at_time = real
    rows = {r["id"]: r for r in db.query(
        "SELECT id, totp_secret_enc, recovery_codes_hash, session_version FROM user_account WHERE id IN (3, 6)")}
    return {
        3: {"totp_enabled": 1, "totp_secret_enc": rows[3]["totp_secret_enc"],
            "recovery_codes_hash": rows[3]["recovery_codes_hash"]},
        6: {"totp_enabled": 0, "totp_secret_enc": rows[6]["totp_secret_enc"]},
    }


TABLES = ["email_outbox", "rate_limit_event", "audit", "login_token", "legal_acceptance", "user_account"]

WATCH = {
    "audit": "SELECT action, actor, detail, owner_user_id, actor_user_id, impersonator_user_id FROM audit ORDER BY id",
    "user_account": (
        "SELECT id, email, email_verified_at, session_version, totp_enabled, "
        "CASE WHEN totp_secret_enc IS NULL THEN 0 ELSE 1 END AS has_secret, "
        "CASE WHEN recovery_codes_hash IS NULL THEN 0 ELSE 1 END AS has_codes FROM user_account ORDER BY id"
    ),
    "legal_acceptance": (
        "SELECT user_account_id, document, version, accepted_at, method, ip, user_agent "
        "FROM legal_acceptance ORDER BY id"
    ),
    "rate_limit_event": "SELECT scope, key FROM rate_limit_event ORDER BY id",
    "login_token": (
        "SELECT user_account_id, purpose, email, remember, next_path, created_at, expires_at, used_at "
        "FROM login_token ORDER BY id"
    ),
    "email_outbox": (
        "SELECT idempotency_key, kind, owner_user_id, to_email, subject, state, payload "
        "FROM email_outbox ORDER BY id"
    ),
}

# scrub: the parts of a value that change from run to run (also in the Go test).
SCRUB = [
    (re.compile(r'"claim_secret_enc": "[^"]*"'), '"claim_secret_enc": "<enc>"'),
    (re.compile(r":[0-9a-f]{24}$"), ":<h>"),
]
ANY_STAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(\+00:00|Z)?")


def _stamp(match):
    text = match.group(0)
    return text if text.startswith(("2001-", "2099-")) else "<now>"


def norm(value):
    if value is None:
        return None
    text = str(value)
    if STAMP.match(text) and not text.startswith(("2001-", "2099-")):
        return "<now>"
    for pattern, repl in SCRUB:
        text = pattern.sub(repl, text)
    return ANY_STAMP.sub(_stamp, text)


def dump():
    return {name: [[norm(v) for v in tuple(row)] for row in db.query(sql)] for name, sql in WATCH.items()}


# page: the same steps as the Go test's normalizePage.
PAGE = [
    (re.compile(r'<meta name="csrf-token" content="[^"]*">'), '<meta name="csrf-token" content="<csrf>">'),
    (re.compile(r'name="_csrf" value="[^"]*"'), 'name="_csrf" value="<csrf>"'),
    (re.compile(r"data:image/png;base64,[A-Za-z0-9+/=]+"), "<qr>"),
    (re.compile(r"<code>[0-9A-F]{4}-[0-9A-F]{4}</code>"), "<code>R</code>"),
]
FRESH = [
    (re.compile(r"secret=[A-Z2-7]{32}&amp;"), "secret=<s>&amp;"),
    (re.compile(r'<code id="totp-setup-key">[A-Z2-7 ]{39}</code>'), '<code id="totp-setup-key"><s></code>'),
]


def page(text, fresh):
    for pattern, repl in PAGE + (FRESH if fresh else []):
        text = pattern.sub(repl, text)
    return re.sub(r"\s+", " ", text).replace("> <", "><").strip()


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


def session_cookie(spec, now):
    if not spec:
        return ""
    return auth.issue_session(
        spec["uid"], spec.get("sv", 1),
        workspace_user_id=spec.get("as"),
        remember=bool(spec.get("rm")),
        impersonation_started_at=int(now + spec["ast"]) if "ast" in spec else None,
        issued_at=int(now + spec.get("iat", -60)),
    )


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
                payload[key] = int(round(payload[key] - now))
        out["payload"] = payload
    return out


CSRF_TOKEN = URLSafeTimedSerializer(SECRET, salt="ubyhost-csrf").dumps({"nonce": security._nonce_binding(NONCE)})


def form_pairs(case):
    pairs = []
    for key, value in case.get("form", []):
        if value == "<totp>":
            value = pyotp.TOTP(STAGED).now()
        elif value == "<totp-spaced>":
            code = pyotp.TOTP(STAGED).now()
            value = f" {code[:3]} {code[3:]} "
        pairs.append((key, value))
    return pairs


def run(case, seed):
    now = time.time()
    load_seed(seed, case.get("seed", []), now)
    SENT.clear()
    cookies = []
    token = session_cookie(case.get("session"), now)
    if token:
        cookies.append(f"{auth.SESSION_COOKIE}={token}")
    if case.get("csrf", True):
        cookies.append(f"{security.CSRF_COOKIE}={NONCE}")
    if case.get("lang"):
        cookies.append(f"ubyhost_lang={case['lang']}")
    headers = {"cookie": "; ".join(cookies)} if cookies else {}
    headers.update(case.get("headers", {}))
    pairs = form_pairs(case)
    if case.get("csrf", True) and case["method"] == "POST":
        pairs.append(("_csrf", CSRF_TOKEN))
    client = TestClient(app, base_url="http://testserver")
    url = case["path"] + (("?" + case["query"]) if case.get("query") else "")
    if case["method"] == "POST":
        headers["content-type"] = "application/x-www-form-urlencoded"
        response = client.post(url, content=urlencode(pairs), headers=headers, follow_redirects=False)
    else:
        response = client.get(url, headers=headers, follow_redirects=False)
    html = response.headers.get("content-type", "").startswith("text/html")
    body = None
    if not 300 <= response.status_code < 400:
        body = page(response.text, case.get("fresh", False)) if html else response.text
    want = {
        "status": response.status_code,
        "location": response.headers.get("location"),
        "content_type": response.headers.get("content-type"),
        "cache_control": response.headers.get("cache-control"),
        "referrer_policy": response.headers.get("referrer-policy"),
        "body": body,
        "cookies": sorted((parse_cookie(line, now) for line in response.headers.get_list("set-cookie")),
                          key=lambda c: c["name"]),
        "sent": list(SENT),
        "db": dump(),
    }
    case = dict(case)
    case["want"] = want
    return case


def make_seed():
    db.init_db()
    seed = base_seed()
    load_seed(seed, [], time.time())
    columns = secret_columns()
    for item in seed:
        if item[0] == "user_account" and item[1]["id"] in columns:
            item[1].update(columns[item[1]["id"]])
    return seed


def cases():
    h = {"uid": 2}
    late = {"uid": 4}
    staged = {"uid": 6}
    stale = {"uid": 6, "iat": -700}
    origin = {"origin": "http://testserver"}
    P, G = "POST", "GET"
    A, S = "/account/accept", "/account/2fa/setup"
    return [
        {"name": "accept_get_signed_out", "method": G, "path": A, "query": "next=/calendar"},
        {"name": "accept_get_nothing_pending", "method": G, "path": A, "session": h, "query": "next=/calendar?x=1&y=%C3%A1"},
        {"name": "accept_get_nothing_pending_no_next", "method": G, "path": A, "session": h},
        {"name": "accept_get_unsafe_next", "method": G, "path": A, "session": h, "query": "next=//evil.example/x"},
        {"name": "accept_get_pending", "method": G, "path": A, "session": late, "query": "next=/calendar&next=/apartments"},
        {"name": "accept_get_pending_cs", "method": G, "path": A, "session": {"uid": 5}, "lang": "cs"},
        {"name": "accept_get_pending_query_lang", "method": G, "path": A, "session": late, "query": "lang=vi", "lang": "en"},
        {"name": "accept_get_pending_no_csrf_cookie", "method": G, "path": A, "session": late, "csrf": False},
        {"name": "accept_get_stale_version", "method": G, "path": A, "session": {"uid": 4, "sv": 9}},
        {"name": "accept_get_inactive", "method": G, "path": A, "session": {"uid": 10}},
        {"name": "accept_get_impersonating", "method": G, "path": A, "session": {"uid": 9, "as": 2, "ast": -60}},
        {"name": "accept_post_signed_out", "method": P, "path": A, "form": [["accept", "1"]]},
        {"name": "accept_post_no_box", "method": P, "path": A, "session": late, "form": [["next", "/calendar"]]},
        {"name": "accept_post_box_not_one", "method": P, "path": A, "session": late, "form": [["accept", "on"]], "lang": "vi"},
        {"name": "accept_post_ok", "method": P, "path": A, "session": late,
         "form": [["accept", " 1 "], ["next", " /calendar?a=1 "]],
         "headers": {"user-agent": "GoldenBrowser/1.0 " + "x" * 400}},
        {"name": "accept_post_partial", "method": P, "path": A, "session": {"uid": 5}, "form": [["accept", "1"]]},
        {"name": "accept_post_nothing_pending", "method": P, "path": A, "session": h, "form": [["next", "/x y"]]},
        {"name": "accept_post_unsafe_next", "method": P, "path": A, "session": late,
         "form": [["accept", "1"], ["next", "https://evil.example/"]]},
        {"name": "accept_post_impersonating_admin", "method": P, "path": A, "session": {"uid": 9, "as": 2, "ast": -60},
         "form": [["accept", "1"], ["next", "/"]]},
        {"name": "accept_post_no_csrf", "method": P, "path": A, "session": late, "csrf": False, "form": [["accept", "1"]]},
        {"name": "accept_post_no_csrf_same_site", "method": P, "path": A, "session": late, "csrf": False,
         "headers": origin, "form": [["accept", "1"]]},
        {"name": "setup_get_signed_out", "method": G, "path": S},
        {"name": "setup_get_enabled", "method": G, "path": S, "session": {"uid": 3}, "lang": "cs"},
        {"name": "setup_get_stale", "method": G, "path": S, "session": stale},
        {"name": "setup_get_staged", "method": G, "path": S, "session": staged},
        {"name": "setup_get_moved_cs", "method": G, "path": S, "session": staged, "query": "moved=1", "lang": "cs"},
        {"name": "setup_get_new_secret", "method": G, "path": S, "session": h, "fresh": True},
        {"name": "setup_get_bad_key", "method": G, "path": S, "session": {"uid": 8}, "fresh": True, "lang": "vi"},
        {"name": "setup_get_acceptance_pending", "method": G, "path": S, "session": late, "fresh": True},
        {"name": "setup_post_signed_out", "method": P, "path": S, "form": [["code", "123456"]]},
        {"name": "setup_post_enabled", "method": P, "path": S, "session": {"uid": 3}, "form": [["code", "123456"]]},
        {"name": "setup_post_stale", "method": P, "path": S, "session": stale, "form": [["code", "<totp>"]], "lang": "vi"},
        {"name": "setup_post_bad_code", "method": P, "path": S, "session": staged, "form": [["code", "12345"]]},
        {"name": "setup_post_no_secret", "method": P, "path": S, "session": h, "form": [["code", "123456"]], "lang": "cs"},
        {"name": "setup_post_ok", "method": P, "path": S, "session": {"uid": 6, "iat": -120}, "form": [["code", "<totp>"]]},
        {"name": "setup_post_ok_remember_spaced", "method": P, "path": S, "session": {"uid": 6, "rm": 1, "iat": -300},
         "form": [["code", "<totp-spaced>"]], "lang": "vi"},
        {"name": "setup_post_no_csrf", "method": P, "path": S, "session": staged, "csrf": False, "form": [["code", "<totp>"]]},
    ]


def write_catalog():
    catalog = PKG / "acct_i18n.json"
    catalog.write_text(go_host_i18n.render(go_host_i18n.read_keys(PKG / "acct_i18n_keys.txt")), encoding="utf-8")
    print(f"wrote {catalog.relative_to(REPO)}")


def write(out, case_list, seed):
    payload = {"secret": SECRET, "nonce": NONCE, "env": ENV, "staged": STAGED, "seed": seed,
               "cases": [run(case, seed) for case in case_list]}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(REPO)}")


def main() -> int:
    write(OUT, cases(), make_seed())
    write_catalog()
    return 0


if __name__ == "__main__":
    sys.exit(main())
