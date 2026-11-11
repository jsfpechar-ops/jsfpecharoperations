# 1111: CHECK constraints for the state columns that have none (PostgreSQL goose file)

Status: blocked (owner must run the query in section "Owner step first" and paste the result)
Depends on: 1103-1110 | Base commit: 0417f799 | Branch: task/1111-sm-state-check-constraints
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

**HIGH RISK migration.** A CHECK that rejects a value already in production makes `pg_schema.py apply` fail and the app refuses to start while the file is pending. A CHECK that omits a value the code writes breaks filing, door codes or mail at run time. Both are prevented by the order below: the owner runs the query first (Part A), the executor only starts Part B when the pasted result shows no value outside the allowed sets.

## Part A. Owner step first

Do not build anything yet. This is one read-only query on production. It changes nothing. It returns only state words and counts, never guest data, so the result may be pasted in the repo.

1. Log in to the production server the way you always do (the same terminal you use for `./scripts/deploy.sh`).
2. Go to the deploy folder: `cd /opt/ubyhost/deploy/lightsail` (path from [LIGHTSAIL](../LIGHTSAIL.md), "Clone first" step).
3. Copy the whole block below, from `docker compose` to the line that says `SQL`, paste it into the terminal and press Enter. It opens psql the way [OPERATIONS](../OPERATIONS.md) does (`docker compose exec -T postgres psql -U ubyhost -d ubyhost`, OPERATIONS.md line 645), switches the session to read-only first, and runs the query.

```bash
docker compose exec -T postgres psql -U ubyhost -d ubyhost -P pager=off <<'SQL'
SET default_transaction_read_only = on;
SELECT 'guest.submit_state' AS col, COALESCE(submit_state, '<NULL>') AS value, COUNT(*) AS n FROM guest GROUP BY 2
UNION ALL SELECT 'submission.state', COALESCE(state, '<NULL>'), COUNT(*) FROM submission GROUP BY 2
UNION ALL SELECT 'reservation.status', COALESCE(status, '<NULL>'), COUNT(*) FROM reservation GROUP BY 2
UNION ALL SELECT 'email_outbox.state', COALESCE(state, '<NULL>'), COUNT(*) FROM email_outbox GROUP BY 2
UNION ALL SELECT 'door_code.state', COALESCE(state, '<NULL>'), COUNT(*) FROM door_code GROUP BY 2
UNION ALL SELECT 'lock_account.status', COALESCE(status, '<NULL>'), COUNT(*) FROM lock_account GROUP BY 2
UNION ALL SELECT 'cleaning_code.state', COALESCE(state, '<NULL>'), COUNT(*) FROM cleaning_code GROUP BY 2
UNION ALL SELECT 'site_booking.status', COALESCE(status, '<NULL>'), COUNT(*) FROM site_booking GROUP BY 2
UNION ALL SELECT 'ad_click.send_state', COALESCE(send_state, '<NULL>'), COUNT(*) FROM ad_click GROUP BY 2
ORDER BY 1, 2;
SQL
```

4. The screen shows a table with three columns: `col`, `value`, `n`. An error such as `relation "..." does not exist` means the tables are missing: copy the error text and stop.
5. Copy the whole table (select it with the mouse, copy) and paste it into this file under the heading "Owner result (paste here)" at the bottom, replacing the line `PASTE HERE`. Or paste it into the chat and tell the orchestrator.
6. Tell the orchestrator "the result is pasted". The orchestrator checks it against section "Allowed value sets". If every `value` is in the allowed list for its `col` (a `<NULL>` row is allowed only for `ad_click.send_state`), the orchestrator changes the Status line to `todo` and the executor may start Part B. If not, nothing is built: the orchestrator writes a decision about the odd value first.

## Part B. The migration (executor, only when Status is `todo`)

## 1. Objective

Add nine named CHECK constraints (one per column below) in a new PostgreSQL goose file, plus a static test that pins each allowed set against the constants the code uses. This is the last step of the [explicit state machines plan](../plans/explicit-state-machines.md): a new write of a value nobody listed now fails in the database, not silently.

## 2. Context

### 2.1 How migrations work here (evidence)

