"""Writes golden auth values for go/internal/session (brief 1280).

Run from App/: .venv/bin/python scripts/auth_golden.py
Everything is produced by app.auth with a frozen clock and fixed random
values, so the Go tests can reproduce it byte for byte.
"""
import json
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

APP_DIR = Path(__file__).resolve().parents[1]
REPO = APP_DIR.parent
SECRET = "auth-golden-secret-0123456789-abcdefghij"
NOW = 1798761600
OUT = REPO / "go" / "internal" / "session" / "testdata" / "auth.json"

os.environ["UBYHOST_SECRET_KEY"] = SECRET
sys.path.insert(0, str(APP_DIR))

from starlette.responses import Response  # noqa: E402

from app import auth, db  # noqa: E402

DAY = 24 * 3600
out = {"secret": SECRET, "now": NOW}


def clock(at):
    return mock.patch("time.time", return_value=float(at))


def set_cookie(fn, *args):
    response = Response()
    fn(response, *args)
    return [v for k, v in response.raw_headers if k == b"set-cookie"][0].decode()


# Session tokens, all issued at NOW (so "rf" is NOW).
sessions = [
    ("plain", dict(user_id=7, session_version=3)),
    ("remember", dict(user_id=7, session_version=3, remember=True, issued_at=NOW - 60)),
    ("same_workspace", dict(user_id=7, session_version=3, workspace_user_id=7)),
    ("impersonating", dict(user_id=1, session_version=2, workspace_user_id=9,
                           revealed_guest_ids=[11, 3, 11, 8], issued_at=NOW - 120)),
    ("impersonating_ast", dict(user_id=1, session_version=2, workspace_user_id=9, remember=True,
                               impersonation_started_at=NOW - 3600, issued_at=NOW - 120)),
    ("compressed", dict(user_id=1, session_version=2, workspace_user_id=9, remember=True,
                        impersonation_started_at=NOW - 60, revealed_guest_ids=list(range(1000, 1060)),
                        issued_at=NOW - 120)),
]
out["sessions"] = []
with clock(NOW):
    for name, kwargs in sessions:
        out["sessions"].append({"name": name, "args": kwargs, "token": auth.issue_session(**kwargs)})

# _session_payload acceptance: token signed at sign_at, read at read_at.
reads = [
    ("plain_fresh", {}, 0, 12 * 3600),
    ("plain_old", {}, 0, 12 * 3600 + 1),
    ("remember_29d", {"remember": True}, 0, 29 * DAY),
    ("remember_31d", {"remember": True}, 0, 31 * DAY),
    ("remember_absolute_ok", {"remember": True, "issued_at": NOW - 80 * DAY}, 0, 10 * DAY),
    ("remember_absolute_over", {"remember": True, "issued_at": NOW - 80 * DAY}, 0, 10 * DAY + 1),
]
out["reads"] = []
for name, extra, sign_off, read_off in reads:
    with clock(NOW + sign_off):
        token = auth.issue_session(5, 1, **extra)
    with clock(NOW + read_off):
        payload = auth._session_payload(token)
    out["reads"].append({"name": name, "token": token, "at": NOW + read_off, "ok": payload is not None})

# refresh_session_cookie on loaded payloads, at NOW.
refreshes = [
    ("not_remember", {"uid": 5, "sv": 1, "iat": NOW - 2 * DAY, "rf": NOW - 2 * DAY}),
    ("recent", {"uid": 5, "sv": 1, "iat": NOW - 2 * DAY, "rf": NOW - DAY + 1, "rm": 1}),
    ("due", {"uid": 5, "sv": 1, "iat": NOW - 2 * DAY, "rf": NOW - DAY, "rm": 1}),
    ("due_no_rf", {"uid": 5, "sv": 1, "iat": NOW - 2 * DAY, "rm": 1}),
    ("due_impersonating", {"uid": 1, "sv": 4, "iat": NOW - 3 * DAY, "rf": NOW - 2 * DAY, "rm": 1,
                           "as": 9, "ast": NOW - 2 * DAY, "rv": [4, 5]}),
]
out["refreshes"] = []
with clock(NOW), mock.patch.object(auth, "secure_cookies", return_value=True):
    for name, payload in refreshes:
        request = SimpleNamespace(state=SimpleNamespace(session_payload=payload))
        response = Response()
        auth.refresh_session_cookie(request, response)
        cookies = [v.decode() for k, v in response.raw_headers if k == b"set-cookie"]
        out["refreshes"].append({"name": name, "payload": payload, "cookie": cookies[0] if cookies else ""})

