"""Records Python's answers to POST /login/2fa for go/internal/web/auth (brief 1503).

Run from App/: .venv/bin/python scripts/login_2fa_golden.py
Writes go/internal/web/auth/testdata/login_2fa.json. The cases go through the
real FastAPI app with the seed, request and cookie handling of
auth_routes_golden.py (brief 1282). A case's "pending" is minted here with
auth.issue_two_factor_pending (the Go test mints its own with
session.IssueTwoFactorPending, since the token lives 10 minutes) and sent as
the first form field; "pending_raw" is sent as it is. For a page answer the
recording keeps, instead of the whole page (brief 1502 owns its markup), the
text of the auth-alert box and how many hidden "pending" fields echo the
stripped token. Watched tables: audit, user_account, rate_limit_event.
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import auth_routes_golden as g  # noqa: E402  (sets the environment, imports the app)

from app import auth, db  # noqa: E402

OUT = g.PKG / "testdata" / "login_2fa.json"

WATCH = {
    "audit": "SELECT action, actor, detail, owner_user_id, actor_user_id, impersonator_user_id FROM audit ORDER BY id",
    "user_account": "SELECT id, session_version, last_login_at, recovery_codes_hash FROM user_account ORDER BY id",
    "rate_limit_event": "SELECT scope, key FROM rate_limit_event ORDER BY id",
}

ALERT = re.compile(r'<div class="auth-alert" role="alert">(.*?)</div>', re.S)


def dump():
    return {name: [[g.norm(v) for v in tuple(row)] for row in db.query(sql)] for name, sql in WATCH.items()}


g.dump = dump  # g.run reads the module global


def page(body, token):
    """What a page answer is compared on: the alert box and the echoed token."""
    found = ALERT.search(body)
    return {"alert": found.group(1) if found else None,
            "pending_fields": body.count(f'<input type="hidden" name="pending" value="{token}">')}


def run(case, seed):
    spec = case.get("pending")
    if spec is not None:
        token = auth.issue_two_factor_pending(spec["uid"], remember=spec.get("rm", False),
                                              next_path=spec.get("next", "/"))
        sent = (" " + token + " ") if spec.get("pad") else token
    else:
        token = sent = case.get("pending_raw", "")
    form = case.get("form", [])
    pairs = ([["pending", sent]] if (spec is not None or "pending_raw" in case) else []) + form
    out = g.run(dict(case, form=pairs), seed)
    out["form"] = form
    want = out["want"]
    if not 300 <= want["status"] < 400 and (want["content_type"] or "").startswith("text/html"):
        out["page"] = page(want["body"], token.strip())
        want["body"] = None
    return out


def rows(scope, key, n):
    return [["rate_limit_event", {"scope": scope, "key": key, "at": "<now-epoch>"}]] * n


def cases(seed):
    P = "POST"
    # Account 8 has account 3's authenticator with RECOVERY[0] already spent.
    three = seed[2][1]
    spent = [g.account(8, "spent", email="spent@example.test", totp_enabled=1,
                       totp_secret_enc=three["totp_secret_enc"],
                       recovery_codes_hash=json.dumps([auth.recovery_code_hash(g.RECOVERY[1])]))]
    path = "/login/2fa"
    t = {"uid": 3, "rm": True, "next": "/reservations?view=list"}
    good = [["code", g.RECOVERY[0]]]
    origin = {"origin": "http://testserver"}
    return [
        {"name": "no_pending", "method": P, "path": path},
        {"name": "garbage_pending", "method": P, "path": path, "pending_raw": "not-a-token", "form": good},
        {"name": "other_salt_pending", "method": P, "path": path, "form": good,
         "pending_raw": g.session_cookie({"uid": 3}, time.time())},
        {"name": "inactive_account", "method": P, "path": path, "pending": {"uid": 5}, "form": good},
        {"name": "missing_account", "method": P, "path": path, "pending": {"uid": 99}, "form": good},
        {"name": "ok_recovery_remember", "method": P, "path": path, "pending": t,
         "form": [["code", " aaaa-1111 "]]},
        {"name": "ok_not_remembered_cs", "method": P, "path": path, "lang": "cs",
         "pending": {"uid": 3, "next": ""}, "form": [["code", g.RECOVERY[1]]]},
        {"name": "ok_lang_query_vi", "method": P, "path": path, "query": "lang=vi",
         "pending": {"uid": 3, "next": "//evil.example/x"}, "form": good},
        {"name": "ok_padded_pending_en", "method": P, "path": path, "lang": "en",
         "pending": {"uid": 3, "pad": True, "next": "/settings#security"}, "form": good},
        {"name": "bad_code", "method": P, "path": path, "pending": t, "form": [["code", "000000"]]},
        {"name": "bad_code_cs_padded", "method": P, "path": path, "lang": "cs",
         "pending": dict(t, pad=True), "form": [["code", "12 34 56"]]},
        {"name": "no_code_no_totp", "method": P, "path": path, "pending": {"uid": 2}},
        {"name": "recovery_code_spent", "method": P, "path": path, "pending": {"uid": 8}, "form": good,
         "seed": spent},
        {"name": "recovery_code_left", "method": P, "path": path, "pending": {"uid": 8}, "form": [["code", g.RECOVERY[1]]],
         "seed": spent},
        {"name": "locked_account", "method": P, "path": path, "pending": t, "form": good,
         "seed": rows("2fa_fail_account", "3", 10)},
        {"name": "locked_account_vi", "method": P, "path": path, "lang": "vi", "pending": t, "form": good,
         "seed": rows("2fa_fail_account", "3", 10)},
        {"name": "nearly_locked_account", "method": P, "path": path, "pending": t, "form": [["code", "1"]],
         "seed": rows("2fa_fail_account", "3", 9)},
        {"name": "locked_login", "method": P, "path": path, "pending": t, "form": good,
         "seed": rows("login_fail", "testclient:totp:2fa", 12)},
        {"name": "nearly_locked_login", "method": P, "path": path, "pending": t, "form": [["code", "1"]],
         "seed": rows("login_fail", "testclient:totp:2fa", 11)},
        {"name": "locked_ip", "method": P, "path": path, "pending": t, "form": good,
         "seed": rows("login_fail_ip", "testclient", 30)},
        {"name": "other_ip_not_locked", "method": P, "path": path, "pending": t, "form": good,
         "seed": rows("login_fail_ip", "192.0.2.9", 30) + rows("login_fail", "testclient:host:2fa", 12)},
        {"name": "old_failures_pruned", "method": P, "path": path, "pending": t, "form": good,
         "seed": [["rate_limit_event", {"scope": "2fa_fail_account", "key": "3", "at": 1.0}]] * 10},
        {"name": "no_csrf_same_site", "method": P, "path": path, "pending": t, "form": good, "csrf": False,
         "headers": origin},
        {"name": "no_csrf_from_account_page", "method": P, "path": path, "pending": t, "form": good, "csrf": False,
         "headers": dict(origin, referer="http://testserver/account")},
    ]


def main() -> int:
    db.init_db()
    seed = g.base_seed()
    g.load_seed(seed, [], time.time())
    seed[2][1].update(g.totp_columns())
    recorded = [run(case, seed) for case in cases(seed)]
    out = {"secret": g.SECRET, "nonce": g.NONCE, "env": g.ENV, "seed": seed, "watch": WATCH, "cases": recorded}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(g.REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
