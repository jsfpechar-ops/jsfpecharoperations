# 1135 report (executor run, Status: blocked)

Status: blocked. The run hit the 30-tool-call cap after step 2. Steps 3 and 4 are not applied.

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
- [ ] Steps 3 and 4 not run.
- [ ] Test-map rows not run.
- [ ] `git diff --stat` not checked against §3.
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