- Production runs PostgreSQL: `docs/context/status.md` line 7 says "Postgres cutover done". `docs/context/rules.md` line 37 still says "Production stays on SQLite pending owner cutover" and line 44 says `App/app/migrations/` "is frozen at 0033"; both lines are stale (files `0034` to `0043` exist, newest `App/app/migrations/0043_guest_signed_for.sql`). See Open questions 1.
- A PostgreSQL schema change is a goose file `App/migrations_pg/NNNNN_name.sql`, next number = highest + 1 (`docs/context/rules.md` line 44). The highest today is `App/migrations_pg/00014_guest_signed_for.sql`, so the new file is **00015**.
- `App/app/db.py` line 1516: `GOOSE_DIR = Path(__file__).resolve().parent.parent / "migrations_pg"`; `goose_files()` (line 1558) lists them and refuses duplicate versions; `apply_postgresql_schema()` (line 1809) applies every pending goose file inside one transaction (`BEGIN IMMEDIATE` ... `COMMIT`, rollback on any error), so a failing constraint leaves nothing behind.
- The owner applies it after the deploy: `docker compose run --rm --no-deps ubyhost python scripts/pg_schema.py apply --expect-database ubyhost` (`docs/LIGHTSAIL.md` line 224). The app will not start while a goose file is pending.
- Goose files must be additive so the previous image keeps working (`docs/context/rules.md` line 47). A CHECK limited to values the previous image also writes keeps that true.
- **No SQLite twin.** SQLite cannot `ALTER TABLE ... ADD CONSTRAINT`, and the repo has no pattern for adding a CHECK to an existing table on either engine: `grep -n "ADD CONSTRAINT" App/migrations_pg/*.sql App/app/migrations/*.sql` finds nothing outside the baseline dump `App/migrations_pg/00001_baseline.sql`. SQLite files only add a CHECK inside `CREATE TABLE` or `ADD COLUMN ... CHECK (...)` (for example `App/app/migrations/0031_billing_discount_snapshot.sql` lines 27-28). So this brief covers PostgreSQL only. SQLite databases (local runs and the default test run) get no constraint.
- Precedent for a goose file with no SQLite twin: `App/migrations_pg/00008_full_scan_indexes.sql` (header comment "no SQLite twin ... the previous image keeps working"; no `schema_migrations` row). Follow it: **no `schema_migrations` insert**.
- The goose file must be re-runnable: `App/tests/test_goose_migrations.py` line 91 (`test_a_current_schema_without_goose_table_adopts_baseline`) drops `goose_db_version` and re-applies every file. PostgreSQL has no `ADD CONSTRAINT IF NOT EXISTS`, so every constraint is written as `DROP CONSTRAINT IF EXISTS` followed by `ADD CONSTRAINT`.
- Tests: the default test run is SQLite. PostgreSQL tests skip with a reason unless `UBYHOST_DATABASE_URL` or `UBYHOST_TEST_DATABASE_URL` is set (`App/tests/test_db_postgres.py` lines 52-66). The Go tests also run against a goose-built database when `UBYHOST_TEST_DATABASE_URL` is set (`go/internal/palette/palette_test.go` lines 20-26). The executor has no PostgreSQL, so the PostgreSQL test below skips for the executor and CI runs it.
- Column names verified (all `TEXT`): `guest.submit_state` `App/app/db.py:248`, `submission.state` `db.py:277`, `reservation.status` `db.py:209`, `email_outbox.state` `db.py:393`, `door_code.state` `App/app/migrations/0007_door_codes.sql:43`, `lock_account.status` `0007_door_codes.sql:29`, `cleaning_code.state` `0010_cleaning.sql:28`, `site_booking.status` `0034_site_booking.sql:10`, `ad_click.send_state` `0004_meta_capi.sql:5` (nullable).

### 2.2 Allowed value sets (derived from the code, never designed)

Each value has the place that writes (or, where stated, only defines) it. "Python" is `App/app`, "Go" is `go/internal`.

**guest.submit_state** = `pending`, `sent`, `error`, `blocked`, `not_required` (constraint `guest_submit_state_check`)
- `pending` `reporting.py:47` (default `db.py:248`; written `routes/guest.py:2523-2527`, `routes/admin.py:4607-4611`, `admin.py:4730`); `sent` `reporting.py:48` (`reporting.py:1411`, `2445`; Go `ubyport/outcome.go:18`); `error` `reporting.py:49` (Go `outcome.go:19`); `blocked` `reporting.py:50` (Go `outcome.go:20`, `collect.go:26`); `not_required` `reporting.py:51` (`guest.py:2523`; Go `collect.go:27`, written at `collect.go:198-199`).
- Restore on undo is limited to `PENDING, ERROR, BLOCKED` (`reporting.py:2363`, `2476-2481`).

