"""Writes golden host-session tokens for go/internal/session (brief 0672).

Run from App/: .venv/bin/python scripts/session_golden.py
The tokens are issued by app.auth.issue_session with a frozen itsdangerous
timestamp, so the Go tests can reproduce them byte for byte.
"""
import json
import os
import sys
from pathlib import Path
from unittest import mock

APP_DIR = Path(__file__).resolve().parents[1]
REPO = APP_DIR.parent
SECRET = "session-golden-secret-0123456789-abcdefg"
TIMESTAMP = 1798761600
OUT = REPO / "go" / "internal" / "session" / "testdata" / "tokens.json"

assert len(SECRET) == 40
os.environ["UBYHOST_SECRET_KEY"] = SECRET
sys.path.insert(0, str(APP_DIR))

from itsdangerous.timed import TimestampSigner  # noqa: E402

from app import auth  # noqa: E402

# name, expected payload (Python dict order), issue_session arguments
CASES = [
    (
        "plain",
        {"uid": 7, "sv": 3, "iat": TIMESTAMP},
        dict(user_id=7, session_version=3, issued_at=TIMESTAMP),
    ),
    (
        "remember",
        {"uid": 7, "sv": 3, "iat": TIMESTAMP, "rm": 1},
        dict(user_id=7, session_version=3, remember=True, issued_at=TIMESTAMP),
    ),
    (
        "impersonating",
        {"uid": 1, "sv": 2, "iat": TIMESTAMP - 60, "as": 9, "ast": TIMESTAMP - 3600, "rv": [4, 5]},
        dict(
            user_id=1,
            session_version=2,
            workspace_user_id=9,
            impersonation_started_at=TIMESTAMP - 3600,
            revealed_guest_ids=[4, 5],
            issued_at=TIMESTAMP - 60,
        ),
    ),
    (
        "reveal_list",
        {"uid": 1, "sv": 2, "iat": TIMESTAMP - 120, "rm": 1, "as": 9, "ast": TIMESTAMP - 60, "rv": [11, 3, 8]},
        dict(
            user_id=1,
            session_version=2,
            workspace_user_id=9,
            remember=True,
            impersonation_started_at=TIMESTAMP - 60,
            revealed_guest_ids=[11, 3, 11, 8],
            issued_at=TIMESTAMP - 120,
        ),
    ),
    (
        "compressed",
        {
            "uid": 1,
            "sv": 2,
            "iat": TIMESTAMP - 120,
            "rm": 1,
            "as": 9,
            "ast": TIMESTAMP - 60,
            "rv": list(range(1000, 1050)),
        },
        dict(
            user_id=1,
            session_version=2,
            workspace_user_id=9,
            remember=True,
            impersonation_started_at=TIMESTAMP - 60,
            revealed_guest_ids=list(range(1000, 1050)),
            issued_at=TIMESTAMP - 120,
        ),
    ),
]

out_cases = []
with mock.patch.object(TimestampSigner, "get_timestamp", return_value=TIMESTAMP):
    for name, expected, kwargs in CASES:
        token = auth.issue_session(**kwargs)
        decoded = auth._serializer().loads(token)
        assert decoded == expected, (name, decoded)
        if name == "compressed":
            assert token.startswith("."), "compressed case is not compressed"
        out_cases.append({"name": name, "payload": expected, "token": token})

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(
    json.dumps({"secret": SECRET, "timestamp": TIMESTAMP, "cases": out_cases}, indent=1) + "\n",
    encoding="utf-8",
)
print(f"wrote {len(out_cases)} cases to {OUT.relative_to(REPO)}")
