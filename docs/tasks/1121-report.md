# 1121 report

Status: review

## Files changed

```
 App/app/reporting.py                              | helper added
 App/app/routes/admin.py                           | +5
 App/app/routes/guest.py                           | +10/-1
 App/tests/test_submission_duplicate_blocked_edit.py | new
 docs/tasks/1121-sm-duplicate-blocked-edit.md
 docs/tasks/1121-report.md
```

(`test_sm_guest_submit_state.py` unchanged.)

## Commands (last lines)

- Step 1: `assert 'pending' == 'blocked'` ×2; `2 failed, 4 passed` (host unreported-field + guest resave)
- Helper smoke: `False`
- After fix: `6 passed in 1.73s`
- Pin: `10 passed in 0.45s`
- Neighbours: `53 passed in 3.05s`
- Filing without endtoend: `667 passed`; endtoend alone: `28 passed`
- Guest non-browser: `614 passed in 33.98s`
- Guest with `test_guest_browser_e2e.py`: fails mkdir `/mnt/project-files` (PermissionError); not caused by this change
- `context lint: OK`; `edit_keeps_duplicate_block` counts 1/1/1

## §7 Acceptance

- [x] Step 1: two named tests failed at BLOCKED assertion
- [x] New file: 6 passed
- [x] Pin test passes; not in diff
- [x] Only §3 files
- [x] Helper greps 1,1,1
- [x] Filing 0 failed; guest non-browser 0 failed
- [x] Context lint: no ERROR naming 1121

## Deviations

- Guest browser e2e cannot write `/mnt/project-files/ux-shots` in this environment. Non-browser guest row: 614 passed. No template change.
- Endtoend run separately (known trap).

## Questions

None (open questions 1–6 for owner/orchestrator).

## Owner steps left

1. Merge combined PR when green.
2. Later: host banner copy (open question 1); OPERATIONS.md tense (open question 5).