**submission.state** = `running`, `outcome_unknown`, `transport_error`, `ok`, `ok_duplicate`, `partial`, `error` (constraint `submission_state_check`)
- `running` `reporting.py:1693`, `db.py:277` default, Go `ubyport/store.go:85`; `outcome_unknown` `reporting.py:1722`, `1999`, Go `store.go:113`, `recover.go:122`; `transport_error` `reporting.py:1759`, Go `store.go:132`; `ok` `reporting.py:1449`, `1456`, Go `outcome.go:151`, `155`; `ok_duplicate` `reporting.py:1454`, Go `outcome.go:153`; `partial` `reporting.py:1445`, Go `outcome.go:146`; `error` `reporting.py:1445`, Go `outcome.go:148`. Go `store.go:159` writes `plan.State`, which is one of these.

**reservation.status** = `active`, `cancelled` (constraint `reservation_status_check`)
- `active` `db.py:209` default, read at `reporting.py:1118`; `cancelled` `icalsync.py:524`, `icalsync.py:937`, `booking_cancel.py:86`, Go `ical/reconcile.go:340`.

**email_outbox.state** = `queued`, `sending`, `sent`, `failed`, `bounced`, `complained` (constraint `email_outbox_state_check`)
- `queued` `mail.py:21` (written `mail.py:296`; Go `ubyport/notify.go:345`); `sending` `mail.py:22` (`mail.py:673`, `747`); `sent` `mail.py:23` (`mail.py:688`); `failed` `mail.py:24` (`mail.py:705`, `claim.py:780`, Go `ical/reconcile.go:307`); `bounced` `mail.py:25` and `complained` `mail.py:26` are defined constants that code reads (`mail.py:757`, `admin_ops.py:248`) but **no writer exists today** (see Open questions 2); they are included.

**door_code.state** = `pending`, `issuing`, `retrying`, `issued`, `failed`, `expired`, `revoke_pending`, `revoked`, `revoke_failed` (constraint `door_code_state_check`)
- `door_codes.py:13-20` defines the first six, `door_codes.py:21-23` the last three. Written: insert `PENDING` `door_codes.py:202-207`; `ISSUING` `door_codes.py:404`; `ISSUED` `door_codes.py:562-566`, `727-730`; `RETRYING`/`FAILED` `door_codes.py:595-611` (`new_state`); `EXPIRED` `door_codes.py:448`, `1227`; `REVOKE_PENDING` `door_codes.py:848`; `REVOKE_FAILED` `door_codes.py:760`; `REVOKED` `door_codes.py:772`. `period_taken` and `period_shared` (`door_codes.py:28`, `31`) are `last_error` and exception kinds, not states: excluded.
- No Go writer: `grep -rn door_code go/internal` finds only reads.

**lock_account.status** = `ok`, `reauth_needed` (constraint `lock_account_status_check`)
- `ok` `ttlock.py:251` (default `0007_door_codes.sql:29`); `reauth_needed` `ttlock.py:310`. Go only reads the table (`go/internal/palette/db.go:96`).

**cleaning_code.state** = `pending`, `retrying`, `issuing`, `active`, `revoke_pending`, `revoking`, `revoked`, `revoke_failed`, `failed`, `detached` (constraint `cleaning_code_state_check`)
- `cleaning_codes.py`: `active` lines 40, 91-92 (manual insert); `pending` line 121-123 (ttlock insert); `retrying` lines 115, 182; `issuing` and `revoking` line 220; `revoke_pending` lines 31, 61, 87, 173, 186, 211; `revoked` lines 61, 211, 233, 263-267; `detached` line 56; `failed` and `revoke_failed` line 159 (`_failure`). Read at `routes/cleaning.py:257` (`revoke_failed`). No Go writer.

**site_booking.status** = `pending`, `requested`, `paid`, `expired`, `cancelled`, `refunded`, `clash_refunded` (constraint `site_booking_status_check`)
- `booking_site.py:26` (`STATUSES`) and `booking_site.py:337-345` (`_TRANSITIONS` keys, same seven). Direct writers `booking_direct.py:56`, `79`; `booking_webhook.py:84`. No Go writer.

**ad_click.send_state** = `pending`, `sending`, `sent`, `failed`, `expired`, `withdrawn`; NULL stays legal (constraint `ad_click_send_state_check`)
- `meta_capi.py:54` defines the first five; `withdrawn` `signup.py:693`. NULL is the default (`0004_meta_capi.sql:5`; read `meta_capi.py:85`; reset `meta_capi.py:98`). A CHECK passes when the column is NULL, so the constraint needs no `IS NULL` clause.

### 2.3 Fixtures in Go tests that write values outside these sets (found by grep)

These break the Go tests once the constraint exists (those tests build the database from the goose files, `go/internal/palette/palette_test.go` lines 20-26). Step 5 to 8 change them. Verbatim anchors:

