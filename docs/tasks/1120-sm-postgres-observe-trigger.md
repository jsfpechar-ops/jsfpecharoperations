# 1120: Observe mode in PostgreSQL: record, never block, a state move the round 1 tables do not allow

Status: todo (Part A now; Part B only when the gate line in "Part B gate" says `yes`)
Depends on: PR #920 merged, 1119 | Base commit: PR #920 merged to main | Branch: Part A `task/1120a-observe-trigger-tolerance`, Part B `task/1120b-observe-trigger`
Executor: Haiku 5.5 | Fits one session per part: 30 tool calls, 60k tokens. Part A and Part B are two sessions and two PRs.

**HIGH RISK migration.** One PL/pgSQL trigger on each of the 11 round 1 state columns. It writes a row to a small log table when a write makes a move that the Python table does not list. It can never make the write fail. No writer changes, in Python or Go.

## Owner decisions

1. **A Postgres-only trigger** (bends hard rule 5 "Postgres-portable SQL", and `docs/context/rules.md` line 40 "No new triggers"). SQLite, which is kept only for rollback, gets nothing. **Answered yes on 2026-11-11** (the orchestrator passed this on). The orchestrator writes the decision line in `docs/context/decisions.md`. Step A0 checks that the line is there.
2. **Retention period for `state_transition_violation`.** Default in this brief: **90 days** after the row was written, deleted by the nightly retention run. Still open. To pick another period, change `STATE_VIOLATION_DAYS` in Step B9 and the RETENTION.md row in Step B13 before Part B runs.

## Why two parts (read this first)

`App/app/db.py` line 1362 marks the PostgreSQL schema `current` only if `expected_triggers == actual_triggers` (exactly the six invoice guards, lines 1338-1341). The app checks this at every start (`init_db`, line 1729, calls `validate_postgres_schema`, line 1420, which raises). `deploy.sh` applies goose files before the new stack starts (lines 219-227), and its `rollback()` (lines 40-58) puts back `ubyhost:previous` without undoing migrations. An image without the tolerance would refuse to start next to the 11 triggers, which `docs/context/rules.md` line 47 forbids ("the previous image must keep working on the migrated schema").
- **Part A** (small PR, no migration): `postgres_schema_status` ignores triggers named `sm_observe_*`. It merges and deploys first.
- **Part B** (second PR, only when Part A is live): the goose file, tests, retention. A rolled-back Part B deploy lands on Part A's image, which accepts the triggers.

## 1. Objective

Record in production every state change on the 11 round 1 state columns that the round 1 tables do not list, for the Python and the Go writers, without changing any writer and without ever blocking a write. Round 4 then turns each machine from "record" into "refuse", using this record as its evidence.

## 2. Context

### 2.1 Goose mechanics (evidence, SM920 = PR #920's branch)

- Production is PostgreSQL (`docs/context/status.md` line 7; `rules.md` line 37 is stale). Name `NNNNN_name.sql` (`db.py` line 1518). Main ends at `00015_lead_reduced_guests.sql`; **this brief uses `00016`** (reserved; 1111 becomes `00017`). Newest files (`00014`, `00015`) are SQLite twins with a `schema_migrations` row. A file with no twin writes none (precedent `00008_full_scan_indexes.sql`). PostgreSQL-only table precedent: `job` in `00003`.
- Python reads Up with `db._goose_up_statements` (lines 1579-1610): a `-- +goose StatementBegin`/`StatementEnd` block is one statement; the rest is split by `db._statements` (line 1662) with `sqlite3.complete_statement`, **which treats `CREATE TRIGGER ...;` as unfinished until `END;`** (reproduced: "migration ends with an incomplete statement"). So the function and every `CREATE TRIGGER` are their own blocks. The goose binary (CI "goose builds the baseline") reads the same markers. Go test helpers `Exec` the whole Up section (`go/internal/palette/palette_test.go` lines 66-74).
- `apply_postgresql_schema()` (lines 1809-1841): one transaction, then validate. Production: `deploy.sh` lines 219-227 run `scripts/pg_schema.py apply` with the new image; on failure the old stack keeps serving. Manual command: `docs/LIGHTSAIL.md` line 224.
- Must run again: `App/tests/conftest.py` lines 214-249 truncate every table (with `goose_db_version`) and re-apply; so `IF NOT EXISTS`, `CREATE OR REPLACE`, `DROP TRIGGER IF EXISTS` then `CREATE TRIGGER`.
- SQLite needs no skip: goose is PostgreSQL only (`_goose_only`, line 1553); `scripts/migration_guard.py` checks only `App/app/migrations/`. Extra tables keep the schema current (line 1359), extra triggers do not (line 1362).
- Tests: PostgreSQL tests skip without `UBYHOST_DATABASE_URL`/`UBYHOST_TEST_DATABASE_URL` (`test_db_postgres.py` lines 52-66); `test_goose_migrations.py` has `PG_ONLY` and the `pg_goose` fixture. CI `test-postgres` (`ci.yml` 112-193) runs `test_db_postgres.py` with 0 skips; `test-postgres-full` (195-240) runs the suite on PostgreSQL; Go: `go test ./...` (line 276). You have no PostgreSQL: those tests skip for you.
- From 1111 ("Open questions", 2.3): no SQLite pattern exists; Go fixtures write values outside the tables (`recover_test.go` line 92, `effects_test.go` line 259). Here they only add rows to throwaway test databases. No Go change.

### 2.2 Design (and why)

- **Pairs are trigger arguments**, not a reference table: `'<state col>', '<key col>', 'from>to', ...`, `''` for NULL. The pairs live in the one file the static test reads; there is no second, hand-editable copy in production; the check is an in-memory scan with no table read. Cost: a later table change needs a goose file that recreates that trigger, which keeps the change visible in review.
- **One function** reads state and key with `to_jsonb(OLD/NEW) ->> TG_ARGV[n]` (PL/pgSQL has no dynamic field access). The key column is an argument because `reservation_claim`'s key is `reservation_id` (`db.py` line 364).
- `AFTER UPDATE OF <col> ... WHEN (OLD.<col> IS DISTINCT FROM NEW.<col>)`: same-state writes, updates not naming the column and INSERTs never call it. NULL counts as a value: `ad_click.send_state` NULL to `pending` (`meta_capi.enqueue`, an UPDATE) is the allowed `'>pending'`.
- **Never blocks:** the insert sits in `BEGIN ... EXCEPTION WHEN OTHERS THEN NULL; END;`, no `RAISE`, `RETURN NULL`. The block (one subtransaction) is entered only for a violating row; allowed moves pay nothing. One statement violating on 64+ rows in one transaction overflows the subtransaction cache until commit. Acceptable; writers change one row at a time. A rolled-back write leaves no violation row.
- Unqualified names (like `db_postgres.py` lines 440-484). `SET LOCAL lock_timeout = '5s'`: `CREATE TRIGGER` blocks writes to each table until commit; on timeout the apply rolls back and the deploy stops.

