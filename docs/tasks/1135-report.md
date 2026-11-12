# 1135 report (executor run, Status: blocked)

Status: blocked. Steps 3 and 4 are applied and their tests pass. Blocked only on `context_lint.py` (see Deviations).

Continuation run (1135-cont-1): step 3 is commit `ecf5093c`, step 4 is commit `387ee783`.

- `App/app/door_codes.py` (step 3): reactivated DELETE is now `WHERE id = ? AND state = ?` with a `removed` rowcount check before the audit.
- `App/tests/test_sm_door_code_state.py` (step 4): line 39 pin changed from `ANY` to `("revoke_failed", "revoke_pending")`.
- `pytest tests/test_door_code_cancel_guard.py`: `7 passed`.
- `pytest tests/test_sm_door_code_state.py`: `11 passed`.
- `pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py -x -rs`: `243 passed, 2 skipped` (both skips are browser files, playwright not installed).
- `pytest tests/test_sm_reservation_claim_state.py tests/test_claim_*.py -rs`: `118 passed`.
- `python3 scripts/context_lint.py`: FAIL, `ERROR docs/tasks/1135-cont-1.md: missing section '## 2. Context'` (also `## 5`, `## 6`, `## 7`, `## 9`). Brief 1135-cont-1 is not in the brief template. Not fixed here: that file is outside §3.

Branch: `worktree-agent-a2b966eda3e24be90`. Last commit: `d38b1999` (`1135 step 2`). Step 1 is `0ab5daf6`.

## Files changed

- `App/tests/test_door_code_cancel_guard.py`: step 1, three tests appended.
- `App/app/door_codes.py`: step 2, `_keep_issued` UPDATE guarded with `AND state IN (?, ?)` and the comment added.
- The brief was not in this worktree. It exists only in commit `3020e7ea` on `claude/clever-fermi-tudhnt`, so its `Status:` line was not changed here.

## Commands (last 5 lines)

Step 1 (before the fix), `pytest tests/test_door_code_cancel_guard.py -q --tb=short`:
```
    assert _state(row) == "revoked"
E   AssertionError: assert 'issued' == 'revoked'
...
FAILED tests/test_door_code_cancel_guard.py::test_reactivated_delete_leaves_a_row_that_moved_on
2 failed, 5 passed in 0.50s
```
Matches the brief: the two named tests fail.

Step 2, `pytest tests/test_door_code_cancel_guard.py -q --tb=short -k keep_issued`:
```
..                                                                       [100%]
2 passed, 5 deselected in 0.55s
```

## §7 acceptance

- [x] Step 1 shows the two named tests failing before the fix.
- [x] Steps 3 and 4 pass.
- [x] Door-code and claim test-map rows pass (0 failed).
- [ ] `context lint: OK` not reached (brief 1135-cont-1 format, see Deviations).
- [x] `git diff b8d4a0f6 HEAD --stat` shows only the two §3 App files for steps 3-4.
- [x] `TRANSITIONS` not touched.

## Deviations

- `App/.venv` did not exist in the worktree or in the main checkout. I created it with `python3 -m venv` and installed `App/requirements.txt` and `App/requirements-dev.txt`. It is git-ignored.
- Tool-call budget was spent on environment setup (venv, dependencies, brief lookup) and on commands the shell refused (compound `cd` chains), so step 3 and step 4 were not reached.

## Questions

- Where should the brief live for execution? It is only on `claude/clever-fermi-tudhnt`, not on `main`.

## Owner or orchestrator steps left

1. Apply step 3 (`DELETE ... AND state = ?` with `removed` rowcount check in `_handle_cancellations`) and step 4 (test pin at `App/tests/test_sm_door_code_state.py` line 39) from the brief.
2. Run the test-map door-code rows and `python3 scripts/context_lint.py`.
3. Then set the brief `Status: review` and open the PR (the orchestrator does this per the run overrides).
