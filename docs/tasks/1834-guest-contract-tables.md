# 1834: Guest contract tables `guest_form_snapshot` and `guest_inbox`, and the `ubyhost_guest` role script

Status: todo
Depends on: 1830-1833 merged (plan order) | Base commit: current tip of the working branch | Branch: task/1834-guest-contract-tables
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (schema of the guest submission path that feeds UbyPort filing, plus a database role; exact diffs only; orchestrator reads the full diff before ready)
Plan: [guest-form-isolation](../plans/guest-form-isolation.md) sections 2, 3, 5 and 11 (D4).

> **One PR mode.** Commit each step as `1834 step k`. Never push, merge or deploy. Hand the owner the steps in "Owner steps".

## Open questions (orchestrator answers before execute)

Step 0 stops until each line below carries `Answer:`.

1. **Password for `ubyhost_guest`.** The `postgres` service runs `POSTGRES_HOST_AUTH_METHOD: trust` over the socket volume and has no network (`deploy/lightsail/docker-compose.yml` line 20; `docs/ENVIRONMENT.md` "Database"). `ubyhost_app` has no password for that reason (`deploy/lightsail/scripts/pg-app-role.sql` header). A password on `ubyhost_guest` would be ignored unless `pg_hba` changes, which is outside this plan. Recommended answer: no password; the role exists for its connection limit, timeout and grants, not for authentication. `UBYHOST_GUEST_DATABASE_URL` then holds no secret. If the answer is "password required", this brief is replaced (a `pg_hba` change needs its own brief).
2. **Grants differ slightly from plan section 2.** Plan: `INSERT` and `SELECT (id, token hash, status)` on `guest_inbox`. This brief grants `INSERT` on the six columns the guest program writes only (stricter), and `SELECT (id, idempotency_key, token_hash, reservation_id, status, received_at)`: `idempotency_key` because `INSERT ... ON CONFLICT (idempotency_key) DO NOTHING` needs SELECT on the arbiter column, `reservation_id` because the form counts its own rows per stay (plan section 4, "2 of 3 guests registered"), `received_at` because a repeated submission must show the original "Received" time. Recommended answer: approve.

Answers:

1. Answer (orchestrator, 2026-11-17): no password; socket trust as for `ubyhost_app`.
2. Answer (orchestrator, 2026-11-17): approved, the grants in this brief.

Note: compose sets `max_connections=50`, not 20 as the plan says; CONNECTION LIMIT 3 still holds.

## 1. Objective

Add the two contract tables of plan section 3 as goose migration `00020`, and a superuser script that creates the role `ubyhost_guest` with exactly the plan's grants, `CONNECTION LIMIT 3` and `statement_timeout` 2 s. Nothing reads or writes these tables yet; later briefs (1835-1844) build on the names fixed here.

## 2. Context

Hard rules: 1 filing correctness first (nothing here changes what is filed or when; the tables are empty until 1837); 3 no secrets in the repo; 4 no new dependency; 5 schema change is a new `App/migrations_pg/` file; 8 never push to `main`.

**Why the role is a script and not part of the migration.** Migrations run as `ubyhost_app` in production (`docs/ENVIRONMENT.md` line 307) and in CI (`.github/workflows/ci.yml`, step "App works as the non-superuser role": `export UBYHOST_DATABASE_URL=postgresql://ubyhost_app:...` then `pg_schema.py apply`). `ubyhost_app` is `NOCREATEROLE` (`pg-app-role.sql` line 18), so `CREATE ROLE` in a migration would fail. The existing pattern is a superuser script the owner runs once: `deploy/lightsail/scripts/pg-app-role.sql`. This brief copies that pattern as `pg-guest-role.sql`, and CI runs it after the migrations so a broken grant fails CI.

**Contract surface (later briefs reuse these names exactly):**