- `go/internal/palette/palette_test.go` line 110: `` `INSERT INTO submission (id, apartment_id, created_at, state) VALUES (1, 7, '2026-05-02', 'done')`, ``
- `go/internal/palette/slug_test.go` line 220: `` 		 SELECT g, 7, '2026-05-02', 'done' FROM generate_series(1, 41) g`); err != nil { ``
- `go/internal/ubyport/recover_test.go` line 92: `` 	if _, err := pool.Exec(ctx, `UPDATE submission SET state = 'sent' WHERE id = $1`, subF); err != nil { ``
- `go/internal/ubyport/effects_test.go` line 259: `` 	if _, err := pool.Exec(ctx, `UPDATE guest SET submit_state = 'ok' WHERE id = $1`, guest); err != nil { ``

Why each replacement keeps the test meaning: the palette tests only need "a submission row" (the palette query `go/internal/palette/db.go:139` does not filter by state); `recover.go:122` only touches `state = 'running'` rows (`recover_test.go` needs a non-running one, `ok` is one); `effects.go:186-191` counts only `submit_state = 'error'` (the test needs "not error", `sent` is that).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/migrations_pg/00015_state_check_constraints.sql` | create | nine constraints, Up and Down |
| `App/tests/test_sm_state_check_constraints.py` | create | static test, runs on SQLite |
| `App/tests/test_goose_migrations.py` | append | one PostgreSQL-only test |
| `go/internal/palette/palette_test.go` | edit | line 110, `'done'` to `'ok'` |
| `go/internal/palette/slug_test.go` | edit | line 220, `'done'` to `'ok'` |
| `go/internal/ubyport/recover_test.go` | edit | line 92, `'sent'` to `'ok'` |
| `go/internal/ubyport/effects_test.go` | edit | line 259, `'ok'` to `'sent'` |
| `docs/tasks/1111-report.md` | create | the report (section 9) |

No other file may change. In particular no writer, no `App/app/db.py`, no `App/app/migrations/` file.

## 4. Steps

Do each step in order. After each step run its command and commit with the message `1111 step k`.

**Step 0. Gate (no file changes).**
Open section "Owner result (paste here)" at the bottom of this file.
- If it still says `PASTE HERE`, or the Status line is not `todo`: STOP (section 8) and write the report as `blocked`.
- For every row, check `value` is in the allowed list of its `col` in section 2.2. Any row outside (for example a `guest.submit_state` of `ok`, a `submission.state` of `done`, or a `<NULL>` anywhere except `ad_click.send_state`): **STOP. Create nothing. Write the report with the exact `col`, `value`, `n` of each such row** and tell the owner. Do not widen a set to make it fit: the orchestrator decides.
- Check the earlier briefs landed: command `ls App/tests | grep '^test_sm_' | tail -30`. Expected: files for the machines of 1103 to 1110. Nothing listed: STOP and report.

**Step 1. Create the goose file** `App/migrations_pg/00015_state_check_constraints.sql` with exactly this content:

