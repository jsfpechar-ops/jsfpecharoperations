# 1117 report

Status: review

## Files changed

```
 App/app/guest_guide_import.py        | 15 ++++++++++++++-
 App/tests/test_guest_guide_import.py | 31 ++++++++++++++++++++++++++++++-
 App/tests/test_sm_queues.py          |  8 +++++---
 docs/tasks/1117-sm-guide-import-stale-reset.md
 docs/tasks/1117-report.md
```

## Commands (last lines)

- Step 3 fail: `assert ('running', None, None) == ('failed', 'stale', None)`
- `STALE_RUNNING.total_seconds()`: `800`
- Step 7: `47 passed in 4.38s`
- Step 10: `4 passed in 0.27s`
- Step 11: `51 passed in 4.57s`
- Step 12: `context lint: OK`

## §7 Acceptance

- [x] Step 3 failed before fix; step 7 passes
- [x] Stale running → failed/stale; fresh untouched; no Apify call
- [x] test_sm_queues: 4 passed; process_queue pinned with 2 writes
- [x] Only §3 files in diff
- [x] Context lint clean

## Deviations

None material (combined branch; one commit for the brief).

## Questions

None; owner may overrule Decisions taken (failed vs re-queue; 800s cutoff).

## Owner steps left

1. Accept or overrule the two decisions.
2. Merge combined PR when green.
