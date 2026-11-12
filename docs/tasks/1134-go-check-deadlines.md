# 1134: Go port of `reporting.check_deadlines` (the deadline watch), parity-checked against Python

Status: todo
Depends on: 1132, 1133 (merged, PR #934) | Base commit: ab35038 | Branch: claude/go-check-deadlines-1134
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add `calendar.CheckDeadlines`, a Go port of `reporting.check_deadlines` (App/app/reporting.py 2614-2736) that raises and resolves the `deadline`, `headcount_mismatch` and `guest_record_unreadable` alerts exactly as Python does, and a golden file written by the real Python over fixed stays so the two cannot drift. Nothing calls the Go function yet (no job kind, no env switch, no route): that is brief 1132 §10 E. This is GO-DL step B; it adds files only and changes no existing code, so there is no failing-first step.

## 2. Context

Rules that apply (AGENTS.md): 1 filing correctness (**`reporting.check_deadlines` is the reference; Go must produce the same alert rows and the same return value for the same database, byte for byte**); 2 no new personal-data field (none: the fixture names are the specimen "Erika Mustermann"); 3 no guest data in the repo; 4 no new dependency (Go imports only stdlib, pgx and repo packages already in `go.mod`); 5 Postgres-portable SQL (the Go SQL is plain PostgreSQL through `pgxpool`, as every Go package does; the Python script uses `db.execute`/`db.query` with `?` and only names trusted constant tables and columns).

**Package: `go/internal/calendar`.** The port of `reservation_progress` (`progress`), `reservation_deadline_anchor` (`anchorDate`), `expected_guest_count` and the decrypting guest loader (`loadGuests`, `fieldReader`) are unexported in this package and already parity-tested by the live calendar route. A new package would have to duplicate them or change live files. `calendar` already imports `ubyport`, `deadlines` and `validation`, so there is no import cycle, and `go/internal/deadlines` stays a stdlib-only leaf (untouched). Alerts go through the existing `ubyport.RaiseAlert` / `ubyport.ResolveAlert` (go/internal/ubyport/effects.go 85-153, the port of `alerts.raise_alert` / `alerts.resolve`: dedupe on the open key, refresh level/message/detail/params/created_at, owner looked up from the apartment, a 23505 race refreshes the winner; a resolved or dismissed card is never reopened, a new row is inserted). Times are `ubyport.UTCNow()` (`db.utcnow` form).

**What Python does, and how the Go copies it** (each point is in the Go code below and in the golden file):

- Bulk clear first: `UPDATE alert SET resolved_at = now, user_dismissed = 0` for open alerts of kinds `deadline`, `headcount_mismatch`, `guest_incomplete_checkin` whose stay is not `active` or is archived, all owners when `owner` is nil, else only that owner's apartments.
- Stays: `r.status = 'active' AND r.archived_at IS NULL AND a.active = 1 AND COALESCE(r.source, '') != 'demo'`, owner filter the same way. Python has no ORDER BY; Go adds `ORDER BY r.id` (order changes nothing: each key belongs to one stay).
- Per stay, in this order: anchor from the earliest live guest `stay_from`, else `date_from` (a query that reads only `stay_from`, so it never decrypts); no anchor → skip, **even if a guest is unreadable**. Then the guest read; Python's `SELECT *` decrypts every `_enc` column including `fee_host_reason_enc`, which `loadGuests` does not read, so `watchGuests` decrypts that column too, as a check. A token that will not decrypt (`secure.ErrInvalidToken`, Go's `db.DecryptionError`) → log, raise `critical` `guest_record_unreadable` with key `guest_record_unreadable:reservation:<id>`, params `{"property": "<name>"}`, and the exact Python strings, then next stay. Any other error (database, data keys not configured) aborts the run, as in Python.
- Title `<internal_name> · <dd.mm.yyyy> – <dd.mm.yyyy>` (U+00B7 middle dot, U+2013 en dash); an unparsable `date_from` leaves `"<name> ·  – <to>"`, an unparsable `date_to` drops the en dash part.
- `headcount_mismatch` (`warning`, detail `Waiting for guest forms · <filled>/<expected>`) when not settled, expected known, filled < expected and anchor < today's Prague date; else resolve that key. Settled (`reported` or `not_required`) → resolve `deadline:<id>`, next stay.
- `deadlines.Urgency(anchor, now)`: `overdue` → `critical`, detail `<countdown> · <filled>/<expected>` with `DescribeTimeLeft`'s leading "overdue" capitalised to "Overdue"; `urgent` → `warning`, `Due now · <filled>/<expected>`; expected unknown is `?`. Any other level resolves `deadline:<id>`. The return value counts raised `deadline` alerts only.
- Clock: `now` is `deadlines.LocalNow(at)` (not the calendar's second-truncated `localNow`, because Python does not truncate). Validation's `today` is the UTC date of `at`, as the calendar route passes it (Python reads `date.today()`; birth-date century and future-date checks only).

**Parity mechanism** (same pattern as 1132's `deadlines_golden.py`): `App/scripts/check_deadlines_golden.py` seeds a throwaway SQLite database with fixed users, apartments, 20 stays, 11 guests and 16 alerts, runs the real `reporting.check_deadlines` three times (2026-09-17 12:00 Prague for owner 1; the same instant for every owner; Monday 2026-09-21 14:00 for every owner) and writes `go/internal/calendar/testdata/check_deadlines_golden.json`: the seed rows and, per run, the return value and every alert row (seeded id or null, level, kind, ids, key, message, detail, params, user_dismissed, and whether created_at/resolved_at are the seeded value, written by the run, or empty). `watch_test.go` inserts the same seed into a fresh PostgreSQL (`dbPool`, skips without `UBYHOST_TEST_DATABASE_URL`; CI's Go job sets it), runs `CheckDeadlines` per run and compares. `App/tests/test_check_deadlines_golden.py` regenerates in memory and fails when the committed file is stale; CI runs it on SQLite and on PostgreSQL. Cases covered: overdue in days and in hours, urgent, `?` expected, reported and not_required resolving (and `alerts.resolve` keeping `user_dismissed`), cancelled and archived bulk clear (other kinds and inactive-apartment alerts left open, `user_dismissed` reset), owner-scoped run leaving owner 2 alone, demo skipped, inactive apartment skipped, archived guest ignored, early guest arrival anchor, shortfall before start / on the start day / after start, lead reduction, unreadable `doc_number_enc` and `fee_host_reason_enc`, unreadable guest on a stay with no anchor skipped, unparsable `date_from` title, refresh of an open card, re-raise after resolve and after dismiss.

**Verified by the brief writer** on a scratch copy of ab35038: the files below, generated golden sha256 `b48506b79d2d241835368495b1818cde4133e14c65be1718ea7cf6de52c4f422` (2365 lines; generation is deterministic), `gofmt -l` empty, `go vet ./...` clean, `go test ./internal/calendar/` ok **with a local PostgreSQL 16** (DB test ran, not skipped), the Python test green on SQLite and on PostgreSQL, and three deliberate mutations of `watch.go` (no `user_dismissed = 0`, no params, `<=` for the start-day rule) each made the Go test fail.

Anchors that must exist verbatim (step 0): `func anchorDate(stay stayRow, guests []guestRow) (time.Time, bool) {` and `func progress(stay stayRow, guests []guestRow, today time.Time) progressResult {` in go/internal/calendar/progress.go; `func loadGuests(ctx context.Context, pool *pgxpool.Pool, ids []int64, fields *fieldReader) (map[int64][]guestRow, error) {` in handler.go; `func dbPool(t *testing.T) *pgxpool.Pool {` and `func dbGetenv(k string) string {` in handler_test.go; `func RaiseAlert(` and `func ResolveAlert(` in go/internal/ubyport/effects.go; `func UTCNow() string {` in go/internal/ubyport/store.go; `var ErrInvalidToken` in go/internal/secure/fernet.go; `def check_deadlines(` in App/app/reporting.py.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/check_deadlines_golden.py` | create | seeds fixed rows, runs the real `check_deadlines`, writes the golden file |
| `go/internal/calendar/testdata/check_deadlines_golden.json` | create (generated by the script) | seed + expected alert rows per run |
| `go/internal/calendar/watch.go` | create | `CheckDeadlines`, the port |
| `go/internal/calendar/watch_test.go` | create | Go vs golden on PostgreSQL; title unit test |
| `App/tests/test_check_deadlines_golden.py` | create | fails when the golden file is stale |
| `docs/context/test-map.md` | edit (1 line) | Filing row names the new Python test |
| `docs/context/status.md` | edit (1 line) | GO-DL A merged, 1134 next |
| `docs/tasks/1134-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (one call, from the repo root): `git branch --show-current` prints `claude/go-check-deadlines-1134` (if not: `git checkout -b claude/go-check-deadlines-1134`); `ls App/scripts/check_deadlines_golden.py go/internal/calendar/watch.go go/internal/calendar/watch_test.go App/tests/test_check_deadlines_golden.py go/internal/calendar/testdata/check_deadlines_golden.json 2>&1 | tail -30` says "No such file" five times; `grep -c` each anchor in §2 in its file prints 1. If `App/.venv/bin/python` is missing: `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5`. Any anchor missing or file present: STOP (§8).

1. Create `App/scripts/check_deadlines_golden.py` with exactly this content (one trailing newline):

```python
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
```

   From `App/`: `.venv/bin/python scripts/check_deadlines_golden.py 2>&1 | tail -3` ends with `wrote .../go/internal/calendar/testdata/check_deadlines_golden.json` (two `DecryptionError` tracebacks before it are expected: they are the unreadable-guest cases being logged). Then from the repo root `sha256sum App/scripts/check_deadlines_golden.py go/internal/calendar/testdata/check_deadlines_golden.json | tail -30` must print `9f13c676f55c8ec2da42f50f0a682652de2529a200e3a4d331d5b58367fea64c` and `b48506b79d2d241835368495b1818cde4133e14c65be1718ea7cf6de52c4f422`. A different script hash: your paste differs; fix it from the block above (never edit the JSON by hand). Commit "1134 step 1" (both files).

2. Create `go/internal/calendar/watch.go` (sha256 `e5e49fb8c6df420dbb4018787f1d1540b4b9a93aa2f90e95f260b983547ef87a`) with exactly:

```go
// watch.go is reporting.check_deadlines (App/app/reporting.py 2614-2736): the
// deadline watch that raises and resolves the deadline, headcount_mismatch and
// guest_record_unreadable alerts. It lives here because the port of
// reservation_progress and reservation_deadline_anchor it needs (progress.go)
// and the guest loader (handler.go) are this package's. Nothing calls it yet:
// brief 1132 §10 E adds the job kind. testdata/check_deadlines_golden.json,
// written by App/scripts/check_deadlines_golden.py, is the parity check.
package calendar

import (
	"context"
	"errors"
	"log"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// watchClearSQL resolves the open cards of cancelled, ignored or archived
// stays in one statement. $2 is the owner; NULL clears every workspace.
const watchClearSQL = `UPDATE alert SET resolved_at = $1, user_dismissed = 0 WHERE id IN (
	SELECT al.id FROM alert al
	JOIN reservation r ON r.id = al.reservation_id
	JOIN apartment a ON a.id = r.apartment_id
	WHERE al.resolved_at IS NULL
	AND al.kind IN ('deadline', 'headcount_mismatch', 'guest_incomplete_checkin')
	AND (r.status != 'active' OR r.archived_at IS NOT NULL)
	AND ($2::bigint IS NULL OR a.owner_user_id = $2::bigint))`

// watchStaysSQL is the stays the watch reads: live, on an active apartment,
// not the demo stay (0100). The order only makes runs repeatable.
const watchStaysSQL = `SELECT r.id, r.apartment_id, a.internal_name, r.date_from, r.date_to,
	r.declared_guests, r.expected_guests_override, r.lead_reduced_guests
	FROM reservation r JOIN apartment a ON a.id = r.apartment_id
	WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1
	AND COALESCE(r.source, '') != 'demo'
	AND ($1::bigint IS NULL OR a.owner_user_id = $1::bigint)
	ORDER BY r.id`

// CheckDeadlines is reporting.check_deadlines: it alerts on stays running out
// of legal time with data missing and returns how many deadline alerts it
// raised. at is the instant of the run; owner limits the run to one workspace
// (nil runs every workspace, as the scheduled job does).
func CheckDeadlines(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, at time.Time, owner *int64) (int, error) {
	now := deadlines.LocalNow(at)
	today := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, time.UTC)
	// Python's validation reads date.today(): the date of the run on the server clock.
	validationToday := time.Date(at.UTC().Year(), at.UTC().Month(), at.UTC().Day(), 0, 0, 0, 0, time.UTC)
	if _, err := pool.Exec(ctx, watchClearSQL, ubyport.UTCNow(), owner); err != nil {
		return 0, err
	}
	stays, err := watchStays(ctx, pool, owner)
	if err != nil {
		return 0, err
	}
	fields := &fieldReader{getenv: getenv}
	raised := 0
	for _, stay := range stays {
		start, ok, err := watchAnchor(ctx, pool, stay)
		if err != nil {
			return raised, err
		}
		if !ok {
			continue
		}
		guests, err := watchGuests(ctx, pool, stay.id, fields)
		if errors.Is(err, secure.ErrInvalidToken) {
			// One unreadable guest row stops the watch for its own stay only.
			log.Printf("deadline watch stopped for reservation_id=%d: guest record unreadable", stay.id)
			aptID, resID := stay.propertyID, stay.id
			err = ubyport.RaiseAlert(ctx, pool, "critical", "guest_record_unreadable",
				stay.property+": a guest record cannot be read, so this stay is not being watched.",
				"A stored guest document field could not be decrypted. Restore the encryption key, or have the guest's document entered again.",
				"guest_record_unreadable:reservation:"+strconv.FormatInt(stay.id, 10),
				&aptID, &resID, nil, ubyport.AlertParams{"property": stay.property})
			if err != nil {
				return raised, err
			}
			continue
		}
		if err != nil {
			return raised, err
		}
		p := progress(stay, guests, validationToday)
		n, err := watchStay(ctx, pool, stay, p, start, now, today)
		if err != nil {
			return raised, err
		}
		raised += n
	}
	return raised, nil
}

// watchStays reads the stays to watch.
func watchStays(ctx context.Context, pool *pgxpool.Pool, owner *int64) ([]stayRow, error) {
	rows, err := pool.Query(ctx, watchStaysSQL, owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []stayRow
	for rows.Next() {
		var s stayRow
		if err := rows.Scan(&s.id, &s.propertyID, &s.property, &s.dateFrom, &s.dateTo,
			&s.declared, &s.override, &s.reduced); err != nil {
			return nil, err
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

// watchAnchor is reservation_deadline_anchor reading its own rows: only the
// guests' stay_from, so it never decrypts and runs before the guest read, as
// Python's does. A stay with no anchor is skipped even when a guest is unreadable.
func watchAnchor(ctx context.Context, pool *pgxpool.Pool, stay stayRow) (time.Time, bool, error) {
	rows, err := pool.Query(ctx,
		`SELECT stay_from FROM guest WHERE reservation_id = $1 AND archived_at IS NULL
		AND stay_from IS NOT NULL AND stay_from != ''`, stay.id)
	if err != nil {
		return time.Time{}, false, err
	}
	defer rows.Close()
	var guests []guestRow
	for rows.Next() {
		var g guestRow
		if err := rows.Scan(&g.row.StayFrom); err != nil {
			return time.Time{}, false, err
		}
		guests = append(guests, g)
	}
	if err := rows.Err(); err != nil {
		return time.Time{}, false, err
	}
	start, ok := anchorDate(stay, guests)
	return start, ok, nil
}

// watchGuests is the guest read of reservation_progress for one stay. Python's
// SELECT * decrypts every encrypted guest column, fee_host_reason included,
// which loadGuests does not read; so that one is decrypted here as a check.
// A field that will not decrypt returns secure.ErrInvalidToken.
func watchGuests(ctx context.Context, pool *pgxpool.Pool, id int64, fields *fieldReader) ([]guestRow, error) {
	byStay, err := loadGuests(ctx, pool, []int64{id}, fields)
	if err != nil {
		return nil, err
	}
	rows, err := pool.Query(ctx,
		`SELECT COALESCE(fee_host_reason_enc, '') FROM guest
		WHERE reservation_id = $1 AND archived_at IS NULL`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var token string
		if err := rows.Scan(&token); err != nil {
			return nil, err
		}
		if _, err := fields.value("", token); err != nil {
			return nil, err
		}
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return byStay[id], nil
}

// watchTitle is the card title: "<property> · <from> – <to>", dates as
// %d.%m.%Y, an unreadable date left out.
func watchTitle(stay stayRow) string {
	dates := ""
	if d, ok := validation.ParseISODate(stay.dateFrom); ok {
		dates = d.Format("02.01.2006")
	}
	if d, ok := validation.ParseISODate(stay.dateTo); ok {
		dates = dates + " – " + d.Format("02.01.2006")
	}
	return stay.property + " · " + dates
}

// watchStay raises or resolves the two cards of one readable stay and returns
// 1 when it raised a deadline alert.
func watchStay(ctx context.Context, pool *pgxpool.Pool, stay stayRow, p progressResult, start, now, today time.Time) (int, error) {
	id := strconv.FormatInt(stay.id, 10)
	key := "deadline:" + id
	mismatchKey := "headcount_mismatch:" + id
	settled := p.status == "reported" || p.status == "not_required"
	title := watchTitle(stay)
	aptID, resID := stay.propertyID, stay.id
	// Once the stay has started, a shortfall is said as such, so it is chased.
	if !settled && p.expected != nil && p.filled < *p.expected && start.Before(today) {
		detail := "Waiting for guest forms · " + strconv.Itoa(p.filled) + "/" + strconv.Itoa(*p.expected)
		if err := ubyport.RaiseAlert(ctx, pool, "warning", "headcount_mismatch", title, detail,
			mismatchKey, &aptID, &resID, nil, nil); err != nil {
			return 0, err
		}
	} else if err := ubyport.ResolveAlert(ctx, pool, mismatchKey); err != nil {
		return 0, err
	}
	if settled {
		return 0, ubyport.ResolveAlert(ctx, pool, key)
	}
	level := deadlines.Urgency(start, now)
	if level != "overdue" && level != "urgent" {
		return 0, ubyport.ResolveAlert(ctx, pool, key)
	}
	expected := "?"
	if p.expected != nil {
		expected = strconv.Itoa(*p.expected)
	}
	counts := strconv.Itoa(p.filled) + "/" + expected
	alertLevel, detail := "warning", "Due now · "+counts
	if level == "overdue" {
		countdown := deadlines.DescribeTimeLeft(start, now)
		if strings.HasPrefix(countdown, "overdue") {
			countdown = "O" + countdown[1:]
		}
		alertLevel, detail = "critical", countdown+" · "+counts
	}
	if err := ubyport.RaiseAlert(ctx, pool, alertLevel, "deadline", title, detail,
		key, &aptID, &resID, nil, nil); err != nil {
		return 0, err
	}
	return 1, nil
}
```

   and `go/internal/calendar/watch_test.go` (sha256 `7c66c44e99e5d9f7b65ee513997c217eb4a2aedbda5dbb6fffc8933ce7241d04`) with exactly:

```go
package calendar

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// watchAlert is one alert row as App/scripts/check_deadlines_golden.py records it.
type watchAlert struct {
	Seed          *int64  `json:"seed"`
	Level         string  `json:"level"`
	Kind          string  `json:"kind"`
	ApartmentID   *int64  `json:"apartment_id"`
	ReservationID *int64  `json:"reservation_id"`
	OwnerUserID   *int64  `json:"owner_user_id"`
	DedupeKey     *string `json:"dedupe_key"`
	Message       string  `json:"message"`
	Detail        *string `json:"detail"`
	Params        *string `json:"params"`
	Created       string  `json:"created"`
	Resolved      string  `json:"resolved"`
	UserDismissed int64   `json:"user_dismissed"`
}

type watchSeedTable struct {
	Table   string   `json:"table"`
	Columns []string `json:"columns"`
	Rows    [][]any  `json:"rows"`
}

type watchRun struct {
	At          string       `json:"at"`
	OwnerUserID *int64       `json:"owner_user_id"`
	Raised      int          `json:"raised"`
	Alerts      []watchAlert `json:"alerts"`
}

type watchGolden struct {
	SeedCreated  string           `json:"seed_created"`
	SeedResolved string           `json:"seed_resolved"`
	Seed         []watchSeedTable `json:"seed"`
	Runs         []watchRun       `json:"runs"`
}

func loadWatchGolden(t *testing.T) watchGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/check_deadlines_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var g watchGolden
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	if len(g.Runs) == 0 || len(g.Seed) == 0 {
		t.Fatal("golden file has no runs or no seed")
	}
	return g
}

// watchValue turns a decoded seed value into what pgx writes: json numbers are ids and counts.
func watchValue(t *testing.T, v any) any {
	t.Helper()
	if n, ok := v.(json.Number); ok {
		i, err := n.Int64()
		if err != nil {
			t.Fatalf("seed number %q is not an integer", n)
		}
		return i
	}
	return v
}

// watchSeed inserts the golden seed rows and returns the seeded alert ids.
func watchSeed(t *testing.T, pool *pgxpool.Pool, g watchGolden) map[int64]bool {
	t.Helper()
	ids := map[int64]bool{}
	for _, table := range g.Seed {
		marks := make([]string, len(table.Columns))
		for i := range marks {
			marks[i] = fmt.Sprintf("$%d", i+1)
		}
		sql := "INSERT INTO " + table.Table + " (" + strings.Join(table.Columns, ", ") +
			") VALUES (" + strings.Join(marks, ", ") + ")"
		for _, row := range table.Rows {
			args := make([]any, len(row))
			for i, v := range row {
				args[i] = watchValue(t, v)
			}
			if _, err := pool.Exec(context.Background(), sql, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
			if table.Table == "alert" {
				ids[args[0].(int64)] = true
			}
		}
	}
	return ids
}

// watchSnapshot reads every alert row the way the golden script records it.
func watchSnapshot(t *testing.T, pool *pgxpool.Pool, g watchGolden, seeded map[int64]bool) []watchAlert {
	t.Helper()
	rows, err := pool.Query(context.Background(),
		`SELECT id, level, kind, apartment_id, reservation_id, owner_user_id, dedupe_key,
		message, detail, params, created_at, resolved_at, user_dismissed FROM alert`)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	var out []watchAlert
	for rows.Next() {
		var a watchAlert
		var id int64
		var created string
		var resolved *string
		if err := rows.Scan(&id, &a.Level, &a.Kind, &a.ApartmentID, &a.ReservationID, &a.OwnerUserID,
			&a.DedupeKey, &a.Message, &a.Detail, &a.Params, &created, &resolved, &a.UserDismissed); err != nil {
			t.Fatal(err)
		}
		if seeded[id] {
			seed := id
			a.Seed = &seed
		}
		a.Created = "run"
		if created == g.SeedCreated {
			a.Created = "seed"
		}
		switch {
		case resolved == nil:
			a.Resolved = "open"
		case *resolved == g.SeedResolved:
			a.Resolved = "seed"
		default:
			a.Resolved = "run"
		}
		out = append(out, a)
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	return out
}

// watchLines is each alert as one JSON line, sorted, so order does not matter.
func watchLines(t *testing.T, alerts []watchAlert) []string {
	t.Helper()
	out := make([]string, 0, len(alerts))
	for _, a := range alerts {
		b, err := json.Marshal(a)
		if err != nil {
			t.Fatal(err)
		}
		out = append(out, string(b))
	}
	sort.Strings(out)
	return out
}

// TestCheckDeadlinesMatchesPython seeds the golden stays, runs CheckDeadlines
// for every golden run and compares the return value and every alert row with
// what reporting.check_deadlines did on the same rows.
func TestCheckDeadlinesMatchesPython(t *testing.T) {
	g := loadWatchGolden(t)
	pool := dbPool(t)
	seeded := watchSeed(t, pool, g)
	for i, run := range g.Runs {
		at, err := time.Parse(time.RFC3339, run.At)
		if err != nil {
			t.Fatal(err)
		}
		raised, err := CheckDeadlines(context.Background(), pool, dbGetenv, at, run.OwnerUserID)
		if err != nil {
			t.Fatalf("run %d: %v", i+1, err)
		}
		if raised != run.Raised {
			t.Errorf("run %d: raised %d, Python raised %d", i+1, raised, run.Raised)
		}
		got := watchLines(t, watchSnapshot(t, pool, g, seeded))
		want := watchLines(t, run.Alerts)
		if strings.Join(got, "\n") != strings.Join(want, "\n") {
			t.Errorf("run %d alerts differ from Python\n got:\n%s\nwant:\n%s", i+1,
				strings.Join(got, "\n"), strings.Join(want, "\n"))
		}
	}
}

func TestWatchTitle(t *testing.T) {
	for _, c := range []struct{ from, to, want string }{
		{"2026-09-10", "2026-09-14", "Byt · 10.09.2026 – 14.09.2026"},
		{"bad", "2026-09-20", "Byt ·  – 20.09.2026"},
		{"2026-09-10", "", "Byt · 10.09.2026"},
		{"", "", "Byt · "},
	} {
		got := watchTitle(stayRow{property: "Byt", dateFrom: c.from, dateTo: c.to})
		if got != c.want {
			t.Errorf("watchTitle(%q, %q) = %q, want %q", c.from, c.to, got, c.want)
		}
	}
}
```

   From `go/`: `sha256sum internal/calendar/watch.go internal/calendar/watch_test.go | tail -30` matches; `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/calendar/ -count=1 2>&1 | tail -30` prints `ok`. Commit "1134 step 2".

3. Create `App/tests/test_check_deadlines_golden.py` (sha256 `e339110eca41b422f84dded4d8a13664ca54d762185a881993611a5379bf8f9c`) with exactly:

```python
"""go/internal/calendar/watch_test.go reads go/internal/calendar/testdata/check_deadlines_golden.json."""

import importlib.util
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "check_deadlines_golden", APP_DIR / "scripts" / "check_deadlines_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_deadlines_golden_matches_python_check_deadlines(monkeypatch, tmp_path):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "check-deadlines-golden.sqlite3")
    generator = _load_generator()
    committed = generator.OUT.read_bytes()
    assert generator.render().encode("utf-8") == committed
    assert committed.count(b'"dedupe_key"') >= 80
```

   From `App/`: `.venv/bin/python -m pytest tests/test_check_deadlines_golden.py tests/test_deadlines.py tests/test_deadlines_golden.py -q --tb=short -x 2>&1 | tail -30` passes. Commit "1134 step 3".

4. Two one-line docs edits (Edit tool, exact strings):
   - `docs/context/test-map.md`: old `test_deadline*.py test_claim_*.py` new `test_deadline*.py test_check_deadlines_golden.py test_claim_*.py`.
   - `docs/context/status.md`: old ``Next: `deadlines` job, brief 1132.`` new ``Next: `deadlines` job: 1132 and 1133 (GO-DL A, #934, ubyport + calendar repointed to go/internal/deadlines) merged; 1134 (GO-DL B, Go `check_deadlines`) next.``

   From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` passes. Commit "1134 step 4".

5. Go DB test locally (optional, 3 calls at most; skip and say "CI only" in the report if any command fails). As root with PostgreSQL 16 installed:

```bash
P=/var/tmp/pg1134 && mkdir -p $P && chown postgres $P && su postgres -c "/usr/lib/postgresql/16/bin/initdb -D $P/data -A trust -U postgres" >/dev/null && su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D $P/data -o '-p 55432 -k $P' -l $P/log -w start" 2>&1 | tail -3
```

```bash
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres go test ./internal/calendar/ -run 'TestCheckDeadlinesMatchesPython|TestWatchTitle' -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
```

   Expected: two `--- PASS` lines and `ok`. A `--- SKIP` means the variable was not seen. A FAIL: STOP (§8), paste the first 30 lines of the diff into the report. Then write the report (§9), commit "1134 step 5".

## 5. Do not touch

`App/app/` (all of it: `reporting.py`, `alerts.py`, `scheduler.py` stay as they are), `go/internal/deadlines/`, every existing file in `go/internal/calendar/` and `go/internal/ubyport/`, `go/internal/jobs/`, `go/cmd/`, `go/go.mod`, `go/go.sum`, `.github/`, every file not in §3. No job kind, env var, route, migration or new dependency. Hard rules 1-5.

## 6. Commands

From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/calendar/ -count=1 2>&1 | tail -30` (the DB test skips locally without `UBYHOST_TEST_DATABASE_URL` and runs in CI; step 5 runs it locally).
From `App/` (Filing row of the [test-map](../context/test-map.md), narrowed): `.venv/bin/python -m pytest tests/test_check_deadlines_golden.py tests/test_deadlines.py tests/test_deadlines_golden.py -q --tb=short -x 2>&1 | tail -30`.
Golden freshness: from `App/`, `.venv/bin/python scripts/check_deadlines_golden.py >/dev/null 2>&1; git status --short ../go | tail -30` prints nothing after step 1's commit.
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] The five sha256 values in steps 1-3 match.
- [ ] From `go/`: gofmt empty, `go vet ./...` clean, `go test ./internal/calendar/ -count=1` ok.
- [ ] Step 5: `TestCheckDeadlinesMatchesPython` PASS on local PostgreSQL, or "CI only" with the reason.
- [ ] From `App/`: the three pytest files pass and the freshness command leaves `git status --short ../go` empty.
- [ ] `python3 scripts/context_lint.py` passes.
- [ ] `git diff --stat ab35038..HEAD | tail -30` lists only the §3 paths plus this brief.
- [ ] Five commits "1134 step 1" to "1134 step 5" on `claude/go-check-deadlines-1134`; nothing pushed.

## 8. Stop and ask

Stop, and write the report as `blocked`, if:

- an anchor in step 0 is not found, or a §3 file already exists;
- the generated golden hash differs while the script hash matches (the Python behaviour moved: never edit the JSON, the Python or the Go to make it match);
- `TestCheckDeadlinesMatchesPython` fails (any Go/Python mismatch is a filing-correctness question for the orchestrator), or any test fails twice;
- a change to Python behaviour, a migration, or SQL that is not plain PostgreSQL seems needed;
- you reach 25 tool calls or about 50k tokens (see executor.md);
- a new dependency seems needed, or a file outside §3 needs a change;
- you need push, merge, a PR, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1134-report.md` (600 tokens at most) and set this brief's `Status: review`. It has: 1. `git diff --stat ab35038..HEAD | tail -10`; 2. each §6 command and step 5 with the last 5 lines of output; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left (none expected: nothing is wired).

## Risk list (for the reviewer)

Read the full diff of `go/internal/calendar/watch.go` against §2 and App/app/reporting.py 2614-2736 line by line (strings, kinds, levels, keys, the clear UPDATE, the stays filter, anchor-before-decrypt order, `start.Before(today)`, the "Overdue" capitalisation, `?`). Then `App/scripts/check_deadlines_golden.py` (the seed must cover each case named in §2) and `watch_test.go` (it must not skip in CI: look for `--- PASS: TestCheckDeadlinesMatchesPython` in the Go job log, not `SKIP`). Known, accepted gaps (not reachable with data UbyHost writes): a token that decrypts to invalid UTF-8 raises in Python but is read in Go; a year below 1000 formats as `0999` in Go and `999` in Python.

## Owner steps

None for this brief: nothing calls `CheckDeadlines` until brief E adds the job kind and switch.
