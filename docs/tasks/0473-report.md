# 0473 report: deploy.sh on PostgreSQL

## Files changed
- deploy/lightsail/scripts/deploy.sh: PG_MODE switch; missing-e-mail check and row counts through the db layer (both modes); PG backup check (ubyhost-pg.dump.age), SQLite copy and integrity check skipped in PG mode; goose apply before `up` in PG mode ("Goose apply failed." exit 1); post-deploy sqlite3 integrity check skipped in PG mode.
- App/scripts/migrate_encrypt_doc_fields.py: open_database() uses to_regclass('public.guest') in PG mode; new _vacuum() helper skips VACUUM on PG (both call sites).
- App/tests/test_pg_migrate_encrypt_doc_fields.py (new): PG test, skips without UBYHOST_TEST_DATABASE_URL.
- docs/context/rules.md: one line, goose files must be additive.
- docs/tasks/0473-deploy-on-postgresql.md: Status review.
- docs/tasks/0473-report.md: this file.
- App/scripts/backfill_legal_acceptance.py: unchanged (no SQLite-only code).

## Commands
- `bash -n deploy/lightsail/scripts/deploy.sh`: clean. shellcheck is not installed, so not run.
- SQLite: `.venv/bin/python -m pytest tests/test_pii_encryption.py tests/test_pg_migrate_encrypt_doc_fields.py -q --tb=short -x -rs | tail -30`
  `14 passed, 1 skipped` (the skip is the PG test, which needs UBYHOST_TEST_DATABASE_URL).
- PostgreSQL: `UBYHOST_TEST_DATABASE_URL=postgresql://postgres:ubyhost@127.0.0.1:5432/ubyhost_test .venv/bin/python -m pytest tests/test_pg_migrate_encrypt_doc_fields.py -q --tb=short -x -rs | tail -30`
  `1 passed in 1.07s`, 0 skipped. First run failed on the 32-character minimum for UBYHOST_SECRET_KEY in the test; the test key was lengthened and nothing else changed.
- `python3 scripts/context_lint.py | tail -3`: `context lint: OK`.

## Section 7 acceptance
- [x] bash -n clean
- [x] script tests green on SQLite and PostgreSQL
- [x] in PG mode no executed line of deploy.sh calls sqlite3 (remaining sqlite3 lines sit only in the SQLite branches)

## deploy.sh blocks by mode
| Block | SQLite | PostgreSQL |
|---|---|---|
| PG_MODE flag | unchanged behaviour | set from UBYHOST_DATABASE_URL |
| Missing-e-mail check | `db.query_one` count (same message) | same |
| Backup check | age file check, `.backup` copy, integrity_check | checks ubyhost-pg.dump.age is non-empty and age |
| Before row counts | db layer | db layer |
| Migration | dry-run on copy | `pg_schema.py apply --expect-database ubyhost` before `up` |
| Post-deploy | integrity_check and counts | counts only |

## Deviations
- VACUUM guarded on PG: the brief did not name it. It is a SQLite file rewrite for secure_delete and is not valid on PostgreSQL.
- Row counts in SQLite mode also go through the db layer, as step 2 says ("both modes").
- The PG test is a new file, not an addition to test_pii_encryption.py.
- Single commit, not one per step, per the brief-run instructions.
- The commit trailer names Claude Opus 5.5 as instructed. The executor is Haiku 5.5.

## Not verified
- deploy.sh was not run end to end (no server). Only the bash syntax and the two scripts' tests ran.
- backfill_legal_acceptance.py was not run on PostgreSQL.

## Owner steps left
- Review and merge through scripts/merge-pr-on-green.sh. Do not push or merge from here.
- Deploy manually on the server, which runs the goose apply on production.
