# 1471: goose 00017_goose_parity (6 foreign keys DEFERRABLE, 19 text columns COLLATE "C")

Status: blocked
Depends on: none | Base: the current branch (claude/happy-babbage-2zeeam: holds PR #982, 1263 and 1470; writer verified on d3817813d) | Branch: none, see below
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier A (migrations). Plan: [sqlite-retirement](../plans/sqlite-retirement.md) step S2.

**One big PR mode.** Work on the current branch. Commit `1471 step k` after each step. Never create a branch, never push, never open a PR. Acceptance uses `git log --oneline --grep='^1471 step'` and `git show --stat`, not a base commit.

## 1. Objective

Add goose migration `App/migrations_pg/00017_goose_parity.sql`, so that a database built from goose files alone has the same foreign keys and text collations as production; regenerate the goose golden and empty 1263's `KNOWN_NOT_DEFERRABLE` allowlist in the same brief. On a database built by Python's apply, which is how production was built, the migration changes nothing.

## 2. Context

**The drift (writer's run, PostgreSQL 16: A = `pg_schema.py apply`, B = only the goose Up sections).** The `pg_dump --schema-only` diff of A and B has exactly two kinds of difference:

1. 6 foreign keys are `DEFERRABLE` in A and not in B (goose 00004, 00011, 00013 left it out). The names are **the same in both builds**: `site_booking_apartment_id_fkey`, `site_booking_invoice_id_fkey`, `site_booking_owner_user_id_fkey`, `site_booking_reservation_id_fkey`, `stay_fee_rate_apartment_id_fkey`, `guest_form_draft_reservation_id_fkey`.
2. 19 text columns are `COLLATE "C"` in A and use the database default in B (Python's translation writes `TEXT COLLATE "C"`; goose 00004 writes it by hand; goose 00006-00015 forgot it): `apartment.stay_fee_guest_rails`, `.stay_fee_guest_revolut_link`, `.stay_fee_guest_cash_note`, `.stay_fee_guest_default_rail`; `guest.signed_for_role`, `.signed_for_at`, `.signed_for_wording`; `guest_form_draft.device_key_hash`, `.fields_enc`, `.created_at`, `.updated_at`; `property_page.house_rules`; `reservation.lead_reduced_at`; `reservation_claim.fee_mailed_at`, `.fee_pending_since`; `site_booking.pay_method`, `.request_expires_at`; `stay_fee_rate.effective_from`, `.created_at`.

Nothing else differs (no column order difference, same `schema_migrations` rows 1-45). The coordinator decided that both fixes go into one file named for what it does.

**The file** (`docs/tasks/1471-files/00017_goose_parity.sql`, copied verbatim in step 1). Its header lists both fixes and says it is a no-op on a database built by Python's apply. Up: `SET LOCAL lock_timeout = '5s'`; six `ALTER TABLE <t> ALTER CONSTRAINT <name> DEFERRABLE INITIALLY IMMEDIATE`; one `DO` block (inside `-- +goose StatementBegin/End`) that loops over the explicit 19 (table, column) pairs and runs `ALTER TABLE %I ALTER COLUMN %I TYPE text COLLATE "C"` only for a listed column whose `collation_name` is not `C`. It touches no other constraint or column. Down: the 19 columns back to `COLLATE "default"`, the 6 FKs back to `NOT DEFERRABLE` (the goose-only form; never run Down on production). It writes no `schema_migrations` row: it has no SQLite twin.

**Python accepts a goose-only file without a code change** (`App/app/db.py`): `apply_postgresql_schema` runs every goose file whose version is not in `goose_db_version`, then records it. `postgres_schema_status` calls the schema current when `expected_schema_version()` (the highest SQLite migration, 45) equals `MAX(schema_migrations.version)` and the columns, indexes and triggers match; 00017 adds none of these, so it stays 45. Writer's run: `apply OK ... version=45, tables=71, goose=17.` No file under `App/app/` changes, so no go-first exception is needed. `scripts/context_lint.py` already prints `goose migration 00017` as next free and `App/tests/test_sqlite_migrations_frozen.py` checks only `App/app/migrations/`: neither needs a change.

**The goldens and the allowlist.** `App/tests/test_go_schema_golden.py` (#982) fails while `go/internal/schema/testdata/goose_statements_golden.json` is stale; step 2 regenerates it: one new key `"00017_goose_parity.sql"` with 8 statement hashes (SET, 6 ALTERs, the DO block), 12 lines. `expected_schema.json` does not change (built from the SQLite side), and no version constant changes. `App/tests/test_go_schema_migrate.py` (1263) fails once 00017 exists, because the Go-applied database now has DEFERRABLE; step 3 empties `KNOWN_NOT_DEFERRABLE` (writer's run: 1 failed before, 5 passed after; that test also runs the new Down section).

## What happens on production

00017 reaches production through the deploy after the merge (`deploy.sh` runs the schema apply before `up`, while the old stack still serves). Both apply paths (Python and Go) run all pending goose files in one transaction and set `lock_timeout` 30 s; the file lowers it to 5 s for the rest of that transaction. Locks are held until that transaction commits (milliseconds).

**(a) Expected: production has all 6 FKs deferrable and all 19 columns `C`** (it was built by Python's apply). The 6 `ALTER CONSTRAINT` run and find nothing to change; they still take an `ACCESS EXCLUSIVE` lock on `site_booking`, `stay_fee_rate` and `guest_form_draft` (not on the referenced tables). The DO block only reads `information_schema` and runs no ALTER. Nothing is written: `noop_check.py` compares `xmin` of 226 catalog rows before and after (`changed: 0`). `case_check.py a`: the 3 locks, 8 ms, no table rewrite, no index rebuilt.

**(b) Production differs on some of them.** For each FK that is not deferrable, its `ALTER CONSTRAINT` changes the constraint and its triggers in the catalog only: no data is read, nothing can be violated. For each listed column not `C`, the DO block runs `ALTER TABLE <t> ALTER COLUMN <c> TYPE text COLLATE "C"`: `ACCESS EXCLUSIVE` on that table, **no table rewrite** (same type), but every index on that column is rebuilt. Of the 19, two are indexed: `stay_fee_rate.effective_from` (unique `(apartment_id, effective_from)` and `idx_stay_fee_rate_apartment`) and `guest_form_draft.device_key_hash` (unique `(reservation_id, device_key_hash)`), plus `guest_form_draft.updated_at` (`idx_guest_form_draft_updated`). None of the 19 is a foreign-key column. A unique rebuild cannot fail: the database default and `C` are both deterministic collations, so equal means byte-equal in both and no new duplicates can appear. On tables of a few hundred rows this takes milliseconds. `case_check.py b` (FK `stay_fee_rate_apartment_id_fkey` made NOT DEFERRABLE, `effective_from` and `created_at` set back to default, 6 rows inserted): 11-15 ms, locks `ACCESS EXCLUSIVE` plus `SHARE` (index build) on `stay_fee_rate`, table not rewritten, the 2 indexes rebuilt, rows intact, the unique index still refuses a duplicate, end state 6 FKs deferrable and both columns `C`.

**What can go wrong, in either case:** only waiting for a lock. If the running app holds a lock on one of these tables (an open transaction), the ALTER waits, and while it waits other queries on that table queue behind it. `SET LOCAL lock_timeout = '5s'` caps that: the apply fails with `canceling statement due to lock timeout` after 5 s, the whole transaction rolls back (goose stays at 16), the deploy stops, the old stack keeps running, and the next deploy applies it. Writer's test with a lock held for 15 s: `apply failed ... lock timeout`, exit 1 after 5 s, goose still 16; rerun after the lock ended: `apply OK ... goose=17`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/migrations_pg/00017_goose_parity.sql | new (copy) | the migration |
| go/internal/schema/testdata/goose_statements_golden.json | regenerate | new 00017 entry |
| App/tests/test_go_schema_migrate.py | edit (patch) | empty `KNOWN_NOT_DEFERRABLE` |
| docs/tasks/1471-report.md | new | your report |
| docs/tasks/1471-goose-fk-deferrable.md | exists | Status line only |
| docs/tasks/1471-files/* | exist | sidecars; do not edit |

No other file may change.

## 4. Steps

From the repo root unless a step says `App/`. Create `App/.venv` only if missing: `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3; cd ..`.

**Step 0. Check the state.**

```bash
git status --short | wc -l; ls App/migrations_pg/ | tail -1; grep -c KNOWN_NOT_DEFERRABLE App/tests/test_go_schema_migrate.py; test -f App/scripts/pg_schema_golden.py && echo golden-script
```

Expected: `0` (clean tree), `00016_guest_details_mail.sql`, `2`, `golden-script`. Anything else: STOP.

**Step 1. Add the migration.**

```bash
cp docs/tasks/1471-files/00017_goose_parity.sql App/migrations_pg/00017_goose_parity.sql
sha256sum App/migrations_pg/00017_goose_parity.sql | cut -c1-64
git add App/migrations_pg/00017_goose_parity.sql && git commit -m "1471 step 1" 2>&1 | tail -1
```

Expected hash: `4527db995a8a2f09d5eeba134e73fdaba2444782c2a1f3313e9425de069d6512`. Different: STOP.

**Step 2. Regenerate the goose golden** (from `App/`):

```bash
.venv/bin/python scripts/pg_schema_golden.py 2>&1 | tail -5
git diff --stat 2>&1 | tail -3; git diff ../go | grep -c '"00017_goose_parity.sql"'
.venv/bin/python scripts/pg_schema_golden.py --check; echo "check exit $?"
sha256sum ../go/internal/schema/testdata/goose_statements_golden.json | cut -c1-64
```

Expected: exactly one line `wrote: go/internal/schema/testdata/goose_statements_golden.json`; `1 file changed, 12 insertions(+)`; `1`; `check exit 0`; hash `12377b2fd9e5c2594a0f08c97aa6243caa83d801ca1c3f20de9492415e3e4e65`. Same stat but another hash: a goose change reached the branch after d3817813d; write it under Deviations and go on. Another `wrote:` file or another stat: STOP. Commit: `git add ../go/internal/schema/testdata/goose_statements_golden.json && git commit -m "1471 step 2" 2>&1 | tail -1`.

**Step 3. Empty the allowlist** (repo root):

```bash
grep -cF 'KNOWN_NOT_DEFERRABLE = {' App/tests/test_go_schema_migrate.py
git apply --check docs/tasks/1471-files/allowlist.patch && git apply docs/tasks/1471-files/allowlist.patch && git diff --stat 2>&1 | tail -2
sha256sum App/tests/test_go_schema_migrate.py | cut -c1-64
git add App/tests/test_go_schema_migrate.py && git commit -m "1471 step 3" 2>&1 | tail -1
```

Expected: `1`; `1 file changed, 4 insertions(+), 12 deletions(-)`; hash `c0d5eb1022208c9c0419f68a980653682a65ad85eb2e134963f13d4c6fb62505` (another hash after a clean apply: Deviation, go on). `git apply --check` fails: STOP, never `--reject`, never edit by hand.

**Step 4.** Run §6. **Step 5.** Write the report (§9) and commit it as `1471 step 5: report`.

## 5. Do not touch

`App/app/**`, `App/app/migrations/**` (frozen), every other file in `App/migrations_pg/`, `App/scripts/**`, `go/**` except the one golden, `.github/workflows/*`, `deploy/**`, `scripts/context_lint.py`, `App/tests/test_sqlite_migrations_frozen.py`, `docs/context/*`. Rules 3, 4, 5 and 8: no secrets, no new dependency, schema change only as a new goose file, never push. Never connect to any database but the disposable one in §6.

## 6. Commands

Without a database, from `App/`:

```bash
env -u UBYHOST_DATABASE_URL -u UBYHOST_TEST_DATABASE_URL .venv/bin/python -m pytest tests/test_migrations.py tests/test_go_schema_golden.py tests/test_sqlite_migrations_frozen.py -q --tb=short 2>&1 | tail -3
cd ../go && go test ./internal/schema/ -run 'TestGooseFilesMatchPython|TestSplitAndGooseCasesMatchPython' -count=1 2>&1 | tail -3; cd ../App
```

Expected: `23 passed`; `ok`.

**Disposable PostgreSQL 16** (required; data dir under `/var/tmp`, port 5471, removed at the end):

```bash
B=/usr/lib/postgresql/16/bin; mkdir -p /var/tmp/pg1471 && chown postgres /var/tmp/pg1471
runuser -u postgres -- $B/initdb -D /var/tmp/pg1471/data -A trust -E UTF8 --locale=C.UTF-8 2>&1 | tail -1
runuser -u postgres -- $B/pg_ctl -D /var/tmp/pg1471/data -o '-p 5471 -k /var/tmp/pg1471 -c listen_addresses=' -l /var/tmp/pg1471/log start 2>&1 | tail -1
psql -h /var/tmp/pg1471 -p 5471 -U postgres -qc 'CREATE DATABASE ubyhost_test' && echo created
```

Expected: `server started`, `created`. `-E UTF8` is required: Python refuses a non-UTF8 server. Then, from `App/`:

```bash
export UBYHOST_TEST_DATABASE_URL="postgresql://postgres@/ubyhost_test?host=/var/tmp/pg1471&port=5471"
.venv/bin/python ../docs/tasks/1471-files/noop_check.py "$UBYHOST_TEST_DATABASE_URL" 2>&1 | tail -2
.venv/bin/python ../docs/tasks/1471-files/case_check.py "$UBYHOST_TEST_DATABASE_URL" a 2>&1 | tail -4
.venv/bin/python ../docs/tasks/1471-files/case_check.py "$UBYHOST_TEST_DATABASE_URL" b 2>&1 | tail -4
env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_db_postgres.py tests/test_go_schema_migrate.py -q -rs --tb=short 2>&1 | tail -3
```

Expected: `rows compared: 226; changed: 0`, `NOOP OK`; case a ends `table rewritten: False`, `indexes rebuilt: []`, `CASE a OK`; case b ends `after: deferrable_fks=6 c_columns=2 rows_intact=True duplicate_insert=refused`, `table rewritten: False`, `indexes rebuilt: ['idx_stay_fee_rate_apartment', 'stay_fee_rate_apartment_id_effective_from_key']`, `CASE b OK`; `60 passed` (needs `go` on PATH). Then stop and delete the server:

```bash
runuser -u postgres -- /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1471/data stop 2>&1 | tail -1; rm -rf /var/tmp/pg1471; unset UBYHOST_TEST_DATABASE_URL
```

If PostgreSQL cannot be started, write "PostgreSQL run: not done" in the report and set `Status: blocked`.

From the repo root: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | grep -E '1471|lint:' | tail -3` shows no line naming 1471.

## 7. Acceptance

- [ ] `git log --oneline --grep='^1471 step'` lists steps 1, 2, 3 and 5.
- [ ] `git show --stat <step 1>` = only `App/migrations_pg/00017_goose_parity.sql`; step 2 = only the golden (12 insertions); step 3 = only `App/tests/test_go_schema_migrate.py` (4+, 12-); step 5 = only the report and this brief's Status line.
- [ ] Hashes in steps 1-3 match (or the documented deviation).
- [ ] §6 as expected: `NOOP OK`, `CASE a OK`, `CASE b OK`, `23 passed`, `ok`, `60 passed`; the server is stopped and `/var/tmp/pg1471` is gone.

## 8. Stop and ask

Stop, and write the report, if: an expected value differs where a step says STOP; a test fails twice; `noop_check.py` or `case_check.py` prints `FAILED` (copy its lines into the report; never edit the migration); you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1471-report.md` (600 tokens at most) and set `Status: review`. It has: the files changed (`git show --stat` of each `1471 step` commit), each command with its last 5 lines, §7 ticked, Deviations, Questions, Owner steps left.

## Risk list (for the reviewer)

Full diff of `App/migrations_pg/00017_goose_parity.sql` (the `SET LOCAL lock_timeout` first; exactly 6 named FKs; the DO block alters only the 19 listed columns and only when not `C`; Down is the exact reverse; no `schema_migrations` row) and `App/tests/test_go_schema_migrate.py` (only the set and its comment change). The golden diff is one new key only.

## Owner steps

The migration reaches production by the normal deploy after the merge; nothing to run by hand. It may run before the owner checks anything; see "What happens on production". To check afterwards (read-only):

1. Open a terminal on the server and run `cd /opt/ubyhost/deploy/lightsail`.
2. Run `docker compose run --rm --no-deps ubyhost python scripts/pg_schema.py check --expect-database ubyhost`. Expected: a line ending `goose=17.` (or higher if a later goose file landed).
3. Run `docker compose exec -T postgres psql -U ubyhost -d ubyhost -At < /opt/ubyhost/docs/tasks/1471-files/prod_check.sql`. Expected: `6|19`.
4. If a deploy stopped with `canceling statement due to lock timeout`: nothing changed; run the deploy again.
5. Anything else: send the output to the orchestrator. Never run the migration's Down section.

## Notes for the coordinator

- known-issues: close the `[schema]` 1263 line (FKs without DEFERRABLE) once deployed; add that goose 00006-00015 dropped `COLLATE "C"` on 19 columns, fixed by 00017.
