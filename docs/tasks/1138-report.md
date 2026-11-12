# 1138 report

Status: blocked
Last commit: 6ac46357 (`1138 step 1`)

## 1. Files changed

- App/app/reporting.py (step 1 only): `claim_sendable` re-reads the guest stay window and `updated_at`, and the reservation dates and `updated_at`, and drops a pair that differs from what the payload was built from.

No Go file changed. No test file created. Steps 2 to 5 not started.

## 2. Commands

- Step 1: `cd App && .venv/bin/python -m pytest tests/test_filed_by_hand.py tests/test_connection_reuse.py -q --tb=short -x 2>&1 | tail -30`
  ```
  ...............................                                          [100%]
  31 passed in 6.01s
  ```
- Steps 2 to 6: not run.

## 3. Acceptance (§7)

0 of 7 ticked. Item 1 (`grep -n "stay_from" App/app/reporting.py` shows the new compare) is satisfied by step 1 but the brief's item list was not completed.

## 4. Deviations

Done: steps 1. Left: steps 2 to 6.

Stopped at step 2 under §8. Step 2 creates `App/tests/test_claim_recheck_stay.py`, which uses the `fresh_db` fixture. That fixture exists only as a module-local fixture in `App/tests/test_connection_reuse.py` (and also in `App/tests/test_deadline_cap_filing.py`). There is no `conftest.py` that defines it, so pytest cannot resolve it from the new file. The brief says to stop when `fresh_db` is not found. The file was not created.

## 5. Questions

1. Should `fresh_db` be copied into `test_claim_recheck_stay.py`, or moved to `App/tests/conftest.py`? The second option touches a file outside §3. The brief names neither.

## 6. Owner steps left

1. Answer question 1, then the orchestrator updates the brief and a fresh executor session continues from step 2.
2. No push, PR or merge has been made.
