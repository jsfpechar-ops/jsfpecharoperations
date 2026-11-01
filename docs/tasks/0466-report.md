# 0466 report, part a (poll indexes and iCal digest)
Status: blocked

Files changed: `App/app/icalsync.py` (`body_digest` only), `App/tests/test_ical_digest.py` (new).

Commands:
- `.venv/bin/python -m pytest tests/test_ical_digest.py tests/test_ical_skip_unchanged.py tests/test_icalsync.py -q --tb=short -x 2>&1 | tail -30` gives `64 passed in 5.56s` (test_ical_digest alone: 5 passed).
- `tests/test_goose_migrations.py`: not run yet (step 6 command, next session).
- `python3 scripts/context_lint.py | tail -3`: see the final commit run.

Steps: 1 and 2 done (commit 20da81d). Step 3 done: seed in `ubyhost_test_0466` (scratch, not committed): user_account 1, apartment 2000, reservation 40000, reservation_claim 40000, guest 80000, door_code 40000, email_outbox 100000, push_outbox 10000 (with push_subscription 1), guide_import 2000, cleaning_property 2000, cleaning_code 2000, ical_feed 2300.

Step 4 not finished (see Deviations).

Deviations:
- Done: steps 1 to 3. Left: steps 4 to 12. Step 4 partly run and its EXPLAIN output is not valid, because the job runs changed the seed: `push.drain` deleted subscription 1 with its 10,000 push_outbox rows, door_code cancellations deleted about 9,990 rows, and cleaning_event rows were created. EXPLAIN ANALYZE also executed INSERT, UPDATE and DELETE on the scratch data. Next session: drop and recreate `ubyhost_test_0466`, apply the schema, reseed, run each job once, then EXPLAIN. Scratch files: `/tmp/seed.sql`, `/tmp/seed0466/explain.py`, `/tmp/seed0466/explain_raw.txt`.
- Reason for stopping: the 25-tool-call checkpoint.
- Preliminary plans on the mutated data (for the next session to confirm): `SELECT r.id, r.apartment_id, r.date_to ... WHERE r.status = 'active' AND archived_at IS NULL` seq-scans reservation (8.8 ms), a candidate for `idx_reservation_active_date_to`. `SELECT reservation_id, provisional_until FROM reservation_claim WHERE state = ? AND provisional_until IS NOT NULL` seq-scans 40k rows (3.0 ms), a candidate for `idx_reservation_claim_provisional`; check that the partial index is picked when state is a bound parameter.
- Outside the step 5 list (stop condition, §8): `SELECT id FROM door_code WHERE state = ? AND notified_at IS NULL AND issued_at IS NOT NULL ORDER BY issued_at LIMIT ?` seq-scans door_code (3.4 ms) and `UPDATE door_code SET state ... WHERE state = ? AND valid_to IS NOT NULL AND valid_to < ?` seq-scans door_code (2.2 ms). No index added for these.
- Not exercised: `cleaning_codes.process_queue` (TTLock disabled, so it returns before any SQL) and the guide import jobs (tables under 10,000 rows).

Questions: should the two door_code statements get an index outside the step 5 list, or stay as they are (2 to 3 ms)?

Owner steps left: none.