```sql
-- +goose Up
-- Brief 1111: CHECK constraints for the state columns that had none. No SQLite
-- twin (SQLite cannot ADD CONSTRAINT; no column is read by Python), the previous
-- image keeps working because it writes only these values. Every set is derived
-- from the code that writes the column; see docs/tasks/1111-sm-state-check-constraints.md.
-- Each constraint is dropped first so the file can run again (the adopt-baseline test re-applies every file).
ALTER TABLE guest DROP CONSTRAINT IF EXISTS guest_submit_state_check;
ALTER TABLE guest ADD CONSTRAINT guest_submit_state_check
    CHECK (submit_state IN ('pending', 'sent', 'error', 'blocked', 'not_required'));
ALTER TABLE submission DROP CONSTRAINT IF EXISTS submission_state_check;
ALTER TABLE submission ADD CONSTRAINT submission_state_check
    CHECK (state IN ('running', 'outcome_unknown', 'transport_error', 'ok', 'ok_duplicate', 'partial', 'error'));
ALTER TABLE reservation DROP CONSTRAINT IF EXISTS reservation_status_check;
ALTER TABLE reservation ADD CONSTRAINT reservation_status_check
    CHECK (status IN ('active', 'cancelled'));
ALTER TABLE email_outbox DROP CONSTRAINT IF EXISTS email_outbox_state_check;
ALTER TABLE email_outbox ADD CONSTRAINT email_outbox_state_check
    CHECK (state IN ('queued', 'sending', 'sent', 'failed', 'bounced', 'complained'));
ALTER TABLE door_code DROP CONSTRAINT IF EXISTS door_code_state_check;
ALTER TABLE door_code ADD CONSTRAINT door_code_state_check
    CHECK (state IN ('pending', 'issuing', 'retrying', 'issued', 'failed', 'expired', 'revoke_pending', 'revoked', 'revoke_failed'));
ALTER TABLE lock_account DROP CONSTRAINT IF EXISTS lock_account_status_check;
ALTER TABLE lock_account ADD CONSTRAINT lock_account_status_check
    CHECK (status IN ('ok', 'reauth_needed'));
ALTER TABLE cleaning_code DROP CONSTRAINT IF EXISTS cleaning_code_state_check;
ALTER TABLE cleaning_code ADD CONSTRAINT cleaning_code_state_check
    CHECK (state IN ('pending', 'retrying', 'issuing', 'active', 'revoke_pending', 'revoking', 'revoked', 'revoke_failed', 'failed', 'detached'));
ALTER TABLE site_booking DROP CONSTRAINT IF EXISTS site_booking_status_check;
ALTER TABLE site_booking ADD CONSTRAINT site_booking_status_check
    CHECK (status IN ('pending', 'requested', 'paid', 'expired', 'cancelled', 'refunded', 'clash_refunded'));
ALTER TABLE ad_click DROP CONSTRAINT IF EXISTS ad_click_send_state_check;
ALTER TABLE ad_click ADD CONSTRAINT ad_click_send_state_check
    CHECK (send_state IN ('pending', 'sending', 'sent', 'failed', 'expired', 'withdrawn'));

-- +goose Down
ALTER TABLE ad_click DROP CONSTRAINT IF EXISTS ad_click_send_state_check;
ALTER TABLE site_booking DROP CONSTRAINT IF EXISTS site_booking_status_check;
ALTER TABLE cleaning_code DROP CONSTRAINT IF EXISTS cleaning_code_state_check;
ALTER TABLE lock_account DROP CONSTRAINT IF EXISTS lock_account_status_check;
ALTER TABLE door_code DROP CONSTRAINT IF EXISTS door_code_state_check;
ALTER TABLE email_outbox DROP CONSTRAINT IF EXISTS email_outbox_state_check;
ALTER TABLE reservation DROP CONSTRAINT IF EXISTS reservation_status_check;
ALTER TABLE submission DROP CONSTRAINT IF EXISTS submission_state_check;
ALTER TABLE guest DROP CONSTRAINT IF EXISTS guest_submit_state_check;
```

Check: `ls App/migrations_pg | tail -2 | cat` prints `00014_guest_signed_for.sql` then `00015_state_check_constraints.sql`. If a `00015_*` file already existed before this step: STOP (another brief took the number).
Command: `grep -c "ADD CONSTRAINT" App/migrations_pg/00015_state_check_constraints.sql | tail -30`. Expected: `9`.

**Step 2. Create the static test** `App/tests/test_sm_state_check_constraints.py` with exactly this content:

