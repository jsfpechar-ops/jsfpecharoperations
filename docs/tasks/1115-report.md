# 1115 report

Status: review

## Files changed

```
 App/app/claim.py                             | 25 +++++++++++++++++++++++--
 App/tests/test_claim_start_guard.py          | new
 App/tests/test_sm_reservation_claim_state.py | 14 ++++++++------
 docs/tasks/1115-sm-claim-start-guard.md
 docs/tasks/1115-report.md
```

## Commands (last lines)

- Step 2 fail: `assert 'provisional' == 'claimed'`; `assert 'second@claim.test' == 'third@claim.test'`; `2 failed`
- After fix: `2 passed in 0.72s`
- Pin+guard: `12 passed in 2.64s`
- `tests/test_claim_*.py`: `108 passed`
- Filing without endtoend: `661 passed`
- `test_endtoend.py` alone: `28 passed`
- `context lint: OK`

## §7 Acceptance

- [x] Step 2 showed 2 failed before fix
- [x] `grep -c 'AND state = ? AND token_version = ?'` = 1
- [x] First §6 command area: 12 passed
- [x] Test-map: 0 failed (endtoend alone 28 passed)
- [x] Only §3 files in the diff

## Deviations

- Step 6 (pin fail before AS_READ) not run as a separate command; pin edits applied with steps 7–11 after guard tests passed.
- `test_claim_*.py` count 108 (brief writer saw 118); 0 failed.
- Skipped per-brief branch/push/PR (combined branch).

## Questions

None (open questions left for owner/reviewer).

## Owner steps left

1. Merge combined PR when CI green via `scripts/merge-pr-on-green.sh`.
