# 1164 report: crash-stuck running batch recovered in every mode (K-F23), Python

Status: blocked (Postgres run not possible: the ubytest schema is absent; SQLite run green)

## Files changed
- App/app/reporting.py: `_recover_stuck_running_batches` plus one call at the top of `sweep()`
- App/tests/test_stale_submission.py: 3 helpers and 7 test cases (4 parametrized)
- docs/OPERATIONS.md: one sentence in the `submit` row
- docs/tasks/1164-report.md (this file)

## Commands (last lines)
- Step 1 (expect 4 failed, 3 passed): `4 failed, 3 passed, 16 deselected`
- Step 2 (expect 23 passed): `23 passed in 0.69s`
- Step 3 (expect 1): `1`; the 7 targeted tests then `7 passed`
- Step 4 bites, each restored with `git checkout` and back to `7 passed`:
  - BITE a FAIL: `4 failed, 3 passed` (PASS after restore: `7 passed`)
  - BITE b FAIL: `1 failed, 6 passed` (PASS after restore: `7 passed`)
  - BITE c FAIL: `6 failed, 1 passed` (PASS after restore: `7 passed`)
- Ruff (E9,F63,F7,F82,F401,F841): `All checks passed!`
- SQLite area run: `258 passed, 2 warnings in 18.27s`, 0 skipped
- Postgres area run: ERROR at setup. `RuntimeError: PostgreSQL schema is absent, outdated, or incompatible` on `UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest`. Postgres accepts connections; the schema is missing. `scripts/pg_schema.py` does not exist on this branch, so the schema could not be applied as the brief expects.
- `python3 scripts/context_lint.py`: `context lint: OK` (WARN: 6 App/ commits after the last status.md update; orchestrator's to fix)

## Acceptance (section 7)
- [x] stuck row in manual, inactive and auth-failed apartments becomes outcome_unknown, pointer set, critical alert, `_send_in_flight` True, no send (tested)
- [x] live claim (10 s) in manual mode left alone
- [x] auto apartment: two sweeps leave one alert
- [x] other workspace untouched
- [x] bites a, b, c as above
- [ ] Postgres area run (blocked, see above)

## Deviations
- Bite (b): the brief's two anchors are not unique (the same tuple line appears 3 times in reporting.py). The mutation used the two-line anchor at the new helper's query instead. Same intent.
- Postgres run not executed (schema absent, no pg_schema script). Done: steps 1 to 5 except the Postgres run.

## Questions
- Should the ubytest Postgres schema be applied, and by which command, so the Postgres area run can be done?

## Owner steps left
- None from this brief. Brief 1164b (Go) is still to do before merge.