```python
"""Brief 1111: the CHECK constraints on state columns match what the code writes.

Runs on SQLite (no database needed): it reads the goose file as text and compares
every set with the constants the owning modules define. A new state written by
code but not listed here fails this test before it can fail in production.
"""
from __future__ import annotations

import re
from pathlib import Path

from app import booking_site, door_codes, mail, meta_capi, reporting

GOOSE_FILE = Path(__file__).resolve().parent.parent / "migrations_pg" / "00015_state_check_constraints.sql"

ALLOWED = {
    ("guest", "submit_state"): {"pending", "sent", "error", "blocked", "not_required"},
    ("submission", "state"): {
        "running", "outcome_unknown", "transport_error", "ok", "ok_duplicate", "partial", "error",
    },
    ("reservation", "status"): {"active", "cancelled"},
    ("email_outbox", "state"): {"queued", "sending", "sent", "failed", "bounced", "complained"},
    ("door_code", "state"): {
        "pending", "issuing", "retrying", "issued", "failed", "expired",
        "revoke_pending", "revoked", "revoke_failed",
    },
    ("lock_account", "status"): {"ok", "reauth_needed"},
    ("cleaning_code", "state"): {
        "pending", "retrying", "issuing", "active", "revoke_pending", "revoking",
        "revoked", "revoke_failed", "failed", "detached",
    },
    ("site_booking", "status"): {
        "pending", "requested", "paid", "expired", "cancelled", "refunded", "clash_refunded",
    },
    ("ad_click", "send_state"): {"pending", "sending", "sent", "failed", "expired", "withdrawn"},
}

# The column defaults in db.py / the SQLite migrations: each must be allowed.
DEFAULTS = {
    ("guest", "submit_state"): "pending",
    ("submission", "state"): "running",
    ("reservation", "status"): "active",
    ("email_outbox", "state"): "queued",
    ("door_code", "state"): "pending",
    ("lock_account", "status"): "ok",
    ("site_booking", "status"): "pending",
}


def _up_section() -> str:
    text = GOOSE_FILE.read_text(encoding="utf-8")
    return text.split("-- +goose Down")[0]


def _declared() -> dict:
    found = {}
    pattern = re.compile(
        r"ALTER TABLE (\w+) ADD CONSTRAINT (\w+)\s+CHECK \((\w+) IN \(([^)]*)\)\);"
    )
    for table, name, column, body in pattern.findall(_up_section()):
        values = re.findall(r"'([a-z_]+)'", body)
        assert len(values) == len(set(values)), f"{name} repeats a value"
        assert name == f"{table}_{column}_check"
        found[(table, column)] = set(values)
    return found


def test_goose_file_declares_exactly_the_pinned_constraints():
    assert _declared() == ALLOWED


def test_down_section_drops_every_constraint():
    down = GOOSE_FILE.read_text(encoding="utf-8").split("-- +goose Down")[1]
    assert down.count("DROP CONSTRAINT IF EXISTS") == len(ALLOWED)


def test_every_add_is_preceded_by_a_drop_so_the_file_can_run_again():
    up = _up_section()
    assert up.count("DROP CONSTRAINT IF EXISTS") == up.count("ADD CONSTRAINT") == len(ALLOWED)


def test_defaults_are_allowed():
    for key, default in DEFAULTS.items():
        assert default in ALLOWED[key], key


def test_constants_in_code_equal_the_allowed_sets():
    assert {
        reporting.PENDING, reporting.SENT, reporting.ERROR, reporting.BLOCKED, reporting.NOT_REQUIRED,
    } == ALLOWED[("guest", "submit_state")]
    assert {
        mail.QUEUED, mail.SENDING, mail.SENT, mail.FAILED, mail.BOUNCED, mail.COMPLAINED,
    } == ALLOWED[("email_outbox", "state")]
    assert {
        door_codes.PENDING, door_codes.ISSUING, door_codes.RETRYING, door_codes.ISSUED,
        door_codes.FAILED, door_codes.EXPIRED,
        door_codes.REVOKE_PENDING, door_codes.REVOKED, door_codes.REVOKE_FAILED,
    } == ALLOWED[("door_code", "state")]
    assert {
        meta_capi.PENDING, meta_capi.SENDING, meta_capi.SENT, meta_capi.FAILED, meta_capi.EXPIRED, "withdrawn",
    } == ALLOWED[("ad_click", "send_state")]
    assert set(booking_site.STATUSES) == ALLOWED[("site_booking", "status")]
    assert set(booking_site._TRANSITIONS) == ALLOWED[("site_booking", "status")]
```

Command: `cd App && .venv/bin/python -m pytest tests/test_sm_state_check_constraints.py -q --tb=short -x 2>&1 | tail -30`. Expected: `6 passed`. If `app.meta_capi`, `door_codes` or `mail` fails to import: STOP and report the last 30 lines.

**Step 3. Append the PostgreSQL-only test** to `App/tests/test_goose_migrations.py`. The file's last two lines today are (verify first with `tail -2 App/tests/test_goose_migrations.py`; if they differ: STOP):

```
    db.apply_postgresql_schema()
    assert db.validate_postgres_schema()["goose_pending"] == []
```

Append, after one blank line, exactly this (file ends with a newline; the append command is `cat >> App/tests/test_goose_migrations.py <<'EOF'` with the lines below, the first line being an empty line):

```python


STATE_CHECKS = [
    "guest_submit_state_check",
    "submission_state_check",
    "reservation_status_check",
    "email_outbox_state_check",
    "door_code_state_check",
    "lock_account_status_check",
    "cleaning_code_state_check",
    "site_booking_status_check",
    "ad_click_send_state_check",
]


@PG_ONLY
def test_state_check_constraints_are_installed_and_validated(pg_goose):
    conn = db.connect()
    try:
        rows = conn.execute_native(
            "SELECT conname, convalidated FROM pg_constraint WHERE conname = ANY(%s)", (STATE_CHECKS,)
        ).fetchall()
    finally:
        conn.close()
    assert sorted(row["conname"] for row in rows) == sorted(STATE_CHECKS)
    assert all(row["convalidated"] for row in rows)
```

Command: `cd App && .venv/bin/python -m pytest tests/test_goose_migrations.py -q --tb=short -x -rs 2>&1 | tail -30`. Expected: `1 passed` and the PostgreSQL tests reported as skipped with the reason "PostgreSQL integration tests need UBYHOST_DATABASE_URL ..." (this skip is expected for the executor; CI has PostgreSQL). Any failure other than skip: fix once, rerun, then STOP.

