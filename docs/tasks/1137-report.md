# 1137 report: operator pause outside TRANSITIONS, door-code guards

Status: review. Branch exec-1137, not pushed, no PR (owner instruction for this run).

## 1. Files changed (vs 116def7d, code only)

```
App/app/billing.py                       | 31 +-
App/app/billing_order.py                 |  6 +-
App/app/door_codes.py                    | 45 +--
App/tests/test_door_code_cancel_guard.py | 50 +++
App/tests/test_sm_billing_status.py      | 22 +-
App/tests/test_sm_door_code_state.py     |  8 +-
```

Commits: 56065c81 (step 1), c7e39451 (step 2), 24d35429 (step 3), 766c2c68 (step 4), 11132d20 (step 5), 8ac5d23d (step 6), e3ce7405 (step 7).

## 2. Commands (last lines of output)

- `pytest tests/test_sm_go_parity.py` (step 1): `14 passed in 2.45s`
- `pytest tests/test_sm_billing_status.py tests/test_sm_go_parity.py tests/test_billing_core.py` (step 3): `41 passed in 1.02s`
- `pytest tests/test_sm_door_code_state.py tests/test_door_code_cancel_guard.py` (step 4): `18 passed in 1.98s`
- `pytest tests/test_sm_door_code_state.py` (step 6): `11 passed in 2.20s`
- `grep -c 'AND state = ?' app/door_codes.py` (step 5): `8` (5 new guards plus 3 existing)
- `pytest tests/test_door_code_cancel_guard.py` (step 7): `10 passed in 0.45s`
- §6 target set (5 files): `62 passed in 2.44s`
- §6 `tests/test_billing_*.py -x`: `163 passed in 18.41s`
- §6 `tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py -x -rs`: `246 passed, 2 skipped in 7.72s`
- `python3 scripts/context_lint.py`: `context lint: OK` (one WARN about status.md staleness, orchestrator task)

## 3. §7 acceptance

- [x] `"trial_pending"` in billing.py shows `{"trialing"}` only.
- [x] test_sm_go_parity.py passes.
- [x] No `set_status(owner_user_id, "paused"` in billing_order.py.
- [x] Three new tests pass; §6 commands pass.
- [x] Lint says OK.

## 4. Deviations

- Step 7: the append of the three tests landed above one existing line (`assert _state(row) == "pending"`) of `test_reactivated_delete_leaves_a_row_that_moved_on`. Caught by the first run, moved back to its test before the commit. Final diff of that file removes no lines.
- §6 test-map skips: 2 tests skipped (`test_property_navigation_browser.py`, `test_ttlock_setup_0954_browser.py`) because `playwright` is not installed in App/.venv. Neither file is touched by this change. Not installed (hard rule 4).

## 5. Questions

- None open. The Haiku-side reading of executor.md ("browser tests: 0 skipped") conflicts with §6's "skips only for missing playwright". I followed §6.

## 6. Owner steps left

1. Review the PR diff for `App/app/billing.py` (`operator_pause`, the only move outside TRANSITIONS) and `App/app/door_codes.py` (`_keep_issued` lease condition and the five guarded writes in `_revoke_one`).
2. Push the branch and open the PR, then merge with `scripts/merge-pr-on-green.sh` when CI is green.
