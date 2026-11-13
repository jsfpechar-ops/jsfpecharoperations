# 1471: goose 00017 (6 foreign keys DEFERRABLE, 19 text columns COLLATE "C")

Status: todo
Depends on: none | Base commit: origin/main (writer verified on b5f353682, which holds PR #982, and on its parent schema files, equal to origin/main ed39902f7) | Branch: task/1471-goose-fk-deferrable
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier A (migrations). Plan: [sqlite-retirement](../plans/sqlite-retirement.md) step S2.

## 1. Objective

Add goose migration `App/migrations_pg/00017_fk_deferrable.sql`, so that a database built from goose files alone has the same foreign keys and text collations as production. On production it changes nothing: production was built by Python's translation of the SQLite migrations, which already has both.

## 2. Context

**The drift (writer's run, PostgreSQL 16, two databases: A = `pg_schema.py apply`, B = only the goose Up sections).** The `pg_dump --schema-only` diff of A and B has exactly two kinds of difference:

1. 6 foreign keys are `DEFERRABLE` in A and not in B (goose 00004, 00011, 00013 left it out). Their names are **the same in both builds**: `site_booking_apartment_id_fkey`, `site_booking_invoice_id_fkey`, `site_booking_owner_user_id_fkey`, `site_booking_reservation_id_fkey` (table `site_booking`), `stay_fee_rate_apartment_id_fkey` (table `stay_fee_rate`), `guest_form_draft_reservation_id_fkey` (table `guest_form_draft`). All 90 FKs in A are deferrable; B has 84 plus these 6.
2. 19 text columns are `COLLATE "C"` in A and have the database default collation in B (Python's translation writes `TEXT COLLATE "C"` for every TEXT column; goose 00004 writes it by hand, goose 00006-00015 forgot it): `apartment.stay_fee_guest_rails`, `.stay_fee_guest_revolut_link`, `.stay_fee_guest_cash_note`, `.stay_fee_guest_default_rail`; `guest.signed_for_role`, `.signed_for_at`, `.signed_for_wording`; `guest_form_draft.device_key_hash`, `.fields_enc`, `.created_at`, `.updated_at`; `property_page.house_rules`; `reservation.lead_reduced_at`; `reservation_claim.fee_mailed_at`, `.fee_pending_since`; `site_booking.pay_method`, `.request_expires_at`; `stay_fee_rate.effective_from`, `.created_at`.

Nothing else differs (no column order difference, same `schema_migrations` rows 1-45). The writer added item 2 to this migration because a goose-only build must equal production (plan target 2) and brief 1472's test fails on it otherwise.

**The file** (`docs/tasks/1471-files/00017_fk_deferrable.sql`, copied verbatim in step 1). Up: six `ALTER TABLE <t> ALTER CONSTRAINT <name> DEFERRABLE INITIALLY IMMEDIATE`, then one `DO` block (inside `-- +goose StatementBegin/End`) that loops over the explicit 19 (table, column) pairs and runs `ALTER TABLE %I ALTER COLUMN %I TYPE text COLLATE "C"` only for a listed column whose `collation_name` is not `C`. It touches no other constraint or column. Down: the 19 columns back to `COLLATE "default"`, the 6 FKs back to `NOT DEFERRABLE` (the goose-only form; never run Down on production). It writes no `schema_migrations` row: it has no SQLite twin.

**What it does on production: nothing.** PostgreSQL's `ALTER CONSTRAINT` with the attributes the constraint already has writes no catalog row, and the DO block finds no column to alter. `noop_check.py` (step 4) proves this: on a database built the way production was, it forgets goose version 17, records `xmin` of the 6 FK rows in `pg_constraint` and of every column of the 8 tables in `pg_attribute` (226 rows), applies again so only 00017 runs, and compares. Writer's run: `rows compared: 226; changed: 0`, `NOOP OK`.

**Python accepts a goose-only file without a code change** (`App/app/db.py`): `apply_postgresql_schema` runs every goose file whose version is not in `goose_db_version`, then records it. `postgres_schema_status` calls the schema current when `expected_schema_version()` (the highest SQLite migration, 45) equals `MAX(schema_migrations.version)` and the columns, indexes and triggers match; 00017 adds none of these and no `schema_migrations` row, so it stays 45. Writer's run: `PostgreSQL schema apply OK: database=a0, version=45, tables=71, goose=17.` and `check OK ... goose=17`. No file under `App/app/` changes, so no go-first exception is needed.

**Order with PR #982 and brief 1263.** Step 0 prints which case applies:
- `GOLDEN` (#982 is on main: `App/scripts/pg_schema_golden.py` exists). Its test `App/tests/test_go_schema_golden.py` fails while the goose golden is stale, so step 2 regenerates it. Expected change: only `go/internal/schema/testdata/goose_statements_golden.json`, 11 lines added (a `"00017_fk_deferrable.sql"` entry with 7 statement hashes: 6 ALTERs and the DO block). `expected_schema.json` does not change (it is built from the SQLite side).
- `ALLOWLIST` (1263 is on main: `KNOWN_NOT_DEFERRABLE` is in `App/tests/test_go_schema_migrate.py`). That test then fails, because the Go-applied database now has DEFERRABLE. Step 3 applies `docs/tasks/1471-files/allowlist.patch`, which empties the set (writer's run: 1 failed before the patch, 5 passed after it; the test also runs the new Down section).
- No version constant or other expected-schema file changes in any case.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/migrations_pg/00017_fk_deferrable.sql | new (copy) | the migration |
| go/internal/schema/testdata/goose_statements_golden.json | regenerate, case `GOLDEN` only | new 00017 entry |
| App/tests/test_go_schema_migrate.py | edit (patch), case `ALLOWLIST` only | empty `KNOWN_NOT_DEFERRABLE` |
| docs/tasks/1471-report.md | new | your report |
| docs/tasks/1471-goose-fk-deferrable.md | exists | Status line only |
| docs/tasks/1471-files/* | exist | sidecars; do not edit |

No other file may change.

## 4. Steps

Run everything from the repo root unless a step says `App/`.

**Step 0. Branch and pick the case.**

```bash
git fetch origin main 2>&1 | tail -2; git switch -c task/1471-goose-fk-deferrable origin/main 2>&1 | tail -2
ls App/migrations_pg/ | tail -2; (test -f App/scripts/pg_schema_golden.py && echo GOLDEN || echo NO-GOLDEN); (grep -q KNOWN_NOT_DEFERRABLE App/tests/test_go_schema_migrate.py 2>/dev/null && echo ALLOWLIST || echo NO-ALLOWLIST)
```

Expected: the last goose file is `00016_guest_details_mail.sql`, then one of `NO-GOLDEN NO-ALLOWLIST`, `GOLDEN NO-ALLOWLIST`, `GOLDEN ALLOWLIST`. Write the pair in the report. STOP if a file `00017_*` already exists, or you see `NO-GOLDEN ALLOWLIST`.

**Step 1. Add the migration.**

```bash
cp docs/tasks/1471-files/00017_fk_deferrable.sql App/migrations_pg/00017_fk_deferrable.sql
sha256sum App/migrations_pg/00017_fk_deferrable.sql 2>&1 | tail -1
git add App/migrations_pg/00017_fk_deferrable.sql && git commit -m "1471 step 1" 2>&1 | tail -1
```

Expected hash: `7ba7810c98ed7932e97fc7162f8ce33897cc1cf0ec1767424bbb4a5513d02c3e`. Different: STOP.

**Step 2. Case `GOLDEN` only (skip on `NO-GOLDEN`). Regenerate the goose golden** (from `App/`; create `.venv` only if missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3`):

```bash
.venv/bin/python scripts/pg_schema_golden.py 2>&1 | tail -5
git diff --stat 2>&1 | tail -3; git diff ../go | grep -c '"00017_fk_deferrable.sql"'
.venv/bin/python scripts/pg_schema_golden.py --check; echo "check exit $?"
sha256sum ../go/internal/schema/testdata/goose_statements_golden.json | cut -c1-64
```

Expected: exactly one line `wrote: go/internal/schema/testdata/goose_statements_golden.json`; stat `1 file changed, 11 insertions(+)`; `1`; `check exit 0`; hash `e5a9d6b8c40b609d34f4c00951c11b825495d9607b22d25b086a1d72f6d6f817`. A different hash with the same stat means another goose change reached main after b5f353682: write it under Deviations and go on. Another `wrote:` file, or a different stat: STOP. Commit: `git add ../go/internal/schema/testdata/goose_statements_golden.json && git commit -m "1471 step 2" 2>&1 | tail -1`.

**Step 3. Case `ALLOWLIST` only (skip on `NO-ALLOWLIST`). Empty the allowlist.**

```bash
grep -cF 'KNOWN_NOT_DEFERRABLE = {' App/tests/test_go_schema_migrate.py
git apply --check docs/tasks/1471-files/allowlist.patch && git apply docs/tasks/1471-files/allowlist.patch && git diff --stat 2>&1 | tail -2
sha256sum App/tests/test_go_schema_migrate.py | cut -c1-64
```

Expected: `1`; `1 file changed, 4 insertions(+), 12 deletions(-)`; hash `c0d5eb1022208c9c0419f68a980653682a65ad85eb2e134963f13d4c6fb62505` (a different hash after a clean apply: Deviation, go on). `git apply --check` fails: STOP, never `--reject`, never edit by hand. Commit: `git add App/tests/test_go_schema_migrate.py && git commit -m "1471 step 3" 2>&1 | tail -1`.

**Step 4.** Run §6. **Step 5.** Write the report (§9), commit it as `1471 step 5: report`, open one draft PR whose text says "Adds goose file 00017; goose-only, no SQLite twin; a no-op on production (noop_check.py)" and names the case from step 0.

## 5. Do not touch

`App/app/**` (no Python change is needed), `App/app/migrations/**` (frozen), every other file in `App/migrations_pg/`, `App/scripts/**`, `go/**` except the one golden in case `GOLDEN`, `.github/workflows/*`, `deploy/**`, `docs/context/*`. Rules 3, 4, 5 and 8: no secrets, no new dependency, schema change only as a new migration file, never push to main. Never connect to any database but the disposable one in §6.

## 6. Commands

Without a database, from `App/`:

```bash
env -u UBYHOST_DATABASE_URL -u UBYHOST_TEST_DATABASE_URL .venv/bin/python -m pytest tests/test_migrations.py -q --tb=short 2>&1 | tail -3
```

Expected: `14 passed`. Case `GOLDEN` also: `env -u UBYHOST_DATABASE_URL -u UBYHOST_TEST_DATABASE_URL .venv/bin/python -m pytest tests/test_go_schema_golden.py -q --tb=short 2>&1 | tail -3` gives `5 passed`, and `cd ../go && go test ./internal/schema/ -run 'TestGooseFilesMatchPython|TestSplitAndGooseCasesMatchPython' -count=1 2>&1 | tail -3; cd ../App` gives `ok`.

**Disposable PostgreSQL 16** (needed for the no-op proof; data dir under `/var/tmp`, port 5471, removed at the end):

```bash
B=/usr/lib/postgresql/16/bin; mkdir -p /var/tmp/pg1471 && chown postgres /var/tmp/pg1471
runuser -u postgres -- $B/initdb -D /var/tmp/pg1471/data -A trust -E UTF8 --locale=C.UTF-8 2>&1 | tail -1
runuser -u postgres -- $B/pg_ctl -D /var/tmp/pg1471/data -o '-p 5471 -k /var/tmp/pg1471 -c listen_addresses=' -l /var/tmp/pg1471/log start 2>&1 | tail -1
psql -h /var/tmp/pg1471 -p 5471 -U postgres -qc 'CREATE DATABASE ubyhost_test' && echo created
```

Expected: `server started`, `created`. `-E UTF8` is required: Python refuses a non-UTF8 server. Then, from `App/`:

```bash
export UBYHOST_TEST_DATABASE_URL="postgresql://postgres@/ubyhost_test?host=/var/tmp/pg1471&port=5471"
.venv/bin/python ../docs/tasks/1471-files/noop_check.py "$UBYHOST_TEST_DATABASE_URL" 2>&1 | tail -4
env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_db_postgres.py -q -rs --tb=short 2>&1 | tail -3
```

Expected: `rows compared: 226; changed: 0` and `NOOP OK`; `55 passed`. Case `GOLDEN` also: `env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_go_schema_migrate.py -q -rs --tb=short 2>&1 | tail -3` gives `4 passed` (`5 passed` in case `ALLOWLIST`; needs `go` on PATH). Then stop and delete the server:

```bash
runuser -u postgres -- /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1471/data stop 2>&1 | tail -1; rm -rf /var/tmp/pg1471; unset UBYHOST_TEST_DATABASE_URL
```

If PostgreSQL cannot be started, write "PostgreSQL run: not done" in the report and set `Status: blocked` (the no-op proof is required for a tier A review).

From the repo root: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -3` shows `context lint: OK`.

## 7. Acceptance

- [ ] Step 0 case written; step 1 hash matches.
- [ ] Case `GOLDEN`: step 2 as expected and `pg_schema_golden.py --check` exit 0. Case `ALLOWLIST`: step 3 applied.
- [ ] `noop_check.py` printed `NOOP OK` with `changed: 0`.
- [ ] §6 tests as expected; the PostgreSQL server is stopped and `/var/tmp/pg1471` is gone.
- [ ] `git diff --stat origin/main..HEAD` lists only §3 files.
- [ ] After push, CI `test-postgres` ("goose builds the baseline": goose and Python agree on 17 files) and `test-postgres-full` are green.

## 8. Stop and ask

Stop, and write the report, if: an expected value in a step differs where the step says STOP; a test fails twice; `noop_check.py` prints `NOOP FAILED` (copy its `changed:` lines into the report; never edit the migration); you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push to main, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1471-report.md` (600 tokens at most) and set `Status: review`. It has: the step 0 case, the files changed (`git diff --stat origin/main..HEAD`), each command with its last 5 lines, §7 ticked, Deviations, Questions, Owner steps left.

## Risk list (for the reviewer)

Full diff of `App/migrations_pg/00017_fk_deferrable.sql` (exactly 6 named FKs; the DO block alters only the 19 listed columns and only when not `C`; Down is the exact reverse; no `schema_migrations` row). In case `ALLOWLIST`, `App/tests/test_go_schema_migrate.py` (only the set and its comment change). In case `GOLDEN`, the golden diff is one new key only.

## Owner steps

The migration reaches production by the normal deploy: after the merge, the green deploy runs `deploy.sh`, which applies pending goose files with `scripts/pg_schema.py apply --expect-database ubyhost` before `up` (`UBYHOST_SCHEMA_APPLY` unset or `python`; with `go`, `ubyhost-web migrate apply` does the same). A failure stops the deploy and the running stack stays as it was. Nothing to run by hand. To check it did nothing harmful:

1. Merge with `scripts/merge-pr-on-green.sh <pr>` once CI is green, and wait for the deploy to finish green.
2. Open a terminal on the server and run `cd /opt/ubyhost/deploy/lightsail`.
3. Run `docker compose run --rm --no-deps ubyhost python scripts/pg_schema.py check --expect-database ubyhost`. Expected: a line ending `version=45, tables=71, goose=17.` (tables may be higher if a later PR added one).
4. Run `docker compose exec -T postgres psql -U ubyhost -d ubyhost -At < /opt/ubyhost/docs/tasks/1471-files/prod_check.sql`. Expected: `6|19` (read-only; it counts the 6 foreign keys and 19 columns).
5. Anything else in step 3 or 4: send the output to the orchestrator. Do not run the migration's Down section.

## Notes for the coordinator

- If this merges before 1263, 1263's test fails on main (its §8 then stops): give 1263 a fix brief that also applies `docs/tasks/1471-files/allowlist.patch`. If it merges before #982, #982 must rerun `App/scripts/pg_schema_golden.py` (its own rule).
- known-issues: close the `[schema]` 1263 line (FKs without DEFERRABLE) once this is deployed; add that goose 00006-00015 had dropped `COLLATE "C"` on 19 columns, fixed here.
