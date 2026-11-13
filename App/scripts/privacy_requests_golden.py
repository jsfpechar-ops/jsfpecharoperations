"""Write go/internal/web/privacy/testdata/privacy_requests_golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/privacy_requests_golden.py

It seeds a throwaway SQLite database with SEED, mounts the real
routes/privacy_requests.py router on a bare FastAPI app and posts each entry of
STEPS through it. The clock is fixed at NOW, so every timestamp a step writes
is NOW. Sign-in and CSRF are not what this file pins: the CSRF dependency is
switched off and require_login is replaced by one that sets the step's actor
the way the real one does. After each step it records the status, Location
and body of the answer and every data_subject_request, audit and alert row.
It also records dsr.one_month_later for each ONE_MONTH input ("error" when it
raises) and the ids dsr.list_for_owner returns for owners 1, 2 and None at the
end. go/internal/web/privacy/handler_test.go seeds PostgreSQL from the same
file, signs in for real, posts the same bodies and compares.
App/tests/test_go_privacy_requests.py fails when this file is stale.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "privacy" / "testdata" / "privacy_requests_golden.json"

NOW = "2026-11-13T09:30:00+00:00"
STAMP = "2026-09-01T00:00:00+00:00"
FORM = "application/x-www-form-urlencoded"

SEED = [
    {
        "table": "user_account",
        "columns": ["id", "username", "password_hash", "role", "active", "session_version", "created_at"],
        "rows": [
            [1, "owner@example.test", "x", "host", 1, 1, STAMP],
            [2, "other@example.test", "x", "host", 1, 1, STAMP],
            [3, "admin@example.test", "x", "admin", 1, 1, STAMP],
        ],
    },
    {
        "table": "legal_acceptance",
        "columns": ["id", "user_account_id", "document", "version", "accepted_at", "method"],
        "rows": [
            [101, 1, "terms", "t1", STAMP, "clickwrap"],
            [102, 1, "privacy", "p1", STAMP, "clickwrap"],
            [103, 1, "dpa", "d1", STAMP, "clickwrap"],
            [104, 3, "terms", "t1", STAMP, "clickwrap"],
            [105, 3, "privacy", "p1", STAMP, "clickwrap"],
            [106, 3, "dpa", "d1", STAMP, "clickwrap"],
        ],
    },
    {
        "table": "apartment",
        "columns": ["id", "owner_user_id", "internal_name", "created_at"],
        "rows": [[1, 1, "Byt A", STAMP]],
    },
    {
        "table": "reservation",
        "columns": ["id", "apartment_id", "source", "uid", "date_from", "date_to",
                    "status", "created_at", "updated_at"],
        "rows": [[1, 1, "manual", "r1", "2026-10-01", "2026-10-03", "active", STAMP, STAMP]],
    },
    {
        "table": "guest",
        "columns": ["id", "reservation_id", "created_at", "updated_at"],
        "rows": [[7, 1, STAMP, STAMP]],
    },
    {
        "table": "data_subject_request",
        "columns": ["id", "owner_user_id", "received_at", "due_at", "channel",
                    "request_type", "subject_kind", "status", "created_at", "updated_at"],
        "rows": [
            [49, None, STAMP, "2026-10-01T00:00:00+00:00", "other", "other", "other", "fulfilled", STAMP, STAMP],
            [50, 2, STAMP, "2026-10-01T00:00:00+00:00", "email", "access", "guest", "open", STAMP, STAMP],
            [51, 1, STAMP, "2026-10-01T00:00:00+00:00", "post", "erasure", "guest", "open", STAMP, STAMP],
        ],
    },
    {
        "table": "alert",
        "columns": ["id", "level", "kind", "owner_user_id", "dedupe_key", "message",
                    "created_at", "user_dismissed"],
        "rows": [
            [9001, "info", "dsr_due", 1, "dsr_due:51", "seeded", STAMP, 0],
            [9002, "info", "dsr_due", 2, "dsr_due:50", "seeded", STAMP, 0],
        ],
    },
]

OWNER = {"account": 1, "workspace": 1}
ADMIN_AS_OWNER = {"account": 3, "workspace": 1}

# Each step: name, actor, language cookie ("" for none), path, raw form body.
# Created requests get ids 52, 53, ... in order.
STEPS = [
    ["create_date_only", OWNER, "",
     "/privacy-requests", "channel=email&request_type=access&subject_kind=guest&received_at=2026-01-31&guest_id="],
    ["create_bad_channel", OWNER, "",
     "/privacy-requests", "channel=fax&request_type=access&subject_kind=guest"],
    ["create_bad_subject_cs", OWNER, "cs",
     "/privacy-requests", "channel=email&request_type=access&subject_kind=robot"],
    ["create_received_empty_is_now", OWNER, "",
     "/privacy-requests", "channel=post&request_type=erasure&subject_kind=host_user&received_at="],
    ["create_guest_digits_offset_passthrough", OWNER, "",
     "/privacy-requests", "channel=in_person&request_type=objection&subject_kind=guest&guest_id=+7+&received_at=2026-03-31T23%3A15%3A00%2B02%3A00"],
    ["create_guest_not_digits_space_separator", OWNER, "",
     "/privacy-requests", "channel=support&request_type=portability&subject_kind=other&guest_id=12a&received_at=2026-12-31+08%3A00"],
    ["create_received_invalid_500", OWNER, "",
     "/privacy-requests", "channel=email&request_type=access&subject_kind=guest&received_at=31.01.2026"],
    ["create_last_value_wins_cs_fraction", OWNER, "cs",
     "/privacy-requests", "channel=fax&channel=other&request_type=rectification&subject_kind=guest&received_at=2026-05-31T10%3A00%3A00.5Z"],
    ["create_impersonating", ADMIN_AS_OWNER, "",
     "/privacy-requests", "channel=email&request_type=restriction&subject_kind=guest&received_at=2024-01-31"],
    ["update_closed_resolves_alert", OWNER, "",
     "/privacy-requests/51", "status=fulfilled"],
    ["update_note_identity_unknown_status", OWNER, "",
     "/privacy-requests/52", "status=pending&outcome_note=+Sent+the+export+&identity_checked=on"],
    ["update_extended_keeps_alert", OWNER, "",
     "/privacy-requests/52", "status=extended&outcome_note="],
    ["update_nothing_still_audits", OWNER, "",
     "/privacy-requests/52", "status=bogus"],
    ["update_other_owner", OWNER, "",
     "/privacy-requests/50", "status=fulfilled"],
    ["update_missing_cs", OWNER, "cs",
     "/privacy-requests/999", "status=fulfilled"],
    ["update_path_int_forms", OWNER, "",
     "/privacy-requests/+5_2.00", "status=refused"],
    ["update_path_not_int_422", OWNER, "",
     "/privacy-requests/abc", "status=refused"],
    ["update_impersonating_withdrawn", ADMIN_AS_OWNER, "",
     "/privacy-requests/53", "status=withdrawn&outcome_note=Asked+to+stop"],
    # Last on purpose: on Postgres the refused INSERT still uses up an id,
    # on SQLite it does not, so no step may create a request after this one.
    ["create_guest_missing_row_500", OWNER, "",
     "/privacy-requests", "channel=email&request_type=access&subject_kind=guest&guest_id=999&received_at=2026-01-01"],
]

ONE_MONTH = [
    "2026-01-31", "2024-01-31", "2026-12-31", "2026-02-28", "2026-03-31T23:15:00+02:00",
    "2026-01-31T00:00:00+00:00", "2026-01-31T10:00", "2026-01-31T10", "2026-01-31 10:00:00Z",
    "2026-12-31T23:59:59.5+02:00", "2026-01-31T10:00:00,5", "2026-01-31T10:00:00.1234567",
    "2026-01-31T10:00:00.000000", "2026-01-31T10:00:00-00:00", "2026-01-31T10:00:00-05:30",
    "2026-01-31T10:00:00+05:30:15", "2026-01-31T10:00:00.123+05:30:15.25", "2026-01-31T10:00+01",
    "9999-11-30", "9999-12-01", "0000-01-01", "2026-13-01", "2026-02-30", "2026-01-31T24:00",
    "2026-01-31T23:59:60", "2026-01-31T10:00:00+24:00", "31.01.2026", "garbage", "",
]


def _seed(db) -> None:
    for table in SEED:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        for row in table["rows"]:
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", row)


def _rows(db, sql: str) -> list:
    return [dict(row) for row in db.query(sql)]


def _state(db) -> dict:
    return {
        "data_subject_request": _rows(db, "SELECT * FROM data_subject_request ORDER BY id"),
        "audit": _rows(db, "SELECT at, actor, action, detail, owner_user_id, actor_user_id, "
                           "impersonator_user_id FROM audit ORDER BY id"),
        "alert": _rows(db, "SELECT id, dedupe_key, resolved_at FROM alert ORDER BY id"),
    }


def _one_month(dsr) -> list:
    out = []
    for value in ONE_MONTH:
        try:
            due = dsr.one_month_later(value)
        except ValueError:
            due = "error"
        out.append([value, due])
    return out


def render() -> str:
    """Seed a fresh database, post every step, and return the golden JSON text."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app import access, auth, db, dsr, security
    from app.routes import privacy_requests

    db.init_db()
    _seed(db)
    current = {}

    def fake_login(request):
        account, workspace = current["account"], current["workspace"]
        username = db.query_one("SELECT username FROM user_account WHERE id = ?", (account,))[0]
        db.set_current_actor(account, username, impersonating=account != workspace)
        db.set_current_owner(workspace)
        return None

    saved = (db.utcnow, auth.require_login, access.owner_id)
    db.utcnow = lambda: NOW
    auth.require_login = fake_login
    access.owner_id = lambda request: current["workspace"]
    try:
        app = FastAPI()
        app.include_router(privacy_requests.router)
        app.dependency_overrides[security.protect_host_post] = lambda: None
        client = TestClient(app, raise_server_exceptions=False)
        steps = []
        for name, actor, lang, path, body in STEPS:
            current.update(actor)
            headers = {"Content-Type": FORM}
            if lang:
                headers["Cookie"] = f"ubyhost_lang={lang}"
            response = client.request(
                "POST", path, content=body.encode("utf-8"), headers=headers, follow_redirects=False
            )
            steps.append({
                "name": name,
                "account": actor["account"],
                "workspace": actor["workspace"],
                "lang": lang,
                "path": path,
                "body": body,
                "status": response.status_code,
                "location": response.headers.get("location", ""),
                "response": "" if response.status_code == 303 else response.text,
                "state": _state(db),
            })
    finally:
        db.utcnow, auth.require_login, access.owner_id = saved
    listed = {
        str(owner): [row["id"] for row in dsr.list_for_owner(owner)] for owner in (1, 2, None)
    }
    golden = {
        "list_for_owner": listed,
        "now": NOW,
        "seed": SEED,
        "steps": steps,
        "one_month_later": _one_month(dsr),
    }
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "privacy_requests_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    main()
