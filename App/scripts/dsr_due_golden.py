"""Write go/internal/calendar/testdata/dsr_due_golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/dsr_due_golden.py

It seeds a throwaway SQLite database with the fixed rows in SEED, runs
dsr.raise_due_alerts once per entry in RUNS, and records the return value and
every alert row after each run. go/internal/calendar/dsr_due_test.go seeds
PostgreSQL from the same file, runs calendar.RaiseDSRDueAlerts and compares.
App/tests/test_dsr_due_golden.py fails when this file is stale.

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
from datetime import date
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "calendar" / "testdata" / "dsr_due_golden.json"

SEED_CREATED = "2026-09-01T00:00:00+00:00"
SEED_RESOLVED = "2026-09-02T00:00:00+00:00"
STAMP = "2026-09-01T00:00:00+00:00"


def _dsr(did, owner, due, status="open"):
    return [did, owner, STAMP, due, "email", "access", "guest", status, STAMP, STAMP]


def _alert(aid, key, owner, *, resolved=None, dismissed=0):
    return [aid, "info", "dsr_due", None, None, owner, key, "seeded", "seeded", None,
            SEED_CREATED, resolved, dismissed]


# Run 1 is 2026-09-17 (horizon 2026-09-22), run 2 is 2026-09-25 (horizon
# 2026-09-30). The comment on each request says what run 1 must do with it.
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
        "table": "data_subject_request",
        "columns": ["id", "owner_user_id", "received_at", "due_at", "channel",
                    "request_type", "subject_kind", "status", "created_at", "updated_at"],
        "rows": [
            # 1 open, inside the horizon, open card seeded: refreshed.
            _dsr(1, 1, "2026-09-20T09:00:00+00:00"),
            # 2 extended, due exactly on the horizon day: raised.
            _dsr(2, 2, "2026-09-22T10:00:00+00:00", "extended"),
            # 3 overdue, a resolved card is seeded: a new card is inserted.
            _dsr(3, 1, "2026-09-10T08:00:00+00:00"),
            # 4 no owner, plain date: raised with a NULL owner.
            _dsr(4, None, "2026-09-18"),
            # 5 +02:00 offset is 2026-09-22 in UTC, so on the horizon; a
            # dismissed card is seeded: a new card is inserted.
            _dsr(5, 2, "2026-09-23T00:30:00+02:00"),
            # 6 one day past the horizon: skipped in run 1, raised in run 2.
            _dsr(6, 1, "2026-09-23T00:00:00+00:00"),
            # 7 fulfilled: skipped, its seeded open card is never resolved.
            _dsr(7, 1, "2026-09-18T09:00:00+00:00", "fulfilled"),
            # 8 refused and 9 withdrawn: skipped.
            _dsr(8, 2, "2026-09-18T09:00:00+00:00", "refused"),
            _dsr(9, 2, "2026-09-18T09:00:00+00:00", "withdrawn"),
            # 10 far away: skipped in both runs.
            _dsr(10, 2, "2026-10-15T09:00:00+00:00"),
        ],
    },
    {
        "table": "alert",
        "columns": ["id", "level", "kind", "apartment_id", "reservation_id",
                    "owner_user_id", "dedupe_key", "message", "detail", "params",
                    "created_at", "resolved_at", "user_dismissed"],
        "rows": [
            _alert(9001, "dsr_due:1", 1),
            _alert(9002, "dsr_due:3", 1, resolved=SEED_RESOLVED),
            _alert(9003, "dsr_due:5", 2, resolved=SEED_RESOLVED, dismissed=1),
            _alert(9004, "dsr_due:7", 1),
        ],
    },
]

RUNS = ["2026-09-17", "2026-09-25"]


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
    """Seed a fresh database, run the job, and return the golden JSON text."""
    from app import db, dsr

    db.init_db()
    _seed(db)
    seed_ids = {row[0] for table in SEED if table["table"] == "alert" for row in table["rows"]}
    runs = []
    for today in RUNS:
        raised = dsr.raise_due_alerts(date.fromisoformat(today))
        runs.append({"today": today, "raised": raised, "alerts": _alerts(db, seed_ids)})
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
    os.environ.setdefault("UBYHOST_DB", str(tmp / "dsr_due_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    main()