### 2.3 Columns covered and where each Python table lives (SM920)

| Trigger | table.column | key | Python table |
|---|---|---|---|
| `sm_observe_guest_submit_state` | `guest.submit_state` | `id` | `App/app/reporting.py` line 59 `TRANSITIONS` |
| `sm_observe_submission_state` | `submission.state` | `id` | `App/app/reporting.py` line 2749 `SUBMISSION_TRANSITIONS` |
| `sm_observe_reservation_claim_state` | `reservation_claim.state` | `reservation_id` | `App/app/claim.py` line 22 `TRANSITIONS` |
| `sm_observe_door_code_state` | `door_code.state` | `id` | `App/app/door_codes.py` line 37 `TRANSITIONS` |
| `sm_observe_cleaning_code_state` | `cleaning_code.state` | `id` | `App/app/cleaning_codes.py` line 23 `TRANSITIONS` |
| `sm_observe_site_booking_status` | `site_booking.status` | `id` | `App/app/booking_site.py` line 337 `_TRANSITIONS` |
| `sm_observe_payment_request_status` | `payment_request.status` | `id` | `App/app/payment_request.py` line 24 `_TRANSITIONS` |
| `sm_observe_email_outbox_state` | `email_outbox.state` | `id` | `App/app/mail.py` line 31 `OUTBOX_TRANSITIONS` |
| `sm_observe_push_outbox_state` | `push_outbox.state` | `id` | `App/app/push.py` line 39 `PUSH_TRANSITIONS` |
| `sm_observe_ad_click_send_state` | `ad_click.send_state` (nullable) | `id` | `App/app/meta_capi.py` line 59 `SEND_TRANSITIONS` |
| `sm_observe_guide_import_status` | `guide_import.status` | `id` | `App/app/guest_guide_import.py` line 28 `IMPORT_TRANSITIONS` |

`None` keys in the tables (`SUBMISSION_TRANSITIONS`, claim `TRANSITIONS`: the INSERT; `SEND_TRANSITIONS`: NULL) become `''`. Self-pairs (`claimed>claimed`, `active>active`, ...) are copied as they are. They never fire, but copying them keeps the file exactly equal to the tables. The pair lists in Step B1 were generated from these tables with an `ast` script and checked against them.

### 2.5 Personal data and retention (hard rule 2)

A row holds a table name, a column name, the row's key and two state words. For `guest`, `reservation_claim` (key = `reservation_id`) and `ad_click` (points at a `user_account`), the key identifies one guest, stay or account when joined. That makes the row pseudonymous personal data (GDPR Art. 4(5), recital 26). So it gets a `retention.py` line and a fixed period. It is pruned where the other log-like tables are pruned: `App/app/retention.py` `STEPS` (lines 543-565, next to `rate_limit_events` and `havel_gap`), with an audit line from `_cutoffs` (lines 568-598; `tests/test_retention_alignment.py` `test_every_step_of_the_run_writes_class_count_and_cutoff` requires a cutoff for every step). The step does nothing on SQLite (the table exists only in PostgreSQL) and on an owner-scoped run (the table has no owner), like `_havel_gap_step` (lines 260-268). The retention run is a dry run unless `UBYHOST_RETENTION_AUTOPURGE=1` (`docs/privacy/RETENTION.md` lines 3-5), the same as every other step.

### 2.6 Performance (honest)

Per UPDATE that names a covered column, PostgreSQL evaluates the `WHEN` clause (a C-level comparison, negligible). Only when the state really changes does the function run: two `to_jsonb` row conversions and a scan of at most 22 short strings, in the order of microseconds to tens of microseconds. `to_jsonb` reads the whole row, so large columns are read too: `email_outbox.payload`, `submission.request_xml` and `response_xml`, and the encrypted `guest` fields. These rows were usually just read or written, so their pages are normally in memory. A violating update adds one subtransaction and one small INSERT.

Hot tables, by state changes per day: **`email_outbox`** (every mail: `queued>sending>sent`, 2 firings), **`guest.submit_state`** and **`submission.state`** (every UbyPort batch: one firing per guest and one per batch), **`push_outbox`** (one per alert), `door_code` (a few per stay). The rest (`site_booking`, `payment_request`, `reservation_claim`, `cleaning_code`, `ad_click`, `guide_import`) change rarely. Expected total: a few thousand firings a day at most. Filing correctness is unaffected: the trigger cannot fail and changes no row it fires on.

## 3. Files

Part A:

| Path | Action | What |
|---|---|---|
| `App/app/db.py` | edit | line 1342: ignore `sm_observe_*` triggers in `postgres_schema_status` |
| `App/tests/test_goose_migrations.py` | append | one PostgreSQL-only test |
| `docs/tasks/1120-report.md` | create | Part A report |

Part B:

| Path | Action | What |
|---|---|---|
| `App/migrations_pg/00016_state_transition_observe.sql` | create | table, function, 11 triggers; Down |
| `App/tests/test_sm_state_observe_trigger.py` | create | static parity test (runs on SQLite) |
| `App/tests/test_goose_migrations.py` | append | three PostgreSQL-only tests |
| `App/tests/test_db_postgres.py` | edit | lines 251, 252, 278 and after 285: the new table and triggers |
| `App/app/retention.py` | edit | personal-data comment, constant, step, `STEPS` entry, cutoff |
| `docs/privacy/RETENTION.md` | edit | one row after line 35 |
| `docs/tasks/1120-report.md` | edit | Part B section |

No other file may change.

## 4. Steps

Commit after each step with the message `1120 step <id>` (for example `1120 step A1`).

### Part A (branch `task/1120a-observe-trigger-tolerance` from main)