**Step 4. Confirm the other fixtures with no change.** Command: `grep -rn "'done'" go/internal --include=*_test.go | tail -30`. Expected: exactly the two lines of 2.3 (`palette_test.go:110`, `slug_test.go:220`). More lines: STOP and report them (a fixture writes a value the plan did not list).

**Step 5. Edit `go/internal/palette/palette_test.go` line 110.** Anchor (grep it first: `grep -nF "VALUES (1, 7, '2026-05-02', 'done')" go/internal/palette/palette_test.go | tail -30`, expected exactly one line, 110). Replace `'done')` with `'ok')` on that line only, so the line becomes:
`` 		`INSERT INTO submission (id, apartment_id, created_at, state) VALUES (1, 7, '2026-05-02', 'ok')`, ``
Command: `grep -nF "VALUES (1, 7, '2026-05-02', 'ok')" go/internal/palette/palette_test.go | tail -30`. Expected: line 110.

**Step 6. Edit `go/internal/palette/slug_test.go` line 220.** Anchor: `grep -nF "SELECT g, 7, '2026-05-02', 'done' FROM generate_series(1, 41) g" go/internal/palette/slug_test.go | tail -30` (expected exactly one line, 220). Replace `'done'` with `'ok'` on that line only.
Command: `grep -nF "SELECT g, 7, '2026-05-02', 'ok' FROM generate_series(1, 41) g" go/internal/palette/slug_test.go | tail -30`. Expected: line 220.

**Step 7. Edit `go/internal/ubyport/recover_test.go` line 92.** Anchor: `grep -nF "UPDATE submission SET state = 'sent' WHERE id = \$1" go/internal/ubyport/recover_test.go | tail -30` (expected exactly one line, 92). Replace `'sent'` with `'ok'` on that line only.
Command: `grep -nF "UPDATE submission SET state = 'ok' WHERE id = \$1" go/internal/ubyport/recover_test.go | tail -30`. Expected: line 92.

**Step 8. Edit `go/internal/ubyport/effects_test.go` line 259.** Anchor: `grep -nF "UPDATE guest SET submit_state = 'ok' WHERE id = \$1" go/internal/ubyport/effects_test.go | tail -30` (expected exactly one line, 259). Replace `'ok'` with `'sent'` on that line only.
Command: `grep -nF "UPDATE guest SET submit_state = 'sent' WHERE id = \$1" go/internal/ubyport/effects_test.go | tail -30`. Expected: line 259.

**Step 9. Context lint.** Command: `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: no error for this brief (it warns when two open briefs name the same file in section 3; report any warning in the report, do not fix it).

**Step 10. Report.** Write `docs/tasks/1111-report.md` (section 9) and set `Status: review`. Go tests are not run by the executor (they need PostgreSQL); say so in the report.

## 5. Do not touch

- Every writer: `App/app/reporting.py`, `mail.py`, `door_codes.py`, `cleaning_codes.py`, `booking_site.py`, `meta_capi.py`, `ttlock.py`, `signup.py`, `claim.py`, `icalsync.py`, and every non-test file under `go/`.
- `App/app/db.py` (`SCHEMA` and `ADDED_COLUMNS` never change, rules.md line 44), `App/app/migrations/` (no new SQLite file: SQLite cannot add a constraint), `App/migrations_pg/00001` to `00014`.
- Hard rules: 1 (filing correctness wins: if in doubt about a filing value, STOP), 3 (the pasted owner result holds only state words and counts; remove anything else before committing), 4 (no new dependency), 5 (SQL only through `db.py` helpers; the new file is a goose file, Postgres only).
- Never widen an allowed set, never add `NOT VALID`, never drop a constraint to make a test pass.

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

- `.venv/bin/python -m pytest tests/test_sm_state_check_constraints.py -q --tb=short -x 2>&1 | tail -30` expects `6 passed`.
- `.venv/bin/python -m pytest tests/test_goose_migrations.py tests/test_migrations.py -q --tb=short -x -rs 2>&1 | tail -30` expects no failure; the PostgreSQL tests skip with the stated reason.
- `.venv/bin/python -m pytest tests/test_db_upgrade.py -q --tb=short -x 2>&1 | tail -30` (the [test-map](../context/test-map.md) row "Database, migrations" is `test_migrations.py test_db_*.py`; run `test_db_upgrade.py` as the SQLite member of that row) expects no failure.

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] Step 0 passed: the owner result is pasted and every value is inside the allowed sets (or the report is `blocked` with the odd rows).
- [ ] `App/migrations_pg/00015_state_check_constraints.sql` exists, has 9 `ADD CONSTRAINT` and 18 `DROP CONSTRAINT IF EXISTS` lines in total (9 in Up, 9 in Down); `grep -c "DROP CONSTRAINT IF EXISTS" App/migrations_pg/00015_state_check_constraints.sql | tail -30` prints `18`.
- [ ] `test_sm_state_check_constraints.py`: 6 passed.
- [ ] `test_goose_migrations.py`: no failure (the PostgreSQL tests are skipped for the executor, run by CI).
- [ ] `grep -rn "'done'" go/internal --include=*_test.go | tail -30` prints nothing.
- [ ] `git diff --stat` shows only the files of section 3.

## 8. Stop and ask

Stop, and write the report, if:

- the owner result is missing, or any value is outside its allowed set (Step 0): create nothing;
- an excerpt or anchor is not found, or a grep count differs from the stated one;
- another `00015_*` goose file exists;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change (for example a Go fixture that grep step 4 found beyond the two listed);
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH, deploy, or to run `pg_schema.py apply` (hand that to the owner with the exact command in "Owner steps after merge").

## 9. Report

Write `docs/tasks/1111-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Open questions

