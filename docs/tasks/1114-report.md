# 1114 report

Status: review

## Files changed

```
 App/app/reporting.py                  | 19 ++++++++++++------
 App/tests/test_sm_submission_state.py |  4 ++--
 App/tests/test_stale_submission.py    | 38 +++++++++++++++++++++++++++++++++++
 go/internal/ubyport/recover.go        | 24 ++++++++++++++++++----
 go/internal/ubyport/recover_test.go   | 38 +++++++++++++++++++++++++++++++++++
 docs/tasks/1114-sm-submission-recovery-guard.md
 docs/tasks/1114-report.md
```

## Commands (last lines)

- Step 1 fail: `E   assert 1 == 0` / `1 failed, 15 deselected`
- Step 3: `16 passed in 0.62s`
- Step 8: `fmt-ok`; TestRecover* SKIP (no Postgres); `ok`
- Step 10: `23 passed in 1.03s`
- Step 11a: `666 passed, 3 warnings in 24.49s` (0 failed)
- Step 11b: `28 passed in 2.97s`
- Step 12: `context lint: OK` (no WARN naming 1114 or §3)

## §7 Acceptance

- [x] Step 1 failed with `assert 1 == 0` before fix
- [x] Python recovery has `WHERE id = ? AND state = 'running'`
- [x] Go recovery has `WHERE id = $3 AND state = 'running'`
- [x] Steps 3, 10, 11 pass; step 8 `fmt-ok` and `ok`
- [x] diff --stat only §3 files (+ brief/report)
- [ ] CI `go` job green with TestRecoverKeeps... PASS (owner)

## Deviations

- Filing row: 666 passed (brief expected ~665, 1 skipped); 0 failed.
- Go tests SKIP locally (UBYHOST_TEST_DATABASE_URL unset); CI runs them.

## Questions

None new; Open questions 1–2 remain for the owner.

## Owner steps left

1. Decide Open questions 1–2 in decisions.md.
2. Merge combined PR when green, including `go` job.