# Cookie headers.
with clock(NOW):
    out["cookies"] = {}
    for secure in (False, True):
        with mock.patch.object(auth, "secure_cookies", return_value=secure):
            s = "secure" if secure else "plain"
            out["cookies"]["session_" + s] = set_cookie(auth.attach_session, "TOKEN")
            out["cookies"]["session_remember_" + s] = set_cookie(auth.attach_session, "TOKEN", True)
            out["cookies"]["clear_" + s] = set_cookie(auth.clear_session)
            with mock.patch.object(auth.secrets, "token_urlsafe", return_value="DEVICEID0123456789abcd"):
                out["cookies"]["device_" + s] = set_cookie(
                    auth.attach_device, {"id": 7, "session_version": 3})

# Two-factor pending tokens.
out["pending"] = []
with clock(NOW):
    for uid, rm, nxt in [(7, False, "/"), (7, True, "/settings?x=<a>&b=\"c\""), (8, False, "/příjezdy/\U0001F600\x7f\t \x00")]:
        out["pending"].append({"uid": uid, "rm": rm, "next": nxt,
                               "token": auth.issue_two_factor_pending(uid, rm, nxt)})

# TOTP codes and URIs.
secrets_ = ["JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP", "jbswy3dpehpk3pxp", "GEZDGNBVGY3TQOJQGEZDGNBVGY"]
steps = [0, 1, 59958720, 59958721, 99999999]
out["totp"] = []
for s in secrets_:
    import pyotp
    totp = pyotp.TOTP(s)
    out["totp"].append({"secret": s, "codes": {str(st): totp.at(st * totp.interval) for st in steps}})
out["uris"] = [{"secret": s, "username": u, "uri": auth.totp_uri(s, u)}
               for s, u in [(secrets_[0], "anna-1a2b"), (secrets_[2], "a b/c:d@é+%&=?#")]]
out["recovery"] = {"codes": ["ABCD-1234", "beef 0042", "x-y-z"],
                   "json": json.dumps([auth.recovery_code_hash(c) for c in ["ABCD-1234", "beef 0042", "x-y-z"]])}

# Usernames.
names = ["  Anna.B ", "ab", "abc", "-abc", "a" * 32, "a" * 33, "Ab_c-d.e", "école", "x y z"]
out["usernames"] = [{"in": n, "norm": auth.normalise_username(n), "valid": auth.username_is_valid(n)} for n in names]
emails = ["Anna.Novak@example.com", "--__..x@y", "@x", "", "éé@x", "a" * 30 + "@x", "a+b@x"]
out["new_usernames"] = []
with mock.patch.object(auth.secrets, "token_hex", return_value="abcd"), \
        mock.patch.object(auth.db, "query_one", return_value=None):
    for e in emails:
        out["new_usernames"].append({"email": e, "username": auth.new_username(e)})

# Whitespace, JSON strings (ensure_ascii=False, as itsdangerous), timestamps, the admin 403.
out["whitespace"] = [c for c in range(0x110000) if re.match(r"\s", chr(c))]
out["json_string"] = {"in": "a\"b\\c\n\r\t\b\f\x01\x1f\x7f/<>&é \U0001F600",
                      "out": json.dumps("a\"b\\c\n\r\t\b\f\x01\x1f\x7f/<>&é \U0001F600", ensure_ascii=False)}
with mock.patch("app.db.datetime") as fake:
    from datetime import datetime, timezone
    fake.now.return_value = datetime.fromtimestamp(NOW + 0.75, tz=timezone.utc)
    out["utcnow"] = db.utcnow()
forbidden = Response("Administrators only.", status_code=403)
out["forbidden"] = {"status": forbidden.status_code, "body": forbidden.body.decode(),
                    "headers": [[k.decode(), v.decode()] for k, v in forbidden.raw_headers]}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {OUT.relative_to(REPO)}")
