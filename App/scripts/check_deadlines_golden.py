"""Write go/internal/calendar/testdata/check_deadlines_golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/check_deadlines_golden.py

It seeds a throwaway SQLite database with the fixed rows in SEED, runs
reporting.check_deadlines once per entry in RUNS, and records the return value
and every alert row after each run. go/internal/calendar/watch_test.go seeds
PostgreSQL from the same file, runs calendar.CheckDeadlines and compares.
App/tests/test_check_deadlines_golden.py fails when this file is stale.

Timestamps the run writes are not comparable, so an alert row records only
whether created_at and resolved_at are still the seeded values ("seed"), were
written by a run ("run"), or resolved_at is empty ("open"). "seed" is the alert
id when the row was seeded, else null.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "calendar" / "testdata" / "check_deadlines_golden.json"

SEED_CREATED = "2026-09-01T00:00:00+00:00"
SEED_RESOLVED = "2026-09-02T00:00:00+00:00"
STAMP = "2026-09-01T00:00:00+00:00"
BAD_TOKEN = "not-a-token"

_GUEST_COLUMNS = [
    "id", "reservation_id", "surname", "first_name", "birth_date", "nationality",
    "res_country", "res_street", "res_city", "doc_number", "doc_number_enc",
    "fee_host_reason_enc", "purpose", "signature_png", "identity_verified_at",
    "submit_state", "submitted_at", "stay_from", "stay_to", "is_lead",
    "archived_at", "created_at", "updated_at",
]


def _guest(gid, rid, nationality="DEU", *, complete=True, surname="Mustermann",
           state="pending", submitted=None, stay_from=None, stay_to=None,
           doc_enc=None, fee_enc=None, archived=None):
    """One guest row; complete=False leaves everything but the surname empty."""
    if complete:
        values = ["Erika", "02011990", nationality, nationality, "Hlavni 1", "Brno",
                  "C01X00T47", doc_enc, fee_enc, "10", "imported", "2026-09-01T08:00:00Z"]
    else:
        values = [None, None, nationality, None, None, None, None, doc_enc, fee_enc,
                  None, None, None]
    return [gid, rid, surname, *values, state, submitted, stay_from, stay_to, 1,
            archived, STAMP, STAMP]


def _stay(rid, apt, date_from, date_to, *, status="active", source="host",
          declared=None, override=None, reduced=None, archived=None):
    return [rid, apt, f"u{rid}", date_from, date_to, status, source, declared,
            override, reduced, archived, STAMP, STAMP]


def _alert(aid, level, kind, apt, rid, owner, key, *, resolved=None, dismissed=0,
           message="seeded", detail="seeded"):
    return [aid, level, kind, apt, rid, owner, key, message, detail, None,
            SEED_CREATED, resolved, dismissed]


# Run 1 is 2026-09-17 12:00 in Prague (a Thursday), owner 1 only. The comment
# on each stay says what run 1 must do with it.
SEED = [
    {
        "table": "user_account",
        "columns": ["id", "username", "password_hash", "role", "created_at"],
        "rows": [
            [1, "owner@example.test", "x", "host", STAMP],
            [2, "other@example.test", "x", "host", STAMP],
        ],
    },
    {
        "table": "apartment",
        "columns": ["id", "owner_user_id", "internal_name", "city_en", "uby_name",
                    "permalink_token", "active", "created_at"],
        "rows": [
            [1, 1, "Byt Dole", "Brno", "UBY", "tok1", 1, STAMP],
            [2, 1, "Byt Vypnuty", "Brno", "UBY", "tok2", 0, STAMP],
            [3, 2, "Cizi byt", "Brno", "UBY", "tok3", 1, STAMP],
        ],
    },
    {
        "table": "reservation",
        "columns": ["id", "apartment_id", "uid", "date_from", "date_to", "status",
                    "source", "declared_guests", "expected_guests_override",
                    "lead_reduced_guests", "archived_at", "created_at", "updated_at"],
        "rows": [
            _stay(101, 1, "2026-09-10", "2026-09-14", declared=2),  # overdue 1/2 + shortfall
            _stay(102, 1, "2026-09-15", "2026-09-18"),  # urgent, expected unknown "?"
            _stay(103, 1, "2026-09-10", "2026-09-12", declared=1),  # reported: resolves
            _stay(104, 1, "2026-09-11", "2026-09-13", declared=1),  # not_required: resolves
            _stay(105, 1, "2026-09-10", "2026-09-12", status="cancelled", declared=1),
            _stay(106, 1, "2026-09-10", "2026-09-12", declared=1, archived="2026-09-13"),
            _stay(107, 1, "2026-09-10", "2026-09-12", source="demo", declared=1),
            _stay(108, 2, "2026-09-10", "2026-09-12", declared=1),  # inactive apartment
            _stay(109, 1, "2026-09-16", "2026-09-20", declared=1),  # guest arrived 09-11
            _stay(110, 1, "2026-09-17", "2026-09-21", declared=2),  # starts today
            _stay(111, 1, "2026-09-20", "2026-09-22", declared=2),  # not started
            _stay(112, 1, "2026-09-16", "2026-09-18", declared=2),  # soon 1/2
            _stay(113, 1, "2026-09-15", "2026-09-17", declared=1),  # doc unreadable
            _stay(114, 1, "unknown", "unknown", declared=1),  # no anchor: skipped
            _stay(115, 3, "2026-09-10", "2026-09-12", declared=1),  # owner 2
            _stay(116, 3, "2026-09-10", "2026-09-12", status="cancelled", declared=1),
            _stay(117, 1, "2026-09-09", "2026-09-11", declared=1),  # dismissed before
            _stay(118, 1, "bad", "2026-09-20", declared=1),  # no check-in date
            _stay(119, 1, "2026-09-15", "2026-09-17", declared=1),  # fee reason unreadable
            _stay(120, 1, "2026-09-10", "2026-09-12", declared=3, reduced=1),
        ],
    },
    {
        "table": "guest",
        "columns": _GUEST_COLUMNS,
        "rows": [
            _guest(1, 101),
            _guest(2, 101, complete=False, surname="Gone", stay_from="2026-09-01",
                   archived="2026-09-12"),
            _guest(3, 103, state="sent", submitted="2026-09-11T10:00:00+00:00"),
            _guest(4, 104, "CZE"),
            _guest(5, 109, complete=False, surname="Early", stay_from="2026-09-11",
                   stay_to="2026-09-20"),
            _guest(6, 112),
            _guest(7, 113, doc_enc=BAD_TOKEN),
            _guest(8, 114, doc_enc=BAD_TOKEN),
            _guest(9, 118, complete=False, surname="Bad", stay_from="2026-09-10"),
            _guest(10, 119, fee_enc=BAD_TOKEN),
            _guest(11, 120),
        ],
    },
    {
        "table": "alert",
        "columns": ["id", "level", "kind", "apartment_id", "reservation_id",
                    "owner_user_id", "dedupe_key", "message", "detail", "params",
                    "created_at", "resolved_at", "user_dismissed"],
        "rows": [
            _alert(9001, "critical", "deadline", 1, 103, 1, "deadline:103"),
            _alert(9002, "warning", "headcount_mismatch", 1, 103, 1, "headcount_mismatch:103"),
            _alert(9003, "critical", "deadline", 1, 104, 1, "deadline:104"),
            _alert(9004, "critical", "deadline", 1, 105, 1, "deadline:105"),
            _alert(9005, "warning", "guest_incomplete_checkin", 1, 105, 1,
                   "guest_incomplete_checkin:105"),
            _alert(9006, "warning", "feed_incomplete", 1, 105, 1, "feed_incomplete:105"),
            _alert(9007, "warning", "headcount_mismatch", 1, 106, 1, "headcount_mismatch:106"),
            _alert(9008, "warning", "headcount_mismatch", 1, 110, 1, "headcount_mismatch:110"),
            _alert(9009, "warning", "deadline", 1, 112, 1, "deadline:112"),
            _alert(9010, "critical", "deadline", 3, 116, 2, "deadline:116"),
            _alert(9011, "critical", "deadline", 1, 117, 1, "deadline:117",
                   resolved=SEED_RESOLVED, dismissed=1),
            _alert(9012, "critical", "deadline", 1, 101, 1, "deadline:101",
                   resolved=SEED_RESOLVED),
            _alert(9013, "info", "deadline", 1, 102, 1, "deadline:102", message="old",
                   detail="old"),
            _alert(9014, "critical", "deadline", 2, 108, 1, "deadline:108"),
            _alert(9015, "warning", "headcount_mismatch", 3, 116, 2, "headcount_mismatch:116",
                   dismissed=1),
            _alert(9016, "warning", "headcount_mismatch", 1, 104, 1, "headcount_mismatch:104",
                   dismissed=1),
        ],
    },
]

# (instant, owner_user_id). Run 2 repeats run 1 for every owner; run 3 is
# Monday 2026-09-21 14:00 in Prague.
RUNS = [
    ("2026-09-17T10:00:00+00:00", 1),
    ("2026-09-17T10:00:00+00:00", None),
    ("2026-09-21T12:00:00+00:00", None),
]


def _seed(db) -> None:
    for table in SEED:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        for row in table["rows"]:
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", row)


def _alerts(db, seed_ids) -> list:
    out = []
    for row in db.query(
        "SELECT id, level, kind, apartment_id, reservation_id, owner_user_id, dedupe_key, "
        "message, detail, params, created_at, resolved_at, user_dismissed FROM alert"
    ):
        if row["resolved_at"] is None:
            resolved = "open"
        elif row["resolved_at"] == SEED_RESOLVED:
            resolved = "seed"
        else:
            resolved = "run"
        out.append({
            "seed": row["id"] if row["id"] in seed_ids else None,
            "level": row["level"],
            "kind": row["kind"],
            "apartment_id": row["apartment_id"],
            "reservation_id": row["reservation_id"],
            "owner_user_id": row["owner_user_id"],
            "dedupe_key": row["dedupe_key"],
            "message": row["message"],
            "detail": row["detail"],
            "params": row["params"],
            "created": "seed" if row["created_at"] == SEED_CREATED else "run",
            "resolved": resolved,
            "user_dismissed": int(row["user_dismissed"]),
        })
    out.sort(key=lambda a: json.dumps(a, sort_keys=True, ensure_ascii=False))
    return out


def render() -> str:
    """Seed a fresh database, run the watch, and return the golden JSON text."""
    from app import db, reporting

    db.init_db()
    _seed(db)
    seed_ids = {row[0] for table in SEED if table["table"] == "alert" for row in table["rows"]}
    runs = []
    for at, owner in RUNS:
        raised = reporting.check_deadlines(datetime.fromisoformat(at), owner_user_id=owner)
        runs.append({
            "at": at,
            "owner_user_id": owner,
            "raised": raised,
            "alerts": _alerts(db, seed_ids),
        })
    golden = {
        "seed_created": SEED_CREATED,
        "seed_resolved": SEED_RESOLVED,
        "seed": SEED,
        "runs": runs,
    }
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "check_deadlines_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    main()