**Step A0. Gate (no file change).**
Command: `grep -n "1120" docs/context/decisions.md | tail -30`. Expected: a line that records the owner's yes to the Postgres-only trigger. No such line: STOP (section 8), report `blocked: decision line missing`.
Command: `grep -c '^<<<<<<<' docs/context/decisions.md | tail -30`. Expected: `0`. Anything else: STOP and report it (the file has merge-conflict markers; the orchestrator fixes it).
Command: `ls App/tests | grep '^test_sm_' | tail -30`. Expected: the round 1 pin tests (`test_sm_cleaning_code_state.py` ... `test_sm_submission_state.py`). None listed: STOP (PR #920 is not merged).

**Step A1. Edit `App/app/db.py`.** Anchor (grep first, expected exactly one line, 1342):
`grep -nF 'actual_triggers = {row["name"] for row in trigger_rows}' App/app/db.py | tail -30`
Replace that one line with these five lines (same 8-space indent):

```python
        # Brief 1120: the sm_observe_* triggers belong to goose 00016, as the job table
        # belongs to 00003; the goose version row, not this set, says they are installed.
        actual_triggers = {
            row["name"] for row in trigger_rows if not row["name"].startswith("sm_observe_")
        }
```

Command: `grep -nF 'if not row["name"].startswith("sm_observe_")' App/app/db.py | tail -30`. Expected: one line, 1346.

**Step A2. Append to `App/tests/test_goose_migrations.py`.** Check that the last two lines are still these (`tail -2 App/tests/test_goose_migrations.py`; if they differ: STOP):

```
    db.apply_postgresql_schema()
    assert db.validate_postgres_schema()["goose_pending"] == []
```

Append exactly the following. The first two lines are empty lines; the file ends with a newline.

```python


@PG_ONLY
def test_an_observe_trigger_keeps_the_schema_current_and_another_trigger_does_not(pg_goose):
    # Brief 1120 part A: sm_observe_* triggers (goose 00016) are not a schema mismatch,
    # so the image before 00016's PR can still start after the deploy rollback.
    _run(
        "CREATE TRIGGER sm_observe_zz_probe AFTER UPDATE OF state ON email_outbox "
        "FOR EACH ROW EXECUTE FUNCTION ubyhost_invoice_note_guard()"
    )
    status = db.postgres_schema_status()
    assert status["current"] is True
    assert status["missing_triggers"] == status["extra_triggers"] == 0
    _run(
        "CREATE TRIGGER zz_other_probe AFTER UPDATE OF state ON email_outbox "
        "FOR EACH ROW EXECUTE FUNCTION ubyhost_invoice_note_guard()"
    )
    assert db.postgres_schema_status()["current"] is False
```

Command: `cd App && .venv/bin/python -m pytest tests/test_goose_migrations.py -q --tb=short -x -rs 2>&1 | tail -30`. Expected: `2 passed`, the rest skipped with the reason "PostgreSQL integration tests need UBYHOST_DATABASE_URL ...". That skip is expected for you; CI runs them.

**Step A3. The test-map row.** Command: `cd App && .venv/bin/python -m pytest tests/test_migrations.py tests/test_db_upgrade.py -q --tb=short -x 2>&1 | tail -30`. Expected: no failure.

**Step A4. Context lint.** `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: no error. Put any warning in the report.

**Step A5. Report and PR.** Write `docs/tasks/1120-report.md` with a heading `## Part A` (section 9). Set the Status line of this brief to `review (Part A)`. Open one PR titled `1120 part A: schema status ignores sm_observe_ triggers`. Its body says: "Must merge and deploy before Part B (see brief 1120, 'Why two parts'). CI test-postgres-full runs the new PostgreSQL test." Stop here. Part B is a new session.

### Part B gate

Part A live in production: **no** (the orchestrator changes this to `yes` once the owner confirms Owner step A3).

### Part B (branch `task/1120b-observe-trigger` from main, a new session)

**Step B0. Gate (no file change).**
- The gate line above must read `yes`. Otherwise STOP and report `blocked: Part A not live`.
- `grep -nF 'startswith("sm_observe_")' App/app/db.py | tail -30` prints one line. Otherwise STOP (Part A is not on main).
- `ls App/migrations_pg | tail -3 | cat` ends with `00015_lead_reduced_guests.sql` and no `00016_*` file exists. If a `00016_*` exists: STOP (the number is taken).

**Step B1. Create `App/migrations_pg/00016_state_transition_observe.sql`** with exactly this content (169 lines, ends with a newline):

```sql
-- +goose Up
-- Brief 1120: observe mode. One trigger per round 1 state column records a move
-- that its Python transition table does not list, into state_transition_violation.
-- It never blocks a write: the insert is wrapped in an exception handler.
-- PostgreSQL only (owner decision 2026-11-11): no SQLite twin, no schema_migrations
-- row (precedent 00008). The allowed moves are the trigger arguments 'from>to',
-- '' standing for NULL; tests/test_sm_state_observe_trigger.py keeps them equal to
-- the Python tables. Every statement can run again (test resets re-apply all files).
-- Each CREATE TRIGGER is its own StatementBegin block: db._statements splits with
-- sqlite3.complete_statement, which waits for an END; after CREATE TRIGGER.
-- CREATE TRIGGER locks each table against writes until the apply commits: wait at
-- most 5 seconds for a lock, else the whole apply rolls back and deploy.sh stops
-- before it touches the running stack.
SET LOCAL lock_timeout = '5s';
CREATE TABLE IF NOT EXISTS state_transition_violation (
    id          BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    table_name  TEXT NOT NULL,
    column_name TEXT NOT NULL,
    row_id      BIGINT,
    old_state   TEXT,
    new_state   TEXT
);

-- +goose StatementBegin
CREATE OR REPLACE FUNCTION ubyhost_state_transition_observe() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  v_old text := to_jsonb(OLD) ->> TG_ARGV[0];
  v_new text := to_jsonb(NEW) ->> TG_ARGV[0];
BEGIN
  IF (COALESCE(v_old, '') || '>' || COALESCE(v_new, '')) = ANY (TG_ARGV[2:]) THEN
    RETURN NULL;
  END IF;
  BEGIN
    INSERT INTO state_transition_violation (table_name, column_name, row_id, old_state, new_state)
    VALUES (TG_TABLE_NAME, TG_ARGV[0], (to_jsonb(NEW) ->> TG_ARGV[1])::bigint, v_old, v_new);
  EXCEPTION WHEN OTHERS THEN
    NULL;
  END;
  RETURN NULL;
END $$;
-- +goose StatementEnd

DROP TRIGGER IF EXISTS sm_observe_guest_submit_state ON guest;
-- +goose StatementBegin
CREATE TRIGGER sm_observe_guest_submit_state AFTER UPDATE OF submit_state ON guest
    FOR EACH ROW WHEN (OLD.submit_state IS DISTINCT FROM NEW.submit_state)
    EXECUTE FUNCTION ubyhost_state_transition_observe(
        'submit_state', 'id',
        'blocked>error', 'blocked>not_required', 'blocked>pending', 'blocked>sent',
        'error>blocked', 'error>not_required', 'error>pending', 'error>sent',
        'not_required>blocked', 'not_required>error', 'not_required>pending', 'not_required>sent',
        'pending>blocked', 'pending>error', 'pending>not_required', 'pending>sent',
        'sent>blocked', 'sent>error', 'sent>pending');
-- +goose StatementEnd
DROP TRIGGER IF EXISTS sm_observe_submission_state ON submission;
-- +goose StatementBegin
CREATE TRIGGER sm_observe_submission_state AFTER UPDATE OF state ON submission
    FOR EACH ROW WHEN (OLD.state IS DISTINCT FROM NEW.state)
    EXECUTE FUNCTION ubyhost_state_transition_observe(
        'state', 'id',
        '>running', 'running>error', 'running>ok', 'running>ok_duplicate',
        'running>outcome_unknown', 'running>partial', 'running>transport_error');
-- +goose StatementEnd
DROP TRIGGER IF EXISTS sm_observe_reservation_claim_state ON reservation_claim;
-- +goose StatementBegin
CREATE TRIGGER sm_observe_reservation_claim_state AFTER UPDATE OF state ON reservation_claim
    FOR EACH ROW WHEN (OLD.state IS DISTINCT FROM NEW.state)
    EXECUTE FUNCTION ubyhost_state_transition_observe(
        'state', 'reservation_id',
        '>unclaimed', 'claimed>claimed', 'claimed>unclaimed', 'provisional>claimed',
        'provisional>provisional', 'provisional>unclaimed', 'unclaimed>provisional', 'unclaimed>unclaimed');
-- +goose StatementEnd
DROP TRIGGER IF EXISTS sm_observe_door_code_state ON door_code;
-- +goose StatementBegin
CREATE TRIGGER sm_observe_door_code_state AFTER UPDATE OF state ON door_code
    FOR EACH ROW WHEN (OLD.state IS DISTINCT FROM NEW.state)
    EXECUTE FUNCTION ubyhost_state_transition_observe(
        'state', 'id',
        'issued>expired', 'issued>revoke_pending', 'issuing>expired', 'issuing>failed',
        'issuing>issued', 'issuing>pending', 'issuing>retrying', 'pending>issuing',
        'pending>revoked', 'retrying>issuing', 'retrying>revoked', 'revoke_failed>issued',
        'revoke_pending>issued', 'revoke_pending>revoke_failed', 'revoke_pending>revoked');
-- +goose StatementEnd
DROP TRIGGER IF EXISTS sm_observe_cleaning_code_state ON cleaning_code;
-- +goose StatementBegin
CREATE TRIGGER sm_observe_cleaning_code_state AFTER UPDATE OF state ON cleaning_code
    FOR EACH ROW WHEN (OLD.state IS DISTINCT FROM NEW.state)
    EXECUTE FUNCTION ubyhost_state_transition_observe(
        'state', 'id',
        'active>active', 'active>detached', 'active>revoke_pending', 'active>revoked',
        'failed>retrying', 'failed>revoke_pending', 'issuing>active', 'issuing>failed',
        'issuing>retrying', 'issuing>revoke_pending', 'pending>issuing', 'pending>revoke_pending',
        'pending>revoked', 'retrying>issuing', 'retrying>revoke_pending', 'revoke_failed>revoke_pending',
        'revoke_pending>revoke_pending', 'revoke_pending>revoking', 'revoked>revoke_pending', 'revoking>revoke_failed',
        'revoking>revoke_pending', 'revoking>revoked');
-- +goose StatementEnd
DROP TRIGGER IF EXISTS sm_observe_site_booking_status ON site_booking;
-- +goose StatementBegin
CREATE TRIGGER sm_observe_site_booking_status AFTER UPDATE OF status ON site_booking
    FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION ubyhost_state_transition_observe(
        'status', 'id',
        'cancelled>refunded', 'expired>cancelled', 'expired>clash_refunded', 'expired>paid',
        'paid>cancelled', 'paid>clash_refunded', 'paid>refunded', 'pending>clash_refunded',
        'pending>expired', 'pending>paid', 'requested>cancelled', 'requested>expired',
        'requested>paid');
-- +goose StatementEnd
DROP TRIGGER IF EXISTS sm_observe_payment_request_status ON payment_request;
-- +goose StatementBegin
CREATE TRIGGER sm_observe_payment_request_status AFTER UPDATE OF status ON payment_request
    FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION ubyhost_state_transition_observe(
        'status', 'id',
        'awaiting_payment>cancelled', 'awaiting_payment>expired', 'awaiting_payment>paid', 'cancelled>paid',
        'draft>cancelled', 'draft>sent', 'expired>paid', 'sent>awaiting_payment',
        'sent>cancelled', 'sent>expired', 'sent>paid');
-- +goose StatementEnd
DROP TRIGGER IF EXISTS sm_observe_email_outbox_state ON email_outbox;
-- +goose StatementBegin
CREATE TRIGGER sm_observe_email_outbox_state AFTER UPDATE OF state ON email_outbox
    FOR EACH ROW WHEN (OLD.state IS DISTINCT FROM NEW.state)
    EXECUTE FUNCTION ubyhost_state_transition_observe(
        'state', 'id',
        'queued>failed', 'queued>sending', 'sending>failed', 'sending>queued',
        'sending>sent');
-- +goose StatementEnd
DROP TRIGGER IF EXISTS sm_observe_push_outbox_state ON push_outbox;
-- +goose StatementBegin
CREATE TRIGGER sm_observe_push_outbox_state AFTER UPDATE OF state ON push_outbox
    FOR EACH ROW WHEN (OLD.state IS DISTINCT FROM NEW.state)
    EXECUTE FUNCTION ubyhost_state_transition_observe(
        'state', 'id',
        'queued>failed', 'queued>sent');
-- +goose StatementEnd
DROP TRIGGER IF EXISTS sm_observe_ad_click_send_state ON ad_click;
-- +goose StatementBegin
CREATE TRIGGER sm_observe_ad_click_send_state AFTER UPDATE OF send_state ON ad_click
    FOR EACH ROW WHEN (OLD.send_state IS DISTINCT FROM NEW.send_state)
    EXECUTE FUNCTION ubyhost_state_transition_observe(
        'send_state', 'id',
        '>pending', 'pending>expired', 'pending>sending', 'pending>withdrawn',
        'sending>failed', 'sending>pending', 'sending>sent', 'sending>withdrawn');
-- +goose StatementEnd
DROP TRIGGER IF EXISTS sm_observe_guide_import_status ON guide_import;
-- +goose StatementBegin
CREATE TRIGGER sm_observe_guide_import_status AFTER UPDATE OF status ON guide_import
    FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION ubyhost_state_transition_observe(
        'status', 'id',
        'done>expired', 'done>failed', 'done>used', 'queued>failed',
        'queued>running', 'running>done', 'running>failed');
-- +goose StatementEnd

-- +goose Down
DROP TRIGGER IF EXISTS sm_observe_guide_import_status ON guide_import;
DROP TRIGGER IF EXISTS sm_observe_ad_click_send_state ON ad_click;
DROP TRIGGER IF EXISTS sm_observe_push_outbox_state ON push_outbox;
DROP TRIGGER IF EXISTS sm_observe_email_outbox_state ON email_outbox;
DROP TRIGGER IF EXISTS sm_observe_payment_request_status ON payment_request;
DROP TRIGGER IF EXISTS sm_observe_site_booking_status ON site_booking;
DROP TRIGGER IF EXISTS sm_observe_cleaning_code_state ON cleaning_code;
DROP TRIGGER IF EXISTS sm_observe_door_code_state ON door_code;
DROP TRIGGER IF EXISTS sm_observe_reservation_claim_state ON reservation_claim;
DROP TRIGGER IF EXISTS sm_observe_submission_state ON submission;
DROP TRIGGER IF EXISTS sm_observe_guest_submit_state ON guest;
DROP FUNCTION IF EXISTS ubyhost_state_transition_observe();
DROP TABLE IF EXISTS state_transition_violation;
```

Commands: `grep -c "^CREATE TRIGGER sm_observe_" App/migrations_pg/00016_state_transition_observe.sql | tail -30` prints `11`. `wc -l App/migrations_pg/00016_state_transition_observe.sql | tail -30` prints `169`.

**Step B2. Create `App/tests/test_sm_state_observe_trigger.py`** with exactly this content:

```python
"""Brief 1120: the observe triggers allow exactly the moves the round 1 tables list.

Runs on SQLite (no database needed): it reads the goose file as text and compares
each trigger's 'from>to' arguments ('' stands for NULL) with the Python table that
owns the column. A move added to one side only fails here, so the two cannot drift.
"""
from __future__ import annotations

import re
from pathlib import Path

from app import (
    booking_site,
    claim,
    cleaning_codes,
    db,
    door_codes,
    guest_guide_import,
    mail,
    meta_capi,
    payment_request,
    push,
    reporting,
)

GOOSE_FILE = (
    Path(__file__).resolve().parent.parent / "migrations_pg" / "00016_state_transition_observe.sql"
)

# (table, state column, key column) -> the round 1 table that lists its moves.
MACHINES = {
    ("guest", "submit_state", "id"): reporting.TRANSITIONS,
    ("submission", "state", "id"): reporting.SUBMISSION_TRANSITIONS,
    ("reservation_claim", "state", "reservation_id"): claim.TRANSITIONS,
    ("door_code", "state", "id"): door_codes.TRANSITIONS,
    ("cleaning_code", "state", "id"): cleaning_codes.TRANSITIONS,
    ("site_booking", "status", "id"): booking_site._TRANSITIONS,
    ("payment_request", "status", "id"): payment_request._TRANSITIONS,
    ("email_outbox", "state", "id"): mail.OUTBOX_TRANSITIONS,
    ("push_outbox", "state", "id"): push.PUSH_TRANSITIONS,
    ("ad_click", "send_state", "id"): meta_capi.SEND_TRANSITIONS,
    ("guide_import", "status", "id"): guest_guide_import.IMPORT_TRANSITIONS,
}

TRIGGER = re.compile(
    r"CREATE TRIGGER (\w+) AFTER UPDATE OF (\w+) ON (\w+)\n"
    r"    FOR EACH ROW WHEN \(OLD\.(\w+) IS DISTINCT FROM NEW\.(\w+)\)\n"
    r"    EXECUTE FUNCTION ubyhost_state_transition_observe\(([^)]*)\);"
)


def _text() -> str:
    return GOOSE_FILE.read_text(encoding="utf-8")


def _up() -> str:
    return _text().split("-- +goose Down")[0]


def _down() -> str:
    return _text().split("-- +goose Down")[1]


def _pairs(table) -> set:
    """'from>to' for every move; None (no row yet, or a NULL column) is ''."""
    return {
        f"{source or ''}>{target or ''}" for source, targets in table.items() for target in targets
    }


def _declared() -> dict:
    found = {}
    for name, column, table, old_column, new_column, body in TRIGGER.findall(_up()):
        args = re.findall(r"'([^']*)'", body)
        assert name == f"sm_observe_{table}_{column}"
        assert old_column == new_column == column == args[0], name
        assert len(args[2:]) == len(set(args[2:])), f"{name} repeats a pair"
        found[(table, column, args[1])] = set(args[2:])
    return found


def test_every_round_1_machine_has_one_trigger_with_exactly_its_moves():
    declared = _declared()
    assert set(declared) == set(MACHINES)
    for key, table in MACHINES.items():
        assert declared[key] == _pairs(table), key


def test_each_trigger_is_dropped_first_and_is_its_own_statement_block():
    up = _up()
    for table, column, _key in MACHINES:
        name = f"sm_observe_{table}_{column}"
        assert (
            f"DROP TRIGGER IF EXISTS {name} ON {table};\n"
            f"-- +goose StatementBegin\nCREATE TRIGGER {name} "
        ) in up, name
    assert up.count("-- +goose StatementBegin") == len(MACHINES) + 1
    assert up.count("-- +goose StatementEnd") == len(MACHINES) + 1


def test_the_python_goose_reader_sees_one_statement_per_object():
    # SET LOCAL, the table, the function, then one DROP and one CREATE per trigger
    assert len(db._goose_up_statements(_text())) == 3 + 2 * len(MACHINES)


def test_down_drops_every_trigger_the_function_and_the_table():
    down = _down()
    for table, column, _key in MACHINES:
        assert f"DROP TRIGGER IF EXISTS sm_observe_{table}_{column} ON {table};" in down
    assert "DROP FUNCTION IF EXISTS ubyhost_state_transition_observe();" in down
    assert "DROP TABLE IF EXISTS state_transition_violation;" in down


def test_the_trigger_can_never_make_the_write_fail():
    function = _up().split("CREATE OR REPLACE FUNCTION ubyhost_state_transition_observe()")[1]
    function = function.split("-- +goose StatementEnd")[0]
    assert "  EXCEPTION WHEN OTHERS THEN\n    NULL;\n  END;" in function
    assert "RAISE" not in function
    assert function.count("RETURN NULL;") == 2
```

Command: `cd App && .venv/bin/python -m pytest tests/test_sm_state_observe_trigger.py -q --tb=short -x 2>&1 | tail -30`. Expected: `5 passed`. If the first test fails with a table key: one pair in Step B1 differs from that Python table. Compare it once against section 2.4. If they still differ, STOP; never change a Python table.

**Step B3. Append to `App/tests/test_goose_migrations.py`.** The file now ends with Part A's test, whose last line is `    assert db.postgres_schema_status()["current"] is False` (check with `tail -1`; if it differs: STOP). Append exactly the following. The first two lines are empty lines; the file ends with a newline.

```python


def _violations() -> list:
    conn = db.connect()
    try:
        return conn.execute_native(
            "SELECT table_name, column_name, row_id, old_state, new_state "
            "FROM state_transition_violation ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


def _outbox():
    conn = db.connect()
    try:
        return conn.execute_native(
            "SELECT id, state FROM email_outbox WHERE idempotency_key = 'brief-1120'"
        ).fetchone()
    finally:
        conn.close()


def _outbox_row() -> None:
    _run(
        "INSERT INTO email_outbox (idempotency_key, kind, state, created_at, updated_at) "
        "VALUES ('brief-1120', 'test', 'queued', '2026-11-11T00:00:00+00:00', '2026-11-11T00:00:00+00:00')"
    )


def _set_state(state: str, extra: str = "") -> None:
    _run(f"UPDATE email_outbox SET state = '{state}'{extra} WHERE idempotency_key = 'brief-1120'")


@PG_ONLY
def test_observe_trigger_records_only_a_move_the_table_does_not_allow(pg_goose):
    # Brief 1120. email_outbox needs no other row; its table is mail.OUTBOX_TRANSITIONS.
    _outbox_row()
    _set_state("sending")  # allowed
    _set_state("sending", ", attempts = 1")  # same state: the trigger does not fire
    _set_state("sent")  # allowed
    assert _violations() == []
    _set_state("queued")  # sent is final: not allowed
    rows = _violations()
    assert [(r["table_name"], r["column_name"], r["old_state"], r["new_state"]) for r in rows] == [
        ("email_outbox", "state", "sent", "queued")
    ]
    outbox = _outbox()
    assert outbox["state"] == "queued"  # the disallowed write still happened
    assert rows[0]["row_id"] == outbox["id"]


@PG_ONLY
def test_observe_trigger_never_fails_the_write_even_without_its_log_table(pg_goose):
    _outbox_row()
    _run("DROP TABLE state_transition_violation")
    _set_state("sent")  # queued to sent is not allowed, and the log insert itself fails
    assert _outbox()["state"] == "sent"


@PG_ONLY
def test_retention_deletes_violations_older_than_ninety_days(pg_goose):
    from datetime import date

    from app import retention

    _run(
        "INSERT INTO state_transition_violation (at, table_name, column_name, row_id, old_state, new_state) "
        "VALUES (now() - interval '100 days', 'email_outbox', 'state', 1, 'sent', 'queued'), "
        "(now() - interval '1 day', 'email_outbox', 'state', 2, 'sent', 'queued')"
    )
    assert retention._state_violation_step(date.today(), True, None) == 1  # dry run only counts
    assert retention._state_violation_step(date.today(), False, 7) == 0  # global table: owner runs skip
    assert len(_violations()) == 2
    assert retention._state_violation_step(date.today(), False, None) == 1
    assert [row["row_id"] for row in _violations()] == [2]
```

Command: run it after Step B12 (it needs the retention step). Nothing to run now.

**Step B4. Edit `App/tests/test_db_postgres.py` line 251.** Anchor: `grep -nF 'status["actual_tables"] == 71  # + job (goose 00003, PostgreSQL only)' App/tests/test_db_postgres.py | tail -30` (one line, 251). Replace the line with:

```python
    assert status["expected_tables"] == 70 and status["actual_tables"] == 72  # + job (goose 00003), state_transition_violation (00016)
```

**Step B5. Edit `App/tests/test_db_postgres.py` line 252.** Anchor: `grep -nF 'status["extra_tables"] == 1  # job' App/tests/test_db_postgres.py | tail -30` (one line, 252). Replace the line with:

```python
    assert status["missing_tables"] == 0 and status["extra_tables"] == 2  # job, state_transition_violation
```

**Step B6. Edit `App/tests/test_db_postgres.py` line 278.** Anchor: `grep -nF '    assert triggers == {' App/tests/test_db_postgres.py | tail -30` (one line, 278). Replace that line with:

```python
    assert {name for name in triggers if not name.startswith("sm_observe_")} == {
```

**Step B7. Edit `App/tests/test_db_postgres.py` after line 285.** Anchor: `grep -nF '    assert database == TARGET["database"]' App/tests/test_db_postgres.py | tail -30`. Expected: one line, 286, directly after the line `    }` that closes the trigger set. Insert this line **before** line 286:

```python
    assert len([name for name in triggers if name.startswith("sm_observe_")]) == 11  # brief 1120
```

Command: `sed -n 250,253p App/tests/test_db_postgres.py; sed -n 276,288p App/tests/test_db_postgres.py | cat`. Expected: the four edited lines in place, the six invoice names unchanged.

**Step B8. Edit `App/app/retention.py`: personal-data line.** Anchor (one line, 38): `grep -nF '# purged with the row 7 days after done/dead (jobqueue.purge).' App/app/retention.py | tail -30`. Insert after line 38 an empty line and then these four lines:

```python
# 1120: state_transition_violation (PostgreSQL only, goose 00016) holds a table and
# column name, the row's key and two state words. For guest, reservation_claim and
# ad_click rows the key points at a guest, a stay or an account. No name, address or
# document. Deleted STATE_VIOLATION_DAYS after it was recorded (state-violation step).
```

**Step B9. Edit `App/app/retention.py`: the constant.** Anchor (one line): `grep -nF 'HAVEL_GAP_DAYS = 90  # havel_gap: redacted questions Havel could not answer' App/app/retention.py | tail -30`. Insert directly after it:

```python
STATE_VIOLATION_DAYS = 90  # state_transition_violation (1120): observed state moves
```

**Step B10. Edit `App/app/retention.py`: the step.** Anchor (one line): `grep -nF 'def _acceptance_retention_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:' App/app/retention.py | tail -30`. Insert **before** that line (the two empty lines that already sit above it stay above your new function; add two empty lines after it):

```python
def _state_violation_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    """Brief 1120: delete observed state moves after 90 days. PostgreSQL only, global only."""
    if owner_user_id is not None or getattr(config, "DB_BACKEND", "sqlite") != "postgresql":
        return 0
    cutoff = f"{(today - timedelta(days=STATE_VIOLATION_DAYS)).isoformat()}T00:00:00+00:00"
    count = _scalar(
        "SELECT COUNT(*) AS n FROM state_transition_violation WHERE at < CAST(? AS timestamptz)",
        (cutoff,),
    )
    if not dry_run and count:
        db.execute(
            "DELETE FROM state_transition_violation WHERE at < CAST(? AS timestamptz)", (cutoff,)
        )
    return count


```

**Step B11. Edit `App/app/retention.py`: `STEPS`.** Anchor (one line): `grep -nF '    ("havel_gap", _havel_gap_step),' App/app/retention.py | tail -30`. Insert directly after it:

```python
    ("state_violations", _state_violation_step),
```

**Step B12. Edit `App/app/retention.py`: the cutoff.** Anchor (one line): `grep -nF '        "havel_gap": f"created before {(today - timedelta(days=HAVEL_GAP_DAYS)).isoformat()}",' App/app/retention.py | tail -30`. Insert directly after it:

```python
        "state_violations": f"recorded before {(today - timedelta(days=STATE_VIOLATION_DAYS)).isoformat()}",
```

Command: `cd App && .venv/bin/python -m pytest tests/test_retention.py tests/test_retention_alignment.py tests/test_retention_job.py -q --tb=short -x 2>&1 | tail -30`. Expected: no failure (on SQLite the step returns 0 and writes its audit line with the cutoff).
Then: `cd App && .venv/bin/python -m pytest tests/test_goose_migrations.py -q --tb=short -x -rs 2>&1 | tail -30`. Expected: `2 passed`, the PostgreSQL tests skipped with the stated reason.

**Step B13. Edit `docs/privacy/RETENTION.md`.** Anchor (one line, 35): `grep -nF '| Havel gap questions | `havel_gap` |' docs/privacy/RETENTION.md | tail -30`. Insert directly after it:

```
| Observed state moves (table and column name, the row's key, old and new state word; for a guest, claim or ad-click row the key points at that guest, stay or account) | `state_transition_violation` (PostgreSQL only) | recorded | 90 days (1120) | `retention.py` state-violation step | Storage limitation |
```

**Step B14. Test-map rows.** Commands in section 6, Part B. Expected as stated there.

**Step B15. Context lint.** `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: no error. Report any warning.

**Step B16. Report and PR.** Add `## Part B` to `docs/tasks/1120-report.md` (section 9) and set the Status line to `review (Part B)`. Open one PR titled `1120 part B: observe triggers for the round 1 state columns (goose 00016)`. Its body says: "HIGH RISK migration. CI test-postgres and test-postgres-full must pass with 0 skipped in test_db_postgres.py. Deploy applies 00016 automatically (deploy.sh 219-227)."

## 5. Do not touch

- Every writer: `App/app/reporting.py`, `claim.py`, `door_codes.py`, `cleaning_codes.py`, `booking_site.py`, `payment_request.py`, `mail.py`, `push.py`, `meta_capi.py`, `guest_guide_import.py`, `signup.py`, and every file under `go/`. Never change a transition table to make a test pass.
- `App/app/db_postgres.py` (`PG_TRIGGER_NAMES`, `PG_TRIGGERS`), `App/app/migrations/` (no SQLite file), `App/migrations_pg/00001` to `00015`, `db.SCHEMA`, `db.ADDED_COLUMNS`.
- `docs/context/rules.md`, `docs/context/decisions.md` (the orchestrator's).
- Hard rules: 1 (filing correctness wins: the trigger must never fail a write; never add `RAISE`), 2 (the retention line of Steps B8-B13), 3 (no production data in the repo; the owner's pasted query result holds only state words, counts and times), 4 (no dependency), 5 (bent only as Owner decision 1 says), 8 (never push to main).

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`. PostgreSQL tests skip for the executor; CI runs them.

Part A:
- `.venv/bin/python -m pytest tests/test_goose_migrations.py -q --tb=short -x -rs 2>&1 | tail -30`: `2 passed`, the rest skipped.
- `.venv/bin/python -m pytest tests/test_migrations.py tests/test_db_upgrade.py -q --tb=short -x 2>&1 | tail -30`: no failure.

Part B:
- `.venv/bin/python -m pytest tests/test_sm_state_observe_trigger.py -q --tb=short -x 2>&1 | tail -30`: `5 passed`.
- `.venv/bin/python -m pytest tests/test_sm_*.py -q --tb=short -x 2>&1 | tail -30`: no failure (the round 1 pins still hold; no table changed).
- `.venv/bin/python -m pytest tests/test_goose_migrations.py tests/test_migrations.py tests/test_db_upgrade.py tests/test_db_postgres.py -q --tb=short -x -rs 2>&1 | tail -30`: no failure; PostgreSQL tests skipped with the stated reason.
- `.venv/bin/python -m pytest tests/test_retention.py tests/test_retention_alignment.py tests/test_retention_job.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -30`: no failure.

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

Part A:
- [ ] Step A0 passed (decision line present, no conflict markers).
- [ ] `grep -c 'startswith("sm_observe_")' App/app/db.py` prints `1`.
- [ ] `test_goose_migrations.py`: `2 passed`, the rest skipped (CI runs the new test).
- [ ] `git diff --stat main` shows only the Part A files of section 3.

Part B:
- [ ] Step B0 passed (gate `yes`, Part A on main, `00016` free).
- [ ] The goose file has 11 `CREATE TRIGGER sm_observe_` lines and 169 lines in total.
- [ ] `test_sm_state_observe_trigger.py`: `5 passed`.
- [ ] `grep -n '"state_violations"' App/app/retention.py` prints two lines (`STEPS` and `_cutoffs`).
- [ ] `grep -c 'state_transition_violation' docs/privacy/RETENTION.md` prints `1`.
- [ ] `git diff --stat main` shows only the Part B files of section 3.

## 8. Stop and ask

Stop, and write the report, if:

- a gate (A0, B0) fails;
- an excerpt or anchor is not found, or a grep count differs from the stated one;
- a test fails twice;
- the parity test fails after one careful comparison (never edit a Python table);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push to main, merge, secrets, SSH, deploy or `pg_schema.py apply` (hand that to the owner: "Owner steps").

## 9. Report

`docs/tasks/1120-report.md` (600 tokens at most per part), one section per part, with:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Rollback

- **Part B's deploy fails its health check:** `deploy.sh` rolls back to `ubyhost:previous`, which is Part A's image. That image accepts the triggers, so the site comes back. The triggers stay and keep recording; that is harmless.
- **Stop observing (triggers off), on the server**, from `/opt/ubyhost/deploy/lightsail`:

  ```bash
  docker compose exec -T postgres psql -U ubyhost -d ubyhost -v ON_ERROR_STOP=1 <<'SQL'
  BEGIN;
  SET LOCAL lock_timeout = '5s';
  DROP TRIGGER IF EXISTS sm_observe_guide_import_status ON guide_import;
  DROP TRIGGER IF EXISTS sm_observe_ad_click_send_state ON ad_click;
  DROP TRIGGER IF EXISTS sm_observe_push_outbox_state ON push_outbox;
  DROP TRIGGER IF EXISTS sm_observe_email_outbox_state ON email_outbox;
  DROP TRIGGER IF EXISTS sm_observe_payment_request_status ON payment_request;
  DROP TRIGGER IF EXISTS sm_observe_site_booking_status ON site_booking;
  DROP TRIGGER IF EXISTS sm_observe_cleaning_code_state ON cleaning_code;
  DROP TRIGGER IF EXISTS sm_observe_door_code_state ON door_code;
  DROP TRIGGER IF EXISTS sm_observe_reservation_claim_state ON reservation_claim;
  DROP TRIGGER IF EXISTS sm_observe_submission_state ON submission;
  DROP TRIGGER IF EXISTS sm_observe_guest_submit_state ON guest;
  DROP FUNCTION IF EXISTS ubyhost_state_transition_observe();
  COMMIT;
  SQL
  ```

  Keep the table: the nightly retention step reads it and would fail without it. The app stays `current`, because Part A ignores `sm_observe_*` triggers, missing ones included. Goose still lists 16 as applied, so nothing reinstalls them. To remove them for good, the orchestrator writes a later goose file that drops them.
- **Never roll the app image back to a build older than Part A while the triggers exist.** That image refuses to start (strict trigger check). Run the block above first.
- SQLite rollback (`pg-cutover.sh rollback`) is unaffected: SQLite never had these objects.

## Open questions

1. **Two PRs instead of one** (`db.py` lines 1338-1362, `deploy.sh` lines 40-41 and 219-227, `rules.md` line 47). Without Part A first, a failed deploy of Part B would leave the site down. If the orchestrator prefers two briefs, split at "Part B gate".
2. **`rules.md` line 40 "No new triggers"** is bent as well as hard rule 5. The decision line should name both. `rules.md` line 37 is stale (as 1111 noted).
3. **Moves that will show up at once, by design:** `claim.start_claim` turning `claimed` back into `provisional` (the 1115 fault; `claim.py` `TRANSITIONS` lists only `claimed>claimed`, `claimed>unclaimed`) is recorded until 1115 lands. Any fault from 1114, 1116 or 1117 that writes a move missing from its table shows up the same way. That confirms those briefs.
4. **Not covered:** `billing_account.status` (`App/app/billing.py` line 18 `TRANSITIONS`, already enforced in Python at line 170, not a round 1 machine), `reservation.status`, `lock_account.status`. Add them in round 4 if wanted.
5. **Main working tree: `docs/context/decisions.md` lines 64-68 hold unresolved merge-conflict markers** (`<<<<<<< HEAD` ... `>>>>>>> origin/main`). Step A0 stops on them. The orchestrator fixes them before writing decision 1's line.
6. **`to_jsonb` reads the whole row** (section 2.6), large columns included. If production ever shows trigger time in slow-query logs, a later goose file can give `email_outbox` its own small function that reads `OLD.state` and `NEW.state` directly.
7. **Sanity-run by the brief writer** on a scratch PostgreSQL 16 (outside both trees): every goose Up file 00001-00015 plus this file applied cleanly. The file applied a second time with no error (idempotent), and Down then Up worked. The function and 11 triggers came out as expected. Allowed, same-state and disallowed updates gave 0, 0 and 1 violation rows. The disallowed write stayed in place. With the log table renamed away, a disallowed write still succeeded. A rolled-back write left no row. NULL to `pending` was allowed, `sending` to NULL was recorded with `new_state` NULL. Each of the 25 statements from a copy of `db._goose_up_statements` ran on its own. The parity test logic passed against the real tables (via `ast`) and failed when one pair was added. Not run: the app's pytest, the goose binary, and the Go tests (no `.venv`, no goose here). CI runs them.

## Risk list (for the reviewer)

Read in full:
- `App/migrations_pg/00016_state_transition_observe.sql`: each pair list against its table in section 2.4; the function (no `RAISE`, exception block only around the insert, `RETURN NULL`); `SET LOCAL lock_timeout`; Down drops all 11 triggers, the function and the table.
- `App/app/db.py` (the Part A hunk): only `sm_observe_`-prefixed names are ignored; the six invoice guards are still required exactly.
- `App/tests/test_sm_state_observe_trigger.py`: `MACHINES` names the right table for each column, and the right key (`reservation_id` for `reservation_claim`).
- `App/app/retention.py` hunks: the step returns 0 on SQLite and on owner-scoped runs; `CAST(? AS timestamptz)`.
- `App/tests/test_db_postgres.py` hunks: the counts 72, 2 and 11.

## Owner steps

Part A:
1. When CI is green on the Part A PR, merge it with `scripts/merge-pr-on-green.sh` as usual. It deploys by itself.
2. Wait for the deploy to finish. On the server, in `/opt/ubyhost/deploy/lightsail`, run `./scripts/status.sh`. Expected: healthy.
3. Tell the orchestrator: "1120 part A is live". The orchestrator changes the Part B gate line to `yes`.

Part B:
1. When CI is green on the Part B PR (including the jobs `test-postgres` and `test-postgres-full`), merge it with `scripts/merge-pr-on-green.sh`. The deploy applies goose 00016 by itself (`deploy.sh`, "Applying PostgreSQL goose migrations"). If the deploy says `Goose apply failed`, nothing changed and the old site keeps running: copy the last 30 lines of the deploy output to the orchestrator. A `lock timeout` there only means a table was busy; run the deploy again later.
2. On the server, in `/opt/ubyhost/deploy/lightsail`, check the triggers. Copy this line, paste it, press Enter:
   `docker compose exec -T postgres psql -U ubyhost -d ubyhost -Atc "SELECT count(*) FROM pg_trigger WHERE tgname LIKE 'sm_observe_%';"`
   Expected: `11`.
3. Run `./scripts/status.sh`. Expected: healthy.
4. **To look at what was recorded** (read-only; shows only state words, counts and times, never a row key, so the result may be pasted to the orchestrator). Copy the whole block, paste it, press Enter:

   ```bash
   docker compose exec -T postgres psql -U ubyhost -d ubyhost -P pager=off <<'SQL'
   SET default_transaction_read_only = on;
   SELECT table_name, column_name,
          COALESCE(old_state, '<NULL>') AS old_state, COALESCE(new_state, '<NULL>') AS new_state,
          COUNT(*) AS n, MIN(at) AS first_seen, MAX(at) AS last_seen
   FROM state_transition_violation
   GROUP BY 1, 2, 3, 4
   ORDER BY 1, 2, 3, 4;
   SQL
   ```

5. **What the result means.** `(0 rows)`: every state change since the deploy was a move the tables allow. Good. Run it again weekly. A row means a writer (Python or Go) made that move `n` times. Nothing was blocked and no guest was affected. Either the code has a fault, or the table is missing a move the code is meant to make. Paste the result to the orchestrator, who writes a brief that fixes either the writer or the table. Rows for `guest.submit_state` or `submission.state` are about police filing: send them the same day. Expect `reservation_claim provisional` rows from `claimed` until brief 1115 is merged.
6. After about a month with no rows for a table, tell the orchestrator. That table can then move to round 4 ("refuse").
