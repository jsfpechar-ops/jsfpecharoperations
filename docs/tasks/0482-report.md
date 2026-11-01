# 0482 report (executor: Haiku 5.5)
Status: blocked

Done: steps 1 to 4. Left: steps 5 and 6 (`go/internal/ubyport/outcome.go`, `outcome_test.go`), not started.

## Files changed
- `App/app/reporting.py`: step 1, outcome block moved verbatim into `plan_outcome` (only `receipt_submission_id(` became `receipt_lookup(`, plus the return dict). `submit_batch` unpacks the result into the old local names.
- `App/scripts/ubyport_golden_outcome.py` (new), `App/tests/golden/ubyport/outcome/cases.json` (15 invented cases), `expected.json` (generated).
- `App/tests/test_ubyport_golden_outcome.py` (new, 2 tests).
- `docs/tasks/0482-go-g5d1-outcome-plan.md` (Status only), this report.

## Commands
- `python3 scripts/ubyport_golden_outcome.py --out /tmp/g && diff ... && echo SAME` gives `SAME` (15 cases).
- pytest, 4 files with `-x`: `1 failed, 18 passed`. The 2 golden tests pass.
- pytest, `test_submission_retry_cap.py test_duplicate_guard.py test_stale_submission.py` without `-x`: `1 failed, 53 passed`.

## Blocker
`tests/test_submission_retry_cap.py::test_every_state_submit_batch_can_write_is_terminal` fails: `AssertionError: submit_batch never writes 'partial'`. The test reads the source of `submit_batch` and looks for each terminal state literal. Step 1 moved those literals into `plan_outcome`, as the brief asks. Fixing it means editing that test (outside brief section 3) or adding a dead literal to `submit_batch`. Not done; owner or orchestrator to decide.

## Deviations
- App/.venv does not exist. The oracle needed `python3 -m pip install -r App/requirements.txt` (fastapi was missing; installed the declared requirements, not a new dependency). Also installed pytest.
- Go steps not written. Notes for the next session: `exhausted` and `guest_writes` must be `[]` not `null` in JSON; `GuestWrite` needs `MarshalJSON` as `[id, values]`; `auto_attempts` is `max(0, x or 0)`; receipt pointer uses Python `or` semantics (0 and nil both fall through to the lookup).
- No PR opened (blocked).

## Owner steps left
- Decide how to handle the retry_cap source-text test (see Blocker), then the executor or orchestrator finishes steps 5 and 6.
