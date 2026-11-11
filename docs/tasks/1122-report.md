# 1122 report

## Files changed

- `App/tests/test_sm_door_code_state.py`
- `App/tests/test_sm_payment_request.py`
- `App/tests/test_sm_site_booking.py`
- `docs/tasks/1122-sm-pin-demo-writers.md`
- `docs/tasks/1122-report.md`

## Commands

**Before (App/):** `.venv/bin/python -m pytest tests/test_sm_*.py -q --tb=short`
```
FAILED tests/test_sm_site_booking.py::test_no_other_code_touches_the_table_by_helper
3 failed, 97 passed in 5.63s
```

**After:** same command
```
................................                                         [100%]
104 passed in 4.98s
```

**Lint:** `python3 scripts/context_lint.py`
```
context lint: OK
```

## Acceptance (§7)

- [x] All `tests/test_sm_*.py` pass (104 passed, 0 skipped).
- [x] Only the three test files plus the two docs/tasks files changed.
- [x] No file under App/app changed.
- [x] Pushed to task/sm-round1-combined; no new PR.

## Deviations

None.

## Open questions (from §0)

1. Demo seeder uses draft→paid and draft→awaiting_payment via direct `db.update`; pinned as `DEMO_ONLY_MOVES`, table not widened — owner may want seeder to use `set_status` instead.
2. door_code / site_booking demo writes are INSERTs, not transitions.
3. PR #920 `context` job may still fail on `docs/context/decisions.md` token cap / conflict markers on main; not fixed here.