- `guest_form_snapshot`: `token_hash` (PK, SHA-256 hex of the link key, the same hash as `App/app/claim.py` `token_hash`: `hashlib.sha256(token.encode("utf-8")).hexdigest()`), `apartment_id`, `contract_version`, `expires_at`, `form_config` (JSONB, Go type `guestcontract.FormConfig` from brief 1835), `updated_at`.
- `guest_inbox`: `id`, `idempotency_key` (unique, 32 lower-case hex), `token_hash`, `reservation_id`, `contract_version`, `received_at` (the legal submission time, plan section 3 rule 2), `payload_enc`, `status` (`new`/`done`/`held`), `host_note`, `attempts`, `processed_at`.
- `payload_enc` is BYTEA holding the ASCII bytes of a Fernet token made with the existing data keys: the same scheme as the `_enc` columns and `db.encrypt_blob` (`App/app/db.py` line 2391, `_fernet().encrypt(data)`), in Go `secure.LoadDataKeys` then `(*secure.MultiFernet).Encrypt` (`go/internal/secure/datakeys.go`, `fernet.go`). Plaintext is gzip of the JSON payload (brief 1835). Decision D4.
- `payload_enc` is nullable: plan section 3 rule 7 deletes the payload 7 days after `done` while the row stays as the idempotency record. A check keeps it non-null unless `done`.
- `reservation_id` has no foreign key on purpose: a stay deleted or moved must turn the row `held` (plan rule 4), never make the guest program's insert fail.
- Timestamps are `TIMESTAMPTZ` (new PostgreSQL-only tables; no SQLite twin, `App/app/migrations/` is frozen at 0045).
- Role `ubyhost_guest`; env var `UBYHOST_GUEST_DATABASE_URL` (documented here, read first by brief 1840).

**Anchors** (verify each with `grep -nF`; if one is missing, STOP):

`App/migrations_pg/00019_job_autovacuum.sql` (the newest file; the next number is `00020`):
```
-- +goose Up
-- Brief 1816. The job table is small (about 12,000 rows) but every row is updated 2-3 times,
```
`App/tests/test_db_postgres.py` lines 260-261:
```
    assert status["expected_tables"] == 70 and status["actual_tables"] == 71  # + job (goose 00003, PostgreSQL only)
    assert status["missing_tables"] == 0 and status["extra_tables"] == 1  # job
```
`.github/workflows/ci.yml`:
```
          python scripts/pg_schema.py apply --expect-database ubyhost_test
          python scripts/pg_schema.py check --expect-database ubyhost_test
```
`docs/ENVIRONMENT.md` line 307:
```
Production sets the user in `UBYHOST_DATABASE_URL` to `ubyhost_app` (`postgresql://ubyhost_app@/ubyhost?host=/var/run/postgresql`) after the owner runs `scripts/pg-app-role.sh apply`; admin scripts keep the `ubyhost` superuser. No separate variable.
```
`go/internal/schema/golden_test.go`: `TestGooseFilesMatchPython` fails when `testdata/goose_statements_golden.json` has fewer files than `App/migrations_pg/`; the fix it prints is `cd App && .venv/bin/python scripts/pg_schema_golden.py` (no database needed).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/migrations_pg/00020_guest_contract.sql` | create | the two tables, checks and indexes |
| `go/internal/schema/testdata/goose_statements_golden.json` | regenerate | by `App/scripts/pg_schema_golden.py`, never by hand |
| `App/tests/test_db_postgres.py` | edit | table counts 71 to 73, extra tables 1 to 3 |
| `deploy/lightsail/scripts/pg-guest-role.sql` | create | role, limits, grants, proof |
| `.github/workflows/ci.yml` | edit | run `pg-guest-role.sql` after the migrations |
| `docs/ENVIRONMENT.md` | edit | one paragraph for `UBYHOST_GUEST_DATABASE_URL` |
| `docs/tasks/1834-report.md` | create | the report (section 9) |

No other file may change.

## 4. Steps

0. **Open questions.** If any line under "Open questions" lacks `Answer:`, or an answer is not the recommended one, STOP and write the report as `blocked`. Then verify every anchor in section 2 with `grep -nF`. Command: `grep -c 'Answer:' docs/tasks/1834-guest-contract-tables.md` (expect 2 or more lines after the orchestrator answered).

