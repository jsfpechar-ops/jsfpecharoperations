# 1140 report: window fit inside the locked transaction

Status: review
Branch: exec-1140 (not pushed, no PR). HEAD at report time: 2ee72fff (steps 1 to 6 committed).
Brief base: 8e512d47 per brief; actual HEAD before step 1 was 8c3e4edf (brief anchors matched).

## 1. Files changed (git diff 8c3e4edf --stat)

- App/app/icalsync.py (+helper, `_fit_windows_in_tx`, sync_feed call sites)
- App/tests/test_icalsync.py (+4 tests, `import pytest`)
- go/internal/ical/reconcile.go (`fitUnsentGuestWindows` on pgx.Tx, `liveClaimInTx`)
- go/internal/ical/reconcile_test.go (`TestFitUnsentGuestWindows` runs in a tx)
- go/internal/ical/syncfeed.go (`dateMove`, helper, call sites)
- go/internal/ical/syncfeed_test.go (3 calls get `nil`, +2 tests)

## 2. Commands (last 5 lines)

- Python, icalsync + skip-unchanged (step 2 and 3): `63 passed` then `67 passed in 7.61s`.
- Python step 8 set: `382 passed, 1 warning in 20.85s` (warning is a pre-existing utcnow deprecation in mail.py).
- Go, targeted (step 6): `ok github.com/.../go/internal/ical 9.937s` with 2 new tests PASS.
- Go step 8: `ok .../internal/ical 13.484s`, `ok .../internal/ubyport 37.544s`. SKIP count in -v output: 0.
- `go vet ./internal/ical/ ./internal/ubyport/`: no output. `gofmt -l internal`: no output.
- `python3 scripts/context_lint.py | tail -3`: `context lint: OK` (warning about status.md is for the orchestrator).

## 3. Section 7 acceptance

- [x] `_fit_unsent_guest_windows` count 0; `_fit_windows_in_tx` count 2.
- [x] 4 Python tests and 2 Go tests pass; no SKIP.
- [x] Revert-bites: Python (a) 5 tests FAIL, (b) `test_a_host_edit_during_the_sync_logs_deferred_changed` FAIL, (c) `test_a_deferred_date_move...` FAIL. Go (a) `TestDateMoveFitsGuestWindowsInTheSameTransaction` FAIL, (b) `TestDeferredDateMoveChangesNeitherStayNorWindows` FAIL. All restored; files match the step commits.
- [ ] `IS NOT DISTINCT FROM` count in syncfeed.go is 1, not 2 (see Deviations).
- [x] `pg_advisory_xact_lock`: syncfeed.go 0, reconcile.go 1.
- [x] Deferred moves leave stay and windows unchanged (tests above).
- [x] test_sm_* pass, vet and gofmt clean, context lint OK.

## 4. Deviations

- Step 5d: the brief's old text had different indentation. I applied the same change to the actual indentation (the `moved` block sits at 3 tabs).
- Step 7 expected `2` for `IS NOT DISTINCT FROM` in syncfeed.go. The brief's own SQL has both predicates on one line, so the count is 1. Code matches the brief; the expected count looks like a miscount in the brief.
- Mid-step-6 I made a stray backup of syncfeed.go one directory above the worktree. Deleted at once; nothing else touched outside the worktree. My sed restore of the Go revert-bite (b) also changed a second `move.Reason = "claimed"` line; fixed and checked against HEAD.
- Used Python one-off scripts (per the brief's own heredoc steps) for the delete and tab-sensitive edits.

## 5. Questions

- Confirm the step 7 expected count of 2 (should it be 1?).

## 6. Owner steps left

- Review (reviewer reads the Risk list in the brief). Then merge via `scripts/merge-pr-on-green.sh` once a PR exists and the draft may ship. Nothing pushed.
