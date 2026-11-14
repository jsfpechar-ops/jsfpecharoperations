"""Records Python's answers to the login address change for go/internal/web/auth (brief 1506).

Run from App/: .venv/bin/python scripts/auth_email_golden.py
Writes go/internal/web/auth/testdata/account_email.json with the harness of
auth_account_golden.py (brief 1505): the same seed, the same recording, the
same normalisation. mail.send_now is replaced, so the cases record the
outbox ids the route hands it instead of sending.
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import auth_account_golden as base  # noqa: E402

OUT = base.PKG / "testdata" / "account_email.json"
TOKEN = base.EMAIL_TOKEN


def token_row(uid, email, token=TOKEN, used=None, expires=base.FAR):
    return ["login_token", {"token_hash": hashlib.sha256(token.encode("utf-8")).hexdigest(),
                            "user_account_id": uid, "purpose": "email_change", "email": email,
                            "remember": 0, "next_path": "/", "created_at": base.OLD,
                            "expires_at": expires, "used_at": used}]


def cases():
    h = {"uid": 2}
    stale = {"uid": 2, "iat": -700}
    origin = {"origin": "http://testserver"}
    P, G = "POST", "GET"
    E, C = "/account/email", "/account/email/confirm"
    new = token_row(2, "new@example.test")
    login_token = ["login_token", dict(new[1], purpose="login")]
    bad = [["rate_limit_event", {"scope": "login_link_bad", "key": "testclient", "at": "<now-epoch>"}]] * 20
    email_window = [["rate_limit_event", {"scope": "login_link_email", "key": "new@example.test", "at": "<now-epoch>"}]] * 3
    return [
        {"name": "email_post_signed_out", "method": P, "path": E, "form": [["email", "new@example.test"]]},
        {"name": "email_post_acceptance_pending", "method": P, "path": E, "session": {"uid": 4}, "form": [["email", "new@example.test"]]},
        {"name": "email_post_impersonating", "method": P, "path": E, "session": {"uid": 1, "as": 2, "ast": -60},
         "form": [["email", "new@example.test"]], "lang": "cs"},
        {"name": "email_post_stale", "method": P, "path": E, "session": stale, "form": [["email", "new@example.test"]]},
        {"name": "email_post_invalid", "method": P, "path": E, "session": h, "form": [["email", "not-an-address"]]},
        {"name": "email_post_empty", "method": P, "path": E, "session": h, "lang": "vi"},
        {"name": "email_post_unchanged", "method": P, "path": E, "session": h, "form": [["email", "  HOST@Example.test "]]},
        {"name": "email_post_ok", "method": P, "path": E, "session": h, "form": [["email", " New@Example.TEST "]]},
        {"name": "email_post_ok_cs", "method": P, "path": E, "session": h, "form": [["email", "new@example.test"]], "lang": "cs"},
        {"name": "email_post_ok_named", "method": P, "path": E, "session": h, "form": [["email", "Host Name <new@example.test>"]]},
        {"name": "email_post_taken", "method": P, "path": E, "session": h, "form": [["email", "taken@example.test"]]},
        {"name": "email_post_inactive_owner_free", "method": P, "path": E, "session": h, "form": [["email", "gone@example.test"]]},
        {"name": "email_post_rate_limited", "method": P, "path": E, "session": h, "form": [["email", "new@example.test"]],
         "seed": email_window},
        {"name": "email_post_replaces_old_link", "method": P, "path": E, "session": h, "form": [["email", "other@example.test"]],
         "seed": [new]},
        {"name": "email_post_no_csrf", "method": P, "path": E, "session": h, "csrf": False, "form": [["email", "new@example.test"]]},
        {"name": "confirm_get_ok", "method": G, "path": C, "query": "t=" + TOKEN, "seed": [new]},
        {"name": "confirm_get_ok_signed_in_cs", "method": G, "path": C, "query": "t=x&t=" + TOKEN, "session": h,
         "lang": "cs", "seed": [new]},
        {"name": "confirm_get_query_lang", "method": G, "path": C, "query": "t=" + TOKEN + "&lang=vi", "seed": [new]},
        {"name": "confirm_get_no_token", "method": G, "path": C},
        {"name": "confirm_get_unknown", "method": G, "path": C, "query": "t=nope", "seed": [new]},
        {"name": "confirm_get_used", "method": G, "path": C, "query": "t=" + TOKEN,
         "seed": [token_row(2, "new@example.test", used=base.OLD)]},
        {"name": "confirm_get_expired", "method": G, "path": C, "query": "t=" + TOKEN,
         "seed": [token_row(2, "new@example.test", expires=base.OLD)]},
        {"name": "confirm_get_login_purpose", "method": G, "path": C, "query": "t=" + TOKEN, "seed": [login_token]},
        {"name": "confirm_get_same_address", "method": G, "path": C, "query": "t=" + TOKEN,
         "seed": [token_row(2, "host@example.test")]},
        {"name": "confirm_get_inactive_account", "method": G, "path": C, "query": "t=" + TOKEN,
         "seed": [token_row(10, "new@example.test")]},
        {"name": "confirm_get_no_csrf_cookie", "method": G, "path": C, "query": "t=" + TOKEN, "csrf": False, "seed": [new]},
        {"name": "confirm_post_ok", "method": P, "path": C, "form": [["t", " " + TOKEN + " "]], "seed": [new]},
        {"name": "confirm_post_ok_signed_in", "method": P, "path": C, "form": [["t", TOKEN]], "session": h, "seed": [new]},
        {"name": "confirm_post_bad_token", "method": P, "path": C, "form": [["t", "nope"]], "seed": [new], "lang": "cs"},
        {"name": "confirm_post_no_token", "method": P, "path": C},
        {"name": "confirm_post_blocked", "method": P, "path": C, "form": [["t", TOKEN]], "seed": [new] + bad},
        {"name": "confirm_post_taken", "method": P, "path": C, "form": [["t", TOKEN]],
         "seed": [token_row(2, "taken@example.test")]},
        {"name": "confirm_post_same_address", "method": P, "path": C, "form": [["t", TOKEN]],
         "seed": [token_row(2, "host@example.test")]},
        {"name": "confirm_post_no_csrf", "method": P, "path": C, "csrf": False, "form": [["t", TOKEN]], "seed": [new]},
        {"name": "confirm_post_no_csrf_same_site", "method": P, "path": C, "csrf": False, "headers": origin,
         "form": [["t", TOKEN]], "seed": [new]},
    ]


def main() -> int:
    base.write(OUT, cases(), base.make_seed())
    return 0


if __name__ == "__main__":
    sys.exit(main())