1. **Migration.** Create `App/migrations_pg/00020_guest_contract.sql` with exactly:
```sql
-- +goose Up
-- contract: v1
-- Brief 1834, plan docs/plans/guest-form-isolation.md section 3. The only two
-- tables the guest program may touch. Goose-only: no SQLite twin
-- (App/app/migrations/ is frozen at 0045). The role ubyhost_guest and its grants
-- are in deploy/lightsail/scripts/pg-guest-role.sql (migrations run as
-- ubyhost_app, which cannot create roles).
SET LOCAL lock_timeout = '5s';

-- One row per active guest link key (SHA-256 hex, as claim.token_hash).
-- Written by the app in the same transaction as any change that affects the form.
CREATE TABLE IF NOT EXISTS guest_form_snapshot (
    token_hash       TEXT PRIMARY KEY CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    apartment_id     BIGINT NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    contract_version SMALLINT NOT NULL CHECK (contract_version >= 1),
    expires_at       TIMESTAMPTZ NOT NULL,
    form_config      JSONB NOT NULL,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_guest_form_snapshot_apartment ON guest_form_snapshot (apartment_id);

-- One row per submission. received_at is the legal submission time.
-- payload_enc: Fernet token (data keys, as the _enc columns) of gzip(JSON).
-- reservation_id has no foreign key: a moved or deleted stay makes the row
-- held, it must never make the guest program's insert fail.
CREATE TABLE IF NOT EXISTS guest_inbox (
    id               BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    idempotency_key  TEXT NOT NULL UNIQUE CHECK (idempotency_key ~ '^[0-9a-f]{32}$'),
    token_hash       TEXT NOT NULL CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    reservation_id   BIGINT,
    contract_version SMALLINT NOT NULL CHECK (contract_version >= 1),
    received_at      TIMESTAMPTZ NOT NULL,
    payload_enc      BYTEA,
    status           TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'done', 'held')),
    host_note        TEXT,
    attempts         INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    processed_at     TIMESTAMPTZ,
    CHECK (payload_enc IS NOT NULL OR status = 'done')
);
-- The app worker claims the oldest new rows with FOR UPDATE SKIP LOCKED.
CREATE INDEX IF NOT EXISTS idx_guest_inbox_claim ON guest_inbox (status, received_at);
-- The guest program counts its own rows per link and stay.
CREATE INDEX IF NOT EXISTS idx_guest_inbox_token ON guest_inbox (token_hash, reservation_id);
-- Retention: payloads are deleted 7 days after done (plan section 3 rule 7).
CREATE INDEX IF NOT EXISTS idx_guest_inbox_purge ON guest_inbox (processed_at)
    WHERE status = 'done' AND payload_enc IS NOT NULL;

-- +goose Down
DROP TABLE IF EXISTS guest_inbox;
DROP TABLE IF EXISTS guest_form_snapshot;
```
   Command: `head -3 App/migrations_pg/00020_guest_contract.sql` shows `-- +goose Up` then `-- contract: v1`.

2. **Golden.** From `App/`: if `.venv/bin/python` is missing, run `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt 2>&1 | tail -5`. Then `.venv/bin/python scripts/pg_schema_golden.py 2>&1 | tail -5`. Command: `git diff --stat -- ../go/internal/schema/testdata/ | tail -3` shows `goose_statements_golden.json` changed. Never edit the JSON by hand.

3. **Table counts.** In `App/tests/test_db_postgres.py` replace the two anchor lines with:
```
    assert status["expected_tables"] == 70 and status["actual_tables"] == 73  # + job (goose 00003), guest_form_snapshot and guest_inbox (goose 00020), PostgreSQL only
    assert status["missing_tables"] == 0 and status["extra_tables"] == 3  # job, guest_form_snapshot, guest_inbox
```
   Command: `grep -n 'actual_tables\] == 73' App/tests/test_db_postgres.py` prints one line.

