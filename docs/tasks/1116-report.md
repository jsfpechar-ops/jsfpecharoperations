# 1116 report

Status: review

## Files changed

```
 App/app/door_codes.py                | 11 +++++++----
 App/tests/test_door_code_cancel_guard.py | new
 App/tests/test_sm_door_code_state.py |  4 ++--
 docs/tasks/1116-sm-door-code-cancel-guard.md
 docs/tasks/1116-report.md
```

## Commands (last lines)

- Step 1: `assert 'revoked' == 'issuing'`; `assert None == 'issuing'`; `2 failed, 2 passed`
- Steps 2–3: `4 passed in 0.30s`
- Step 5: `11 passed in 1.09s`
- Step 6 without `*_browser.py`: `251 passed in 6.58s`
- Step 6 with browser file: fails launching webkit (`Executable doesn't exist ... webkit-2359`); chromium present, webkit not. Not caused by this change (no template/CSS touch).
- `context lint: OK`

## §7 Acceptance

- [x] Step 1: 2 failed, 2 passed
- [x] Both guards present (PENDING/RETRYING and ISSUED)
- [x] cancel_guard: 4 passed
- [x] sm_door_code_state: all passed; only two PINNED lines
- [x] §3 files only
- [x] Non-browser door-code row: 0 failed
- [x] Context lint OK

## Deviations

- Step 6 browser file fails locally (missing Playwright webkit). Non-browser door-code/ttlock row: 251 passed.
- Pin anchors for `_handle_cancellations` were still present despite demo-seeder pin additions on main.

## Questions

None (open questions 1–7 left for owner/orchestrator).

## Owner steps left

None beyond combined-PR merge when CI green.
