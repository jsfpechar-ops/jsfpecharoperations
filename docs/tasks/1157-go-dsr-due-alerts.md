# 1157: Go port of `dsr.raise_due_alerts` (the data-subject-request due alerts), parity-checked against Python

Status: todo
Depends on: 1132, 1153 (merged, PR #935) | Base commit: bccafce | Branch: claude/go-dsr-due-alerts-1157
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add `calendar.RaiseDSRDueAlerts`, a Go port of `dsr.raise_due_alerts` (App/app/dsr.py 153-172) that raises the `dsr_due` warning for every open or extended data-subject request due within five days, exactly as Python does, and a golden file written by the real Python over fixed requests so the two cannot drift. Nothing calls the Go function yet (no job kind, no env switch, no route): that is brief 1132 §10 E. This is GO-DL step C (tier B); it adds files only and changes no existing code, so there is no failing-first step.

## 2. Context

Rules that apply (AGENTS.md): 1 filing correctness (not touched: no filing code); 2 no new personal-data field and no outbound request (the fixture uses `owner@example.test` and no names); 3 no guest data in the repo; 4 no new dependency (stdlib, pgx and repo packages already in `go.mod`); 5 Postgres-portable SQL (plain PostgreSQL through `pgxpool`; the Python script uses `db.execute`/`db.query` with `?`).

**Package: `go/internal/calendar`**, next to `watch.go` (brief 1153, same GO-DL job family). A new package would only duplicate the golden test helpers. `calendar` already imports `ubyport`.

**What Python does, and how the Go copies it:**

- Selection: `SELECT * FROM data_subject_request WHERE status IN ('open','extended') AND date(due_at) <= <today + 5 days as YYYY-MM-DD>`. `due_at` is a TEXT column (ISO date or ISO datetime, with or without offset: `dsr.one_month_later` writes `isoformat()`). On SQLite `db.sqlite_date_expr` is `date(due_at)`; on PostgreSQL it is `ubyhost_sqlite_date(due_at)` (App/app/db_postgres.py `PG_SQLITE_DATE_FUNCTION`, installed by the PG baseline migration `App/migrations_pg/00001_baseline.sql`, so the Go test database has it too). Go calls that same function, so an offset such as `2026-09-23T00:30:00+02:00` is `2026-09-22` in UTC on both. The golden covers that case. Go adds `ORDER BY id` (Python has none; order changes nothing: each key belongs to one request).
- Per row: `alerts.raise_alert("warning", "dsr_due", "Data-subject request due <due_at>.", "Handle it and record the outcome.", dedupe_key="dsr_due:<id>", owner_user_id=<row owner, may be NULL>, params={"due": <due_at>})`. No apartment, no reservation. The Go helper `ubyport.RaiseAlert` (go/internal/ubyport/effects.go) takes an explicit `ownerUserID *int64` and only looks the owner up when it is nil **and** an apartment or reservation id is given; here both are nil, so a NULL owner stays NULL, as in Python. It dedupes on the open key (refreshes level, message, detail, params, created_at), never reopens a resolved or dismissed card (inserts a new row), and writes params as Python's `json.dumps(..., ensure_ascii=False, sort_keys=True)` (`{"due": "..."}`, with the space); the golden compares the stored text byte for byte.
- It never resolves anything: the card of a request that was fulfilled stays open until the host clears it (the golden has that case). The return value is the number of rows found.
- **`today`**: Python's optional argument defaults to `date.today()`, the server's local date. The Go function takes `today time.Time` and uses only its year, month and day (no zone conversion), so the test is deterministic and the caller (brief E) decides the zone: it must pass `time.Now()` in the container's local zone, as Python's `date.today()` does. The horizon is built with `time.Date(y, m, d+5, ...)`, which normalises month ends.

**Parity mechanism** (same pattern as brief 1153): `App/scripts/dsr_due_golden.py` seeds a throwaway SQLite database with 2 users, 10 requests and 4 alerts, runs the real `dsr.raise_due_alerts` for 2026-09-17 (horizon 2026-09-22) and 2026-09-25 (horizon 2026-09-30), and writes `go/internal/calendar/testdata/dsr_due_golden.json`: the seed rows and, per run, the return value and every alert row. `dsr_due_test.go` inserts the same seed into a fresh PostgreSQL (`dbPool`, skips without `UBYHOST_TEST_DATABASE_URL`; CI's Go job sets it), runs `RaiseDSRDueAlerts` per run and compares; it reuses `watchGolden`, `watchSeedTable`, `watchAlert`, `watchSeed`, `watchSnapshot` and `watchLines` from watch_test.go. `App/tests/test_dsr_due_golden.py` regenerates in memory and fails when the committed file is stale. Cases covered: open and extended inside the horizon, due exactly on the horizon day, overdue, one day past the horizon (skipped on run 1, raised on run 2), far future (skipped), fulfilled, refused and withdrawn skipped, a fulfilled request's seeded open card left open, NULL owner, two owners, UTC conversion of a `+02:00` due date, refresh of an open card (level, message, params, created_at change), re-raise after a resolved and after a dismissed card, a second run changing nothing already raised.

**Verified by the brief writer** on a scratch copy of bccafce: the files below, generated golden sha256 `cb4570db30832ac23e659fd4c8aa2b2894ec33bc73013c03df22f73ae8fe4730` (generation is deterministic), `gofmt -l` empty, `go vet ./...` clean, `go test ./internal/calendar/` ok **with a local PostgreSQL 16** (the DB test ran, `--- PASS: TestRaiseDSRDueAlertsMatchesPython`, not skipped), the Python test green on SQLite (the PostgreSQL backend run is CI only), and five deliberate mutations of `dsr_due.go` (`<` instead of `<=`, owner dropped, `IN ('open')` only, 4-day horizon, `critical` level) each made the Go test fail.

Anchors that must exist verbatim (step 0): `func watchSeed(t *testing.T, pool *pgxpool.Pool, g watchGolden) map[int64]bool {`, `func watchSnapshot(t *testing.T, pool *pgxpool.Pool, g watchGolden, seeded map[int64]bool) []watchAlert {` and `func watchLines(t *testing.T, alerts []watchAlert) []string {` in go/internal/calendar/watch_test.go; `func dbPool(t *testing.T) *pgxpool.Pool {` in handler_test.go; `func RaiseAlert(` in go/internal/ubyport/effects.go; `def raise_due_alerts(` in App/app/dsr.py; `ubyhost_sqlite_date` in App/migrations_pg/00001_baseline.sql.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/dsr_due_golden.py` | create | seeds fixed rows, runs the real `raise_due_alerts`, writes the golden file |
| `go/internal/calendar/testdata/dsr_due_golden.json` | create (generated by the script) | seed + expected alert rows per run |
| `go/internal/calendar/dsr_due.go` | create | `RaiseDSRDueAlerts`, the port |
| `go/internal/calendar/dsr_due_test.go` | create | Go vs golden on PostgreSQL |
| `App/tests/test_dsr_due_golden.py` | create | fails when the golden file is stale |
| `docs/context/test-map.md` | edit (1 line) | Retention, privacy row names the new Python test |
| `docs/context/status.md` | edit (2 lines) | GO-DL B merged (#935), 1157 next; trimmed to stay under the 700-token cap |
| `docs/tasks/1157-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (one call, from the repo root): `git branch --show-current` prints `claude/go-dsr-due-alerts-1157` (if not: `git checkout -b claude/go-dsr-due-alerts-1157`); `ls App/scripts/dsr_due_golden.py go/internal/calendar/dsr_due.go go/internal/calendar/dsr_due_test.go App/tests/test_dsr_due_golden.py go/internal/calendar/testdata/dsr_due_golden.json 2>&1 | tail -30` says "No such file" five times; `grep -c` each anchor in §2 in its file prints 1 (for `ubyhost_sqlite_date`: at least 1). If `App/.venv/bin/python` is missing: `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5`. Any anchor missing or file present: STOP (§8).

1. Create `App/scripts/dsr_due_golden.py` (sha256 `8075114a39405df51014beab1f65c2a78c074ee2e2d839e078785bbf63184d4d`) with exactly this content (one trailing newline):

```python
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
```

   From `App/`: `.venv/bin/python scripts/dsr_due_golden.py 2>&1 | tail -3` ends with `wrote .../go/internal/calendar/testdata/dsr_due_golden.json`. Then from the repo root `sha256sum App/scripts/dsr_due_golden.py go/internal/calendar/testdata/dsr_due_golden.json | tail -30` must print `8075114a39405df51014beab1f65c2a78c074ee2e2d839e078785bbf63184d4d` and `cb4570db30832ac23e659fd4c8aa2b2894ec33bc73013c03df22f73ae8fe4730`. A different script hash: your paste differs; fix it from the block above (never edit the JSON by hand). Commit "1157 step 1" (both files).

2. Create `go/internal/calendar/dsr_due.go` (sha256 `2c1478c02b5330dfea8429d22f754a0ec1962c0dc99d5c7567d165f1eab3f16b`) with exactly:

```go
// dsr_due.go is dsr.raise_due_alerts (App/app/dsr.py 153-172): a warning card
// for every data-subject request whose one-month deadline is near or past. It
// lives here with the other background-job ports (watch.go). Nothing calls it
// yet: brief 1132 §10 E adds the job kind. testdata/dsr_due_golden.json,
// written by App/scripts/dsr_due_golden.py, is the parity check.
package calendar

import (
	"context"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// dsrDueSoonDays is dsr.DUE_SOON_DAYS.
const dsrDueSoonDays = 5

// dsrDueSQL is the open and extended requests due on or before the horizon
// date ($1, YYYY-MM-DD). ubyhost_sqlite_date is the function db.sqlite_date_expr
// names on PostgreSQL (baseline migration): it reads due_at as SQLite date()
// does, so an offset moves the date to UTC. The order only makes runs repeatable.
const dsrDueSQL = `SELECT id, owner_user_id, due_at FROM data_subject_request
	WHERE status IN ('open', 'extended') AND ubyhost_sqlite_date(due_at) <= $1
	ORDER BY id`

type dsrDueRow struct {
	id    int64
	owner *int64
	dueAt string
}

// RaiseDSRDueAlerts raises (or refreshes) one `dsr_due` warning per request due
// within five days of today, and returns how many requests it found. It never
// resolves a card: a closed request's card is cleared by the host. today is the
// calendar date to compare (only its year, month and day are used, no zone
// conversion): Python's date.today() is the server's local date, so the caller
// passes the local time.
func RaiseDSRDueAlerts(ctx context.Context, pool *pgxpool.Pool, today time.Time) (int, error) {
	horizon := time.Date(today.Year(), today.Month(), today.Day()+dsrDueSoonDays, 0, 0, 0, 0, time.UTC).
		Format("2006-01-02")
	rs, err := pool.Query(ctx, dsrDueSQL, horizon)
	if err != nil {
		return 0, err
	}
	var rows []dsrDueRow
	for rs.Next() {
		var r dsrDueRow
		if err := rs.Scan(&r.id, &r.owner, &r.dueAt); err != nil {
			rs.Close()
			return 0, err
		}
		rows = append(rows, r)
	}
	rs.Close()
	if err := rs.Err(); err != nil {
		return 0, err
	}
	for _, r := range rows {
		err := ubyport.RaiseAlert(ctx, pool, "warning", "dsr_due",
			"Data-subject request due "+r.dueAt+".",
			"Handle it and record the outcome.",
			"dsr_due:"+strconv.FormatInt(r.id, 10),
			nil, nil, r.owner, ubyport.AlertParams{"due": r.dueAt})
		if err != nil {
			return 0, err
		}
	}
	return len(rows), nil
}
```

   From `go/`: `test -z "$(gofmt -l .)" && go vet ./... 2>&1 | tail -30` is clean. Commit "1157 step 2".

3. Create `go/internal/calendar/dsr_due_test.go` (sha256 `1c2226d7ab6781ce4e9658bd1284624672da9864df60246a886761bc35e07b44`) with exactly:

```go
package calendar

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"strings"
	"testing"
	"time"
)

type dsrDueRun struct {
	Today  string       `json:"today"`
	Raised int          `json:"raised"`
	Alerts []watchAlert `json:"alerts"`
}

type dsrDueGolden struct {
	SeedCreated  string           `json:"seed_created"`
	SeedResolved string           `json:"seed_resolved"`
	Seed         []watchSeedTable `json:"seed"`
	Runs         []dsrDueRun      `json:"runs"`
}

// TestRaiseDSRDueAlertsMatchesPython seeds the golden requests, runs
// RaiseDSRDueAlerts for every golden day and compares the return value and
// every alert row with what dsr.raise_due_alerts did on the same rows. It reuses
// the seed and snapshot helpers of watch_test.go.
func TestRaiseDSRDueAlertsMatchesPython(t *testing.T) {
	raw, err := os.ReadFile("testdata/dsr_due_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var g dsrDueGolden
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	if len(g.Runs) < 2 || len(g.Seed) == 0 {
		t.Fatal("golden file has fewer than two runs or no seed")
	}
	wg := watchGolden{SeedCreated: g.SeedCreated, SeedResolved: g.SeedResolved, Seed: g.Seed}
	pool := dbPool(t)
	seeded := watchSeed(t, pool, wg)
	for i, run := range g.Runs {
		today, err := time.Parse("2006-01-02", run.Today)
		if err != nil {
			t.Fatal(err)
		}
		raised, err := RaiseDSRDueAlerts(context.Background(), pool, today)
		if err != nil {
			t.Fatalf("run %d: %v", i+1, err)
		}
		if raised != run.Raised {
			t.Errorf("run %d: raised %d, Python raised %d", i+1, raised, run.Raised)
		}
		got := watchLines(t, watchSnapshot(t, pool, wg, seeded))
		want := watchLines(t, run.Alerts)
		if strings.Join(got, "\n") != strings.Join(want, "\n") {
			t.Errorf("run %d alerts differ from Python\n got:\n%s\nwant:\n%s", i+1,
				strings.Join(got, "\n"), strings.Join(want, "\n"))
		}
	}
}
```

   Commit "1157 step 3".

4. Create `App/tests/test_dsr_due_golden.py` (sha256 `942f22e0cae284ec068e2b8353063af8d1cc869766e45210b62b9f7f62e540d4`) with exactly:

```python
"""go/internal/calendar/dsr_due_test.go reads go/internal/calendar/testdata/dsr_due_golden.json."""

import importlib.util
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "dsr_due_golden", APP_DIR / "scripts" / "dsr_due_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dsr_due_golden_matches_python_raise_due_alerts(monkeypatch, tmp_path):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "dsr-due-golden.sqlite3")
    generator = _load_generator()
    committed = generator.OUT.read_bytes()
    assert generator.render().encode("utf-8") == committed
    assert committed.count(b'"dedupe_key"') >= 15
```

   From `App/`: `.venv/bin/python -m pytest tests/test_dsr_due_golden.py tests/test_dsr_audit.py -q --tb=short -x 2>&1 | tail -30` passes. Commit "1157 step 4".

5. Two one-line docs edits (Edit tool, exact strings):
   - `docs/context/test-map.md`: old `test_dsr_audit.py test_data_keys.py` new `test_dsr_audit.py test_dsr_due_golden.py test_data_keys.py`.
   - `docs/context/status.md` (three replacements; status is at its 700-token cap, so the edit must shrink it):
     - old ``Next: `deadlines` job: 1132, 1133 (GO-DL A, #934) merged; 1153 (GO-DL B) next.`` new ``Next: `deadlines` job: GO-DL A, B merged (#934, #935); C = 1157.``
     - old `SQLite rollback only via existing pg-cutover scripts.` new `SQLite rollback only via pg-cutover scripts.`
     - old ``origin/main` 11-12:`` new `Main 11-12:` (the text is `` `origin/main` 11-12: `` with the backticks; replace it, backticks included, by `Main 11-12:`).

   From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` passes. Commit "1157 step 5".

6. Go DB test locally (optional, 3 calls at most; skip and say "CI only" in the report if any command fails). As root with PostgreSQL 16 installed:

```bash
P=/var/tmp/pg1157 && mkdir -p $P && chown postgres $P && su postgres -c "/usr/lib/postgresql/16/bin/initdb -D $P/data -A trust -U postgres" >/dev/null && su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D $P/data -o '-p 55433 -k $P' -l $P/log -w start" 2>&1 | tail -3
```

```bash
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55433/postgres go test ./internal/calendar/ -run 'TestRaiseDSRDueAlertsMatchesPython' -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
```

   Expected: one `--- PASS` line and `ok`. A `--- SKIP` means the variable was not seen. A FAIL: STOP (§8), paste the first 30 lines of the diff into the report. Then write the report (§9), commit "1157 step 6".

## 5. Do not touch

`App/app/` (all of it: `dsr.py`, `alerts.py`, `scheduler.py` stay as they are), `App/migrations_pg/`, every existing file in `go/internal/calendar/` and `go/internal/ubyport/`, `go/internal/jobs/`, `go/cmd/`, `go/go.mod`, `go/go.sum`, `.github/`, every file not in §3. No job kind, env var, route, migration or new dependency. Hard rules 1-5.

## 6. Commands

From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/calendar/ -count=1 2>&1 | tail -30` (the DB test skips locally without `UBYHOST_TEST_DATABASE_URL` and runs in CI; step 6 runs it locally).
From `App/` (Retention row of the [test-map](../context/test-map.md), narrowed): `.venv/bin/python -m pytest tests/test_dsr_due_golden.py tests/test_dsr_audit.py -q --tb=short -x 2>&1 | tail -30`.
Golden freshness: from `App/`, `.venv/bin/python scripts/dsr_due_golden.py >/dev/null 2>&1; git status --short ../go | tail -30` prints nothing after step 1's commit.
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] The five sha256 values in steps 1-4 match.
- [ ] From `go/`: gofmt empty, `go vet ./...` clean, `go test ./internal/calendar/ -count=1` ok.
- [ ] Step 6: `TestRaiseDSRDueAlertsMatchesPython` PASS on local PostgreSQL, or "CI only" with the reason.
- [ ] From `App/`: the two pytest files pass and the freshness command leaves `git status --short ../go` empty.
- [ ] `python3 scripts/context_lint.py` passes.
- [ ] `git diff --stat bccafce..HEAD | tail -30` lists only the §3 paths plus this brief.
- [ ] Six commits "1157 step 1" to "1157 step 6" on `claude/go-dsr-due-alerts-1157`; nothing pushed.

## 8. Stop and ask

Stop, and write the report as `blocked`, if:

- an anchor in step 0 is not found, or a §3 file already exists;
- the generated golden hash differs while the script hash matches (the Python behaviour moved: never edit the JSON, the Python or the Go to make it match);
- `TestRaiseDSRDueAlertsMatchesPython` fails (any Go/Python mismatch is a question for the orchestrator), or any test fails twice;
- a change to Python behaviour, a migration, or SQL that is not plain PostgreSQL seems needed;
- you reach 25 tool calls or about 50k tokens (see executor.md);
- a new dependency seems needed, or a file outside §3 needs a change;
- you need push, merge, a PR, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1157-report.md` (600 tokens at most) and set this brief's `Status: review`. It has: 1. `git diff --stat bccafce..HEAD | tail -10`; 2. each §6 command and step 6 with the last 5 lines of output; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left (none expected: nothing is wired).

## Risk list (for the reviewer)

Read `go/internal/calendar/dsr_due.go` against App/app/dsr.py 153-172 line by line (status list, `<=`, five days, level, kind, the two strings, key `dsr_due:<id>`, explicit NULL-able owner, params `{"due": due_at}`, no resolve, return value is the row count). Then the golden script (the seed must cover each case named in §2) and `dsr_due_test.go` (it must not skip in CI: look for `--- PASS: TestRaiseDSRDueAlertsMatchesPython` in the Go job log, not `SKIP`). Known and accepted: Python's `today` default is the server-local date, the Go function trusts what the caller passes (brief E must pass local time, not UTC); the golden is generated on SQLite and the Go side runs on PostgreSQL, so `ubyhost_sqlite_date` vs `date()` parity for malformed `due_at` is not covered (the application only writes `isoformat()`); a malformed `due_at` returns NULL in the PG function and is skipped, as `date()` does in SQLite. No outbound request, no new personal-data field (rule 2).

## Owner steps

None for this brief: nothing calls `RaiseDSRDueAlerts` until brief E adds the job kind and switch.