4. **Role script.** Create `deploy/lightsail/scripts/pg-guest-role.sql` with exactly:
```sql
-- 1834: restricted role for the guest program (plan guest-form-isolation
-- section 2). Run as the bootstrap superuser AFTER migration 00020 is applied:
--   docker compose exec -T postgres psql -U ubyhost -d ubyhost -X -v ON_ERROR_STOP=1 < scripts/pg-guest-role.sql
-- Idempotent. Never drops anything. No password: the postgres service has no
-- network and trusts its socket volume (docs/SECURITY.md), as for ubyhost_app.
-- Run it again after any restore or cutover (grants are not restored).
\set ON_ERROR_STOP on

DO $do$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ubyhost_guest') THEN
    CREATE ROLE ubyhost_guest NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS LOGIN CONNECTION LIMIT 3;
  ELSE
    ALTER ROLE ubyhost_guest NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS LOGIN CONNECTION LIMIT 3;
  END IF;
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO ubyhost_guest', current_database());
END
$do$;
ALTER ROLE ubyhost_guest SET statement_timeout = '2s';
GRANT USAGE ON SCHEMA public TO ubyhost_guest;
-- Reset, then grant exactly plan section 2 (revoking a table privilege also
-- revokes its column privileges).
REVOKE ALL ON guest_form_snapshot, guest_inbox FROM ubyhost_guest;
GRANT SELECT ON guest_form_snapshot TO ubyhost_guest;
GRANT INSERT (idempotency_key, token_hash, reservation_id, contract_version, received_at, payload_enc)
  ON guest_inbox TO ubyhost_guest;
GRANT SELECT (id, idempotency_key, token_hash, reservation_id, status, received_at)
  ON guest_inbox TO ubyhost_guest;

\echo '== role'
SELECT rolname, rolconnlimit, rolconfig, rolsuper, rolcreaterole FROM pg_roles WHERE rolname = 'ubyhost_guest';

\echo '== proof: expect four PASS lines'
DO $do$
BEGIN
  SET LOCAL ROLE ubyhost_guest;
  PERFORM 1 FROM guest_form_snapshot LIMIT 1;
  PERFORM id, idempotency_key, token_hash, reservation_id, status, received_at FROM guest_inbox LIMIT 1;
  RESET ROLE;
  RAISE NOTICE 'PASS: ubyhost_guest reads the snapshot and its inbox columns';
  SET LOCAL ROLE ubyhost_guest;
  BEGIN
    PERFORM 1 FROM guest LIMIT 1;
    RESET ROLE;
    RAISE EXCEPTION 'FAIL: ubyhost_guest can read the guest table';
  EXCEPTION WHEN insufficient_privilege THEN
    RESET ROLE;
    RAISE NOTICE 'PASS: guest table refused';
  END;
  SET LOCAL ROLE ubyhost_guest;
  BEGIN
    PERFORM payload_enc FROM guest_inbox LIMIT 1;
    RESET ROLE;
    RAISE EXCEPTION 'FAIL: ubyhost_guest can read payload_enc';
  EXCEPTION WHEN insufficient_privilege THEN
    RESET ROLE;
    RAISE NOTICE 'PASS: payload_enc read refused';
  END;
  SET LOCAL ROLE ubyhost_guest;
  BEGIN
    UPDATE guest_inbox SET status = 'done' WHERE false;
    RESET ROLE;
    RAISE EXCEPTION 'FAIL: ubyhost_guest can update guest_inbox';
  EXCEPTION WHEN insufficient_privilege THEN
    RESET ROLE;
    RAISE NOTICE 'PASS: inbox update refused';
  END;
END
$do$;
```
   Command: `grep -c 'PASS:' deploy/lightsail/scripts/pg-guest-role.sql` prints `4`.

5. **CI.** In `.github/workflows/ci.yml`, directly after the anchor line `          python scripts/pg_schema.py check --expect-database ubyhost_test` (the one in step "App works as the non-superuser role"; if the line appears more than once, edit only that step and say so in the report) add:
```
          # 1834: the guest role script, after the contract tables exist
          psql -h localhost -U postgres -d ubyhost_test -v ON_ERROR_STOP=1 -q -f ../deploy/lightsail/scripts/pg-guest-role.sql
```
   Same indentation (10 spaces). Command: `grep -n 'pg-guest-role.sql' .github/workflows/ci.yml` prints one line.