1. **Stale rules text.** `docs/context/rules.md` lines 37 and 44 say production is SQLite and `App/app/migrations/` is frozen at 0033, but `docs/context/status.md` line 7 says the Postgres cutover is done and files `0034` to `0043` exist. This brief follows status.md and the goose rule. The orchestrator fixes rules.md at review.
2. **No SQLite or two-engine pattern.** The repo has no existing way to add a CHECK to an existing table on both engines, and SQLite cannot do it. The brief covers PostgreSQL only. SQLite databases (local runs, the default pytest run) get no constraint; the static test is what protects them. Decision needed only if the owner wants SQLite covered: that would be a table rebuild, a new pattern, and a separate brief.
3. **`email_outbox` `bounced` and `complained`** are defined and read (`mail.py:25-26`, `757`, `admin_ops.py:248`) but nothing writes them today. Included so a later SES webhook does not hit the constraint. Remove them only if the owner prefers a strict "what is written today" set.
4. **`door_code` `period_taken`/`period_shared`** are exception kinds and `last_error` prefixes, not states (`door_codes.py:392`, `459`, `524`, `552`). Excluded. Part A would show them if production holds them as a state.
5. **Go fixtures.** Four Go test fixtures write values outside the sets (section 2.3) and are fixed in steps 5 to 8. Go fixtures that pass the state as a `$n` parameter cannot be found by grep; the Go test run in CI with `UBYHOST_TEST_DATABASE_URL` set is the check. The executor cannot run it.
6. **Lock and size.** `ADD CONSTRAINT ... CHECK` takes an exclusive lock and scans the whole table inside the apply transaction. The tables are small today; the Part A counts show how small. If any `n` total is above about 1,000,000 rows, the orchestrator decides whether to use `NOT VALID` plus a later `VALIDATE CONSTRAINT`.

## Risk list (for the reviewer)

- `App/migrations_pg/00015_state_check_constraints.sql`: each value list against section 2.2 and the pasted owner result.
- `App/tests/test_sm_state_check_constraints.py`: the `ALLOWED` sets equal the migration.
- The four one-line Go test edits.

## Owner steps after merge

1. Wait for the green merge and the auto deploy (the app waits because the goose file is pending).
2. On the server: `cd /opt/ubyhost/deploy/lightsail`.
3. Apply the file: `docker compose run --rm --no-deps ubyhost python scripts/pg_schema.py apply --expect-database ubyhost 2>&1 | tail -30`. Expected: no error. The apply is one transaction: on any error nothing changes.
4. Check: `docker compose exec -T postgres psql -U ubyhost -d ubyhost -c "SELECT conname FROM pg_constraint WHERE conname LIKE '%\_state\_check' OR conname LIKE '%\_status\_check' ORDER BY 1;"`. Expected: the nine names from Step 1 among the rows.
5. Check the app is healthy: `./scripts/status.sh`. Expected: healthy.
6. Rollback if filing, door codes or mail misbehave afterwards: `docker compose exec -T postgres psql -U ubyhost -d ubyhost -c "ALTER TABLE guest DROP CONSTRAINT IF EXISTS guest_submit_state_check;"` and the same for the other eight names (the Down section of the file lists all nine), then tell the orchestrator which write was refused (`docker compose logs --tail 50 ubyhost`).

## Owner result (paste here)

PASTE HERE
