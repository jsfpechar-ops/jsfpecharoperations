# Plan: retire SQLite

Status: proposal, 2026-11-13. Nothing here starts until the owner approves it.
Finishes [migration plan v4](postgresql/migration-plan-v4.md) steps 9, 10 and 18; runs beside [go-full-move](go-full-move.md) lanes D and X.
Goal: PostgreSQL is the only database, and the goose files in `App/migrations_pg/` are the only schema authority, applied by Go, also on an empty database.

## 1. Where SQLite still is

Checked in the code on 2026-11-13 unless the row says "doc".

| Area | What | Files | Still needed for |
|---|---|---|---|
| Runtime default | `UBYHOST_DATABASE_URL` unset means SQLite; `sqlite3` connections, file lock at startup | `App/app/db.py` (2,409 lines), `App/app/config.py` | tests; rollback |
| SQL dialect | Python's queries are written in SQLite dialect and translated per statement on PostgreSQL (`adapt_sql`, `IS` to `IS NOT DISTINCT FROM`) | `App/app/db_postgres.py` (812 lines) | production (until Python is deleted) |
| Schema authority | 44 SQLite migrations (0002-0045) plus `SCHEMA` and `ADDED_COLUMNS` in `db.py`. `apply_postgresql_schema` translates and runs all of them, then the goose files | `App/app/migrations/`, `db.py` `_postgres_schema_ddl`, `db_postgres.render_ddl`, `App/scripts/pg_schema.py` | production schema apply; first-time setup |
| Goose files | 16 files: `00001_baseline` (pg_dump of schema version 33, 4,216 lines, includes the PostgreSQL triggers and `schema_migrations` rows 1-33) plus 15 more; 12 of them are twins of SQLite 0034-0045 and also insert their `schema_migrations` row | `App/migrations_pg/` | production (no-ops there today); every Go test database |
| Startup check | Python validates PostgreSQL against columns built from SQLite `SCHEMA` in memory and expects schema version 45 | `db.py` `_expected_sqlite_columns`, `validate_postgres_schema` | production (until Python is deleted) |
| Rollback path | `pg-cutover.sh rollback` switches `.env` back to SQLite; `restore.sh` restores SQLite snapshots; `deploy.sh` keeps a SQLite backup and `integrity_check` branch for non-PG mode | `deploy/lightsail/scripts/` | rollback |
| Ops tooling | `sqlite3` installed on the server and checked in preflight; transfer script | `setup-server.sh`, `deploy-preflight.yml`, `App/scripts/sqlite_to_postgres.py`, `migrate_encrypt_doc_fields.py`, `migrate_encrypt_signatures.py` | rollback; nothing |
| Litestream | Retired 2026-11-07 (doc: `deploy/lightsail/README.md`); no Litestream service in compose (checked). Old S3 replica kept as archive | `deploy/lightsail/README.md` | nothing |
| Restore drill workflow | `restore-drill.yml` named in v4 step 9 does not exist in `.github/workflows/`; drills were run by hand (doc: status, 11-09) | none | nothing |
| Tests | Default suite and every browser shard run on SQLite. 77 of 769 test files name SQLite, 58 import `sqlite3`; 22 files carry 62 `sqlite_only` marks. `test-postgres-full` runs the whole suite on PostgreSQL minus `sqlite_only`, about 30 min | `App/tests/`, `App/tests/conftest.py`, `.github/workflows/ci.yml` | tests |
| Go | Builds test databases from goose files only; `ubyhost-web` refuses to start while a goose file is pending. PR #982 adds `migrate plan/check/apply`, refuses an empty database | `go/internal/schema/`, `go/cmd/ubyhost-web/register_schema.go` | nothing (Go needs PostgreSQL only) |
| Docs | 38 docs outside archive and tasks name SQLite: `ENVIRONMENT` (`UBYHOST_DB`), `LIGHTSAIL` (13), `OPERATIONS` (6), `SECURITY` (4), `rules` (4); `RETENTION` and `ROPA` name none | `docs/` | nothing once the steps below are done |

## 2. Target state

1. Production, staging, CI and Go tests use PostgreSQL only; no `sqlite3` binary, no SQLite file, no rollback script.
2. `App/migrations_pg/` alone builds an empty database identical to production's schema, seed rows included.
3. `ubyhost-go migrate apply` is the only thing that changes the schema, on an empty or an existing database.
4. `App/app/migrations/` is frozen at 0045 and deleted with Python in lane X3.
5. Until X3, SQLite lives on only as the Python suite's in-process test database (section 5).