6. **Env var docs.** In `docs/ENVIRONMENT.md`, section "Database (PostgreSQL, optional)", add after the anchor line (line 307) one blank line and:
```
`UBYHOST_GUEST_DATABASE_URL`: the guest program's database URL (plan guest-form-isolation; read from brief 1840 on, unused before). Production: `postgresql://ubyhost_guest@/ubyhost?host=/var/run/postgresql`, after the owner runs `scripts/pg-guest-role.sql` as the superuser. No password (socket trust, as above), so it holds no secret. The role reads `guest_form_snapshot` and inserts into `guest_inbox` only, with at most 3 connections and a 2 s statement timeout.
```
   Command: `grep -c 'UBYHOST_GUEST_DATABASE_URL' docs/ENVIRONMENT.md` prints `1`.

7. **Tests.** Run section 6. Write the report.

## 5. Do not touch

`App/app/` (no `db.py`, no `GOOSE_ONLY_COLUMNS`: these are new tables, not new columns), `App/app/migrations/` (frozen), `App/app/retention.py` (retention lines are brief 1839; the tables stay empty until 1837), `deploy/lightsail/docker-compose.yml`, `deploy/lightsail/scripts/pg-app-role.sql`, every other migration file. Rules 1, 3, 4, 5, 8.

## 6. Commands

From `App/`:
- `.venv/bin/python -m pytest tests/test_migrations.py tests/test_db_postgres.py tests/test_goose_migrations.py tests/test_go_schema_golden.py -q --tb=short -x 2>&1 | tail -30` (test-map row "Database, migrations"). Expected: passed; PostgreSQL tests skip locally without `UBYHOST_TEST_DATABASE_URL` (CI runs them with 0 skipped). Report the skip count.

From `go/`:
- `go test ./internal/schema/... 2>&1 | tail -30`. Expected: `ok`.

From the repo root:
- `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: `context lint: OK`.
- `git diff --cached | grep -iE 'secret|token|api[_-]?key|password|AKIA|ghp_' | grep -v token_hash | tail -10`. Expected: nothing but comment lines that say "No password".

## 7. Acceptance

- [ ] `App/migrations_pg/00020_guest_contract.sql` exists; line 2 is `-- contract: v1`; it sets `lock_timeout`.
- [ ] Golden regenerated by the script; `go test ./internal/schema/...` is `ok`.
- [ ] `pg-guest-role.sql` has four `PASS:` lines and no password.
- [ ] CI runs it once, after `pg_schema.py check`.
- [ ] `docs/ENVIRONMENT.md` names `UBYHOST_GUEST_DATABASE_URL` once.
- [ ] Only the files in section 3 changed (`git diff --stat`).

## 8. Stop and ask

Stop, and write the report, if:

- an open question has no answer, or an excerpt is not found;
- `pg_schema_golden.py` fails or changes any file other than `goose_statements_golden.json`;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1834-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/migrations_pg/00020_guest_contract.sql`: additive only (plan section 6); regex checks are PostgreSQL syntax; `apartment(id)` type matches; `Down` drops only the two new tables.
- `deploy/lightsail/scripts/pg-guest-role.sql`: grants equal plan section 2 plus open question 2; no `ALL` grant; the proof blocks really fail on a wrong grant (the `FAIL` exception is not caught by `insufficient_privilege`).
- `.github/workflows/ci.yml`: the new line is inside the step that already ran `pg-app-role.sql` and migrated as `ubyhost_app`.
- `App/tests/test_db_postgres.py`: only the two count lines.
- Note for 1836-1844: `deploy/lightsail/docker-compose.yml` sets `max_connections=50`, not 20 as plan section 2 says; pool sizes are for 1843.

## Owner steps

After this PR is merged and deployed (the deploy applies migration 00020):

1. Open a terminal on the server (SSH) and run: `cd /opt/ubyhost/deploy/lightsail`
2. Run: `docker compose exec -T postgres psql -U ubyhost -d ubyhost -X -v ON_ERROR_STOP=1 < scripts/pg-guest-role.sql`
3. Check the output: the `== role` table shows `ubyhost_guest`, `rolconnlimit` 3 and `{statement_timeout=2s}`, and there are four lines that start with `NOTICE:  PASS:`. If you see `FAIL` or `ERROR`, stop and send the output to the orchestrator.
4. Nothing goes into `.env` yet. Brief 1840 will ask you to add `UBYHOST_GUEST_DATABASE_URL=postgresql://ubyhost_guest@/ubyhost?host=/var/run/postgresql` (it holds no password).
5. After any restore or move to a new server, run step 2 again.
