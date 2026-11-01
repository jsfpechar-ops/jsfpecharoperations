# 0466 report, part a (poll indexes and iCal digest)
Status: blocked

Files changed (vs origin/main): `App/icalsync.py` (`body_digest` only), `App/tests/test_ical_digest.py` (new), `App/migrations_pg/00002_poll_indexes.sql` (new, two indexes), `App/tests/test_goose_migrations.py` (one test, see Deviations), `docs/tasks/0466-report.md`.

Commands (last lines):
- SQLite, part a set (`tests/test_ical_digest.py tests/test_ical_skip_unchanged.py tests/test_icalsync.py tests/test_goose_migrations.py`): `66 passed, 4 skipped in 5.58s` (the 4 skips are the PostgreSQL-only goose tests, expected).
- PostgreSQL 16, same four files, `UBYHOST_DATABASE_URL` and `UBYHOST_TEST_DATABASE_URL` = `ubyhost_test_0466_goose`: `69 passed, 1 skipped in 26.94s` (the skip is `test_ical_skip_unchanged.py:191`, sqlite_only).
- PostgreSQL 16, `tests/test_db_postgres.py`: `55 passed in 28.91s`, 0 skipped.
- `python3 scripts/context_lint.py | tail -3`: `context lint: OK` (plus a WARN that status.md is behind; orchestrator's job).

Seed (`ubyhost_test_0466`, scratch, not committed): user_account 1, apartment 2,000, reservation 40,000 (36,000 active), reservation_claim 40,000 (2,000 provisional), guest 80,000, door_code 40,000, email_outbox 100,000, push_outbox 10,000 (+ push_subscription 1), guide_import 2,000, cleaning_property 2,000, cleaning_code 2,000, ical_feed 2,300. `/tmp/seed.sql` stopped at push_outbox (no subscription row): added the subscription row and ran the rest (`/tmp/seed0466/seed_tail.sql`). push_outbox URLs set to `127.0.0.1:9` so nothing leaves the machine.

Step 4: each of the 11 job functions ran once on a fresh seed with statement logging (connection options). Distinct logged SELECT/UPDATE/DELETE statements: 25 with parameters; `pg_advisory_xact_lock` skipped (removed in part b). `door_codes.reconcile` returns early unless `UBYHOST_DOOR_CODES=1`, so its two timer statements were explained by hand with the constants from door_codes.py (state `issued`, batch 20; expiry to `expired`). Each EXPLAIN ran inside BEGIN ... ROLLBACK on a fresh seed. Raw plans: `/tmp/explain.txt` (before, then after).

Step 5 index decisions (plan time before, then after):
- `SELECT r.id, r.apartment_id, r.date_to ... WHERE r.status='active' AND archived_at IS NULL AND date_to >= ?` (1 run): Seq Scan on reservation, 7.160 ms, then Bitmap Index Scan on `idx_reservation_active_date_to`, 3.201 ms. Index added.
- `SELECT reservation_id, provisional_until FROM reservation_claim WHERE state = ? AND provisional_until IS NOT NULL` (2 runs): Seq Scan, 2.814 ms, then Index Scan on `idx_reservation_claim_provisional`, 0.723 ms. Index added.
- `DELETE FROM push_outbox WHERE subscription_id = ?` (1 run, push.drain when a device is gone): Seq Scan on 10,000 rows, 10.036 ms, then 7.862 ms. NOT indexed: needs an index outside the step 5 list (brief section 8 stop). Owner decision.
- door_code notified/issued SELECT: Bitmap Index Scan on `idx_door_code_due`, no Seq Scan on the fresh seed, 3.455 ms, then 3.987 ms (noise). Nothing added (orchestrator rule). The earlier seq scan came from the mutated data.
- door_code valid_to expiry UPDATE: Bitmap Index Scan on `idx_door_code_due`, 2.913 ms, then 3.067 ms. Nothing added.
- `SELECT r.*, ... JOIN reservation_claim` (1 run): Index Scan on reservation_pkey, 57.5 ms, then 37.0 ms. Only Seq Scan is on apartment (2,000 rows). No index.
- All other statements: index scans, or Seq Scan on tables under 10,000 rows (apartment, ical_feed, push_subscription, settings, alert with 0 rows). No index.

Not measured at volume (tables not in the seed list, so the plans are on empty tables): `cleaning_event` (UPDATE ... WHERE source_reservation_id = ?, run 4,706 times per reconcile, Seq Scan) and `alert` (UPDATE by dedupe_key, 32,991 runs). They may Seq Scan at production size. No index added.

Step 5 file: `App/migrations_pg/00002_poll_indexes.sql`, applied with `scripts/pg_schema.py apply` (goose=2).

Deviations:
- Done: steps 4 and 5 (the two listed indexes). Steps 6 to 12 are part b and were not run. Step 5 stopped short of acceptance: the push_outbox DELETE still seq-scans a 10,000-row table after 00002, so brief section 7 is not met.
- Test change: `tests/test_goose_migrations.py::test_a_current_schema_without_goose_table_adopts_baseline` asserted no goose files pending after adoption. With 00002 it correctly reports goose 2 pending. The test now expects that, applies, and then passes. Not in the brief; needed for the new file.
- Commit trailer: Co-Authored-By Claude Haiku 5.5 (the model that ran this), not Opus 5.5 as the launching brief said.
- Owner deploy step: on PostgreSQL the app refuses to start until goose 2 is applied (per the 0465 design). Before or at deploy, from `App/` on the production host: `UBYHOST_DATABASE_URL=<prod url> .venv/bin/python scripts/pg_schema.py apply --expect-database <prod db name>`, expecting `goose=2`.

Questions:
1. Add `idx_push_outbox_subscription (subscription_id)` for the push DELETE (10 ms at 10,000 rows, only when a device is removed)? Or accept it?
2. Seed `cleaning_event` and `alert` at volume and re-measure? If they Seq Scan, which indexes do you want?

Owner steps left: the deploy command above (after merge); answers to questions 1 and 2.