## 3. Ordered steps

Tiers as in [workflow](../context/workflow.md#roles-and-models): A = migrations, deploy, data loss; B = ordinary code; C = docs only.

| # | Step | Tier | Depends on | Files it may touch | Switch and rollback | Owner step |
|---|---|---|---|---|---|---|
| S1 | Freeze: a test fails a PR that adds or edits a file in `App/app/migrations/`; new schema changes are goose-only | A | none | new `App/tests/test_sqlite_migrations_frozen.py`, `docs/LIGHTSAIL.md` twin paragraph | revert the PR | approve decision 1 |
| S2 | Fix the 6 drifted foreign keys: goose `00017` runs `ALTER TABLE ... ALTER CONSTRAINT ... DEFERRABLE INITIALLY IMMEDIATE` (a no-op on production, which already has it) | A | none | `App/migrations_pg/00017_fk_deferrable.sql` | Down section restores the goose-only form; production unchanged | apply with `pg_schema.py apply` after merge |
| S3 | Equivalence proof in CI: build database A with Python's apply, database B from goose files only, diff `pg_dump --schema-only --no-owner` of both (normalised) plus a data dump of `schema_migrations` and `goose_db_version` | A | S2 | new `App/tests/test_goose_equivalence.py`, `ci.yml` `test-postgres` job | test only | none |
| S4 | Production comparison: owner takes a read-only `pg_dump --schema-only` of production; the S3 check diffs it against B | A | S3 | `deploy/lightsail/scripts/pg-schema-dump.sh` (new, read-only) | read-only | run the dump, hand over the file (no guest data in it) |
| S5 | 1263 twin parity test (written) | A | #982 | as in [1263](../tasks/1263-go-schema-fix-2.md) | test only | merge #982 |
| S6 | Python's PostgreSQL apply becomes goose-only: empty database gets `00001`..`N`; the translated SQLite path is no longer run on PostgreSQL; `conftest` uses it | A | S3, S4 | `App/app/db.py` (`apply_postgresql_schema`, `bootstrap_empty_postgresql_schema`), `App/tests/conftest.py` | production has every goose row, so only pending files run; revert the PR | none |
| S7 | Go applies on an empty database: `migrate apply --init --expect-database <name>`, then the app role | A | #982, S3 | `go/internal/schema/migrate.go`, `target.go`, tests | flag only; rehearse on a staging scratch database | rehearse on staging |
| S8 | Production switch `UBYHOST_SCHEMA_APPLY=go` | A | S5, S6, S7 | `.env` on the server | set back to `python` | set the variable |
| S9 | Delete `pg_schema.py` and Python's apply (D1 end) | B | S8 plus two goose migrations applied by Go | `App/scripts/pg_schema.py`, `db.py`, CI `test-postgres` steps | revert the PR | none |
| S10 | Rollback-window proofs (see section 6) | A | none | `docs/OPERATIONS.md` checklist | none | all of section 6 |
| S11 | End the rollback path: remove `pg-cutover.sh`, SQLite parts of `restore.sh`, `deploy.sh`, `setup-server.sh`, preflight `sqlite3` check | A | S10 | those scripts, `deploy/lightsail/README.md`, `docs/LIGHTSAIL.md` | revert the PR; the archived SQLite copy stays until S12 | approve decision 3 |
| S12 | Archive and delete the SQLite file and old SQLite snapshots on the server | A | S11 plus 30 days | none in the repo | one age-encrypted offline copy until the date in decision 5 | do it by hand |
| S13 | Docs: `ENVIRONMENT`, `LIGHTSAIL`, `OPERATIONS` backup section, `SECURITY`, `rules` say PostgreSQL only | C | S11 | those docs | revert | none |
| S14 | Lane X3: delete SQLite runtime (`db.py` SQLite paths, `db_postgres.py` translation, `App/app/migrations/`, transfer and encrypt scripts, `sqlite_only` tests) together with `App/` | B | go-full-move X2 | `App/` | revert the PR | none |

What the S3 diff cannot see: rows outside the two version tables (backfills such as the `stay_fee_rate` insert in 00011, which do nothing on an empty database), sequence current values, grants and ownership (`--no-owner`; `pg-app-role.sh check` covers them), and column order (a goose `ADD COLUMN` lands last; differences in order are reported but are not errors). The tool is `pg_dump` 16 plus `diff`; both are in the image already, so no new dependency.

## 4. The ordering question

Recommendation: fix the schema authority now, leave the SQLite runtime to lane X.
- Now (needed for a safe Go port): S1 freeze, S2-S4 proof that goose alone equals production, S6 so PostgreSQL never again runs the translated SQLite files. After these, one authority exists for PostgreSQL and drift can only show up as a failing CI check.
- Now, but shell and docs only: S10-S13, because the rollback path is ops, not the 92,000 Python lines.
- Waits for X3: SQLite connections, the dialect translation (`adapt_sql` is what lets Python's SQLite-dialect SQL run on PostgreSQL, so it must stay while Python runs), `_expected_sqlite_columns`, SQLite tests. Removing these inside Python is work deleted again weeks later.
- Rule while both exist: a Python change that needs a goose-only column is tested in `test-postgres-full` and marked `postgres_only`; under the go-first rule such changes should be rare.

## 5. Tests

The suite already runs on PostgreSQL in `test-postgres-full`; only the 62 `sqlite_only` marks (SQLite file, migration runner, PRAGMA) are skipped there. Moving the default job and the browser shards to PostgreSQL would add a database service to every shard and roughly double the slow job; it buys nothing that `test-postgres-full` does not already prove.
Recommendation: keep SQLite as a test-only database until X3. New tests may not be `sqlite_only`; the merge script already refuses a red `test-postgres-full`. So "SQLite is gone" means gone from production, ops and schema authority on S11; gone from the repo on X3.
Not determined: how many tests fail on PostgreSQL today (CI logs not read; the job is green on recent PRs per the #982 history, with flakes).

## 6. Risks

The production database holds real data (2026-11-13 check: about 117 guests, 28 submissions, 14 stay-fee filings, 6 accounts; real or test is unknown). "No users yet" relaxes no step below.

| Risk | What prevents it |
|---|---|
| Data loss at the end of the rollback window | Before S11 and S12, all of these exist: (a) a decrypt test of one `.age` backup with the owner's key (does not exist yet); (b) `pg-restore.sh` of a fresh dump into a scratch database on staging with row counts matching production; (c) the Drive copy runs daily (doc: owner check 11-13, test upload passed) and the S3 copy is current; (d) one age-encrypted copy of the last SQLite file kept offline until decision 5 |
| Goose baseline differs from production | S3 in CI on every PR plus the one-off S4 production dump; S8 waits for both |
| A migration added on one side only | S1 freezes SQLite; S5 checks twins; S3 catches anything else |
| A rehearsal touches production | Every apply carries `--expect-database`; rehearsals run on staging or scratch databases only; S4 is read-only and run by the owner |
| Go `--init` run against a full database | `--init` refuses any schema with user tables; the `--expect-database` guard names the target |

## 7. Owner decisions

1. Freeze `App/app/migrations/` at 0045 now, new schema changes goose-only? Recommend yes.
2. Python's PostgreSQL apply switches to goose files only (S6)? Recommend yes.
3. End the SQLite rollback path once the section 6 proofs exist? Recommend yes; please confirm the cutover date (not found in the docs).
4. Keep SQLite as the Python suite's test database until lane X3? Recommend yes.
5. Keep one encrypted offline copy of the last SQLite file for 30 days after S11, then delete it? Recommend yes.
6. Let Go `migrate` build an empty database with `--init` (S7)? Recommend yes.

## 8. First briefs to write (start now)

| # | Brief | Tier | Files |
|---|---|---|---|
| 1470 | S1 freeze test for `App/app/migrations/` | A | new `App/tests/test_sqlite_migrations_frozen.py`, `docs/LIGHTSAIL.md` |
| 1471 | S2 goose `00017` makes the 6 foreign keys deferrable | A | `App/migrations_pg/00017_fk_deferrable.sql`; rebase on #982 if it lands first (its goose golden file changes) |
| 1472 | S3 goose-only versus Python schema diff in CI | A | new `App/tests/test_goose_equivalence.py`, `.github/workflows/ci.yml` |
| 1473 | S4 read-only production schema dump script plus the S10 proof checklist | A | new `deploy/lightsail/scripts/pg-schema-dump.sh`, `docs/OPERATIONS.md` |

Next: 1474 (S6, after 1472 and 1473), 1263 and 1475 (S7) after #982 merges, 1476 (S11) and 1477 (S13) after the section 6 proofs.
