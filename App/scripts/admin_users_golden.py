"""Records Python's answers to the admin account writes for go/internal/web/auth (brief 1504).

Run from App/: .venv/bin/python scripts/admin_users_golden.py
Writes go/internal/web/auth/testdata/admin_users.json. The cases go through
the real FastAPI app with the seed, request and cookie handling of
auth_routes_golden.py (brief 1282), console mail on, and these tables
watched: audit, user_account, login_token, email_outbox, console_mail_log.
Values a request makes random or time-bound are normalised the same way the
Go test normalises them: a timestamp the request wrote is "<now>", one inside
a longer string is "<ts>", a link key's hash is "<hash>", a generated username ends
in "-<hex>". The Go test admin_users_post_test.go replays each case on
Postgres and compares.
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import auth_routes_golden as g  # noqa: E402  (sets the environment, imports the app)

from app import db  # noqa: E402

OUT = g.PKG / "testdata" / "admin_users.json"
ENV = dict(g.ENV, UBYHOST_MAIL_BACKEND="console")

# Deleted first: the outbox rows point at accounts.
g.TABLES[:0] = ["console_mail_log", "email_outbox"]

WATCH = {
    "audit": "SELECT action, actor, detail, owner_user_id, actor_user_id, impersonator_user_id FROM audit ORDER BY id",
    "user_account": (
        "SELECT id, username, display_name, email, role, active, session_version, email_verified_at, "
        "must_change_password, password_hash FROM user_account ORDER BY id"
    ),
    "login_token": (
        "SELECT user_account_id, purpose, email, remember, next_path, used_at FROM login_token ORDER BY id"
    ),
    "email_outbox": (
        "SELECT id, kind, idempotency_key, owner_user_id, to_email, subject, state, attempts, provider_id, "
        "CASE WHEN payload LIKE '%\"claim_secret_enc\": \"%' THEN 1 ELSE 0 END AS sealed, "
        "CASE WHEN payload LIKE '%{{claim_secret}}%' THEN 1 ELSE 0 END AS marker, "
        "CASE WHEN kind = 'email_changed' THEN payload ELSE '' END AS notice "
        "FROM email_outbox ORDER BY id"
    ),
    "console_mail_log": "SELECT outbox_id, to_email, subject FROM console_mail_log ORDER BY id",
}

WHOLE_STAMP = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00$")
INNER_STAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00")
LINK_HASH = re.compile(r":[0-9a-f]{24}$")
GENERATED = re.compile(r"-[0-9a-f]{4}$")


def norm(value):
    """g.norm, then the in-string rules (kept in step with aupNorm in the Go test)."""
    text = g.norm(value)
    if text is None or text == "<now>" or WHOLE_STAMP.match(text):
        return text
    text = INNER_STAMP.sub("<ts>", text)
    text = LINK_HASH.sub(":<hash>", text)
    return GENERATED.sub("-<hex>", text)


def dump():
    return {name: [[norm(v) for v in tuple(row)] for row in db.query(sql)] for name, sql in WATCH.items()}


g.dump = dump  # g.run reads the module global


def token_row(n, uid, email, used=None):
    return ["login_token", {"token_hash": f"{n:064x}", "user_account_id": uid, "purpose": "invite",
                            "email": email, "remember": 1, "next_path": "/", "created_at": g.OLD,
                            "expires_at": g.FAR, "used_at": used}]


def cases():
    h = {"uid": 2}
    a = {"uid": 1}
    imp = {"uid": 1, "as": 2, "ast": -60}
    origin = {"origin": "http://testserver"}
    no_email = [g.account(6, "noemail", email=None), g.account(7, "blank", email="  ")]
    old_invite = [token_row(1, 2, "host@example.test"), token_row(2, 2, "host@example.test", used=g.OLD)]
    off = {"py_config": {"MAIL_BACKEND": "disabled"}, "env": {"UBYHOST_MAIL_BACKEND": "disabled"}}
    P = "POST"
    c = "/admin/users"
    return [
        {"name": "create", "method": P, "path": c, "session": a,
         "form": [["email", " New.Host@Example.test "], ["display_name", "  New Host "]]},
        {"name": "create_named_address_cs", "method": P, "path": c, "session": a, "lang": "cs",
         "form": [["email", "Jana <jana@example.test>"]]},
        {"name": "create_impersonating", "method": P, "path": c, "session": imp,
         "form": [["email", "third@example.test"]]},
        {"name": "create_mail_off", "method": P, "path": c, "session": a,
         "form": [["email", "quiet@example.test"]], **off},
        {"name": "create_invalid", "method": P, "path": c, "session": a, "form": [["email", "nope"]]},
        {"name": "create_empty_vi", "method": P, "path": c, "session": a, "lang": "vi"},
        {"name": "create_taken", "method": P, "path": c, "session": a, "form": [["email", "HOST@example.test"]]},
        {"name": "create_taken_inactive", "method": P, "path": c, "session": a, "form": [["email", "gone@example.test"]]},
        {"name": "create_host", "method": P, "path": c, "session": h, "form": [["email", "x@example.test"]]},
        {"name": "create_signed_out", "method": P, "path": c, "form": [["email", "x@example.test"]]},
        {"name": "create_no_csrf_same_site", "method": P, "path": c, "session": a, "csrf": False,
         "headers": origin, "form": [["email", "x@example.test"]]},
        {"name": "create_no_csrf_cross_site", "method": P, "path": c, "session": a, "csrf": False,
         "form": [["email", "x@example.test"]]},
        {"name": "invite", "method": P, "path": "/admin/users/2/invite", "session": a, "seed": old_invite},
        {"name": "invite_cs", "method": P, "path": "/admin/users/3/invite", "session": a, "lang": "cs"},
        {"name": "invite_mail_off", "method": P, "path": "/admin/users/4/invite", "session": a, **off},
        {"name": "invite_impersonating", "method": P, "path": "/admin/users/2/invite", "session": imp},
        {"name": "invite_inactive", "method": P, "path": "/admin/users/5/invite", "session": a},
        {"name": "invite_missing", "method": P, "path": "/admin/users/99/invite", "session": a},
        {"name": "invite_no_email", "method": P, "path": "/admin/users/6/invite", "session": a, "seed": no_email},
        {"name": "invite_blank_email_cs", "method": P, "path": "/admin/users/7/invite", "session": a,
         "seed": no_email, "lang": "cs"},
        {"name": "invite_bad_id", "method": P, "path": "/admin/users/x/invite", "session": a},
        {"name": "invite_host", "method": P, "path": "/admin/users/2/invite", "session": h},
        {"name": "invite_signed_out", "method": P, "path": "/admin/users/2/invite"},
        {"name": "email_first", "method": P, "path": "/admin/users/6/email", "session": a, "seed": no_email,
         "form": [["email", " First@Example.test "]]},
        {"name": "email_first_blank", "method": P, "path": "/admin/users/7/email", "session": a, "seed": no_email,
         "form": [["email", "blank@example.test"], ["reason", "x"]]},
        {"name": "email_change", "method": P, "path": "/admin/users/2/email", "session": a, "seed": old_invite,
         "form": [["email", "moved@example.test"], ["reason", "  lost\n her   mailbox "]]},
        {"name": "email_change_cs", "method": P, "path": "/admin/users/3/email", "session": a, "lang": "cs",
         "form": [["email", "Neu <neu@example.test>"], ["reason", "ticket 42"]]},
        {"name": "email_change_inactive", "method": P, "path": "/admin/users/5/email", "session": a,
         "form": [["email", "back@example.test"], ["reason", "reopened"]]},
        {"name": "email_change_mail_off", "method": P, "path": "/admin/users/4/email", "session": a,
         "form": [["email", "later@example.test"], ["reason", "mailbox gone"]], **off},
        {"name": "email_change_impersonating", "method": P, "path": "/admin/users/2/email", "session": imp,
         "form": [["email", "moved@example.test"], ["reason", "support call"]]},
        {"name": "email_own", "method": P, "path": "/admin/users/1/email",
         "session": {"uid": 1, "rm": 1, "iat": -300},
         "form": [["email", "boss@example.test"], ["reason", "new mailbox"]]},
        {"name": "email_own_short_session", "method": P, "path": "/admin/users/1/email",
         "session": {"uid": 1, "iat": -5000}, "form": [["email", "boss@example.test"], ["reason", "new mailbox"]]},
        {"name": "email_own_impersonating", "method": P, "path": "/admin/users/1/email",
         "session": {"uid": 1, "as": 2, "ast": -60, "iat": -400},
         "form": [["email", "boss@example.test"], ["reason", "new mailbox"]]},
        {"name": "email_no_reason", "method": P, "path": "/admin/users/2/email", "session": a,
         "form": [["email", "moved@example.test"]]},
        {"name": "email_short_reason_cs", "method": P, "path": "/admin/users/2/email", "session": a, "lang": "cs",
         "form": [["email", "moved@example.test"], ["reason", " abc "]]},
        {"name": "email_unchanged", "method": P, "path": "/admin/users/2/email", "session": a,
         "form": [["email", "HOST@example.test"]]},
        {"name": "email_invalid", "method": P, "path": "/admin/users/2/email", "session": a,
         "form": [["email", "host@"], ["reason", "a reason"]]},
        {"name": "email_taken", "method": P, "path": "/admin/users/2/email", "session": a,
         "form": [["email", "totp@example.test"], ["reason", "a reason"]]},
        {"name": "email_missing", "method": P, "path": "/admin/users/99/email", "session": a,
         "form": [["email", "x@example.test"]]},
        {"name": "email_bad_id", "method": P, "path": "/admin/users/1.5/email", "session": a},
        {"name": "email_host", "method": P, "path": "/admin/users/2/email", "session": h,
         "form": [["email", "x@example.test"], ["reason", "a reason"]]},
        {"name": "email_signed_out", "method": P, "path": "/admin/users/2/email"},
    ]


def main() -> int:
    db.init_db()
    seed = g.base_seed()
    g.load_seed(seed, [], time.time())
    seed[2][1].update(g.totp_columns())
    out = {"secret": g.SECRET, "nonce": g.NONCE, "env": ENV, "seed": seed, "watch": WATCH,
           "cases": [g.run(case, seed) for case in cases()]}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(g.REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
