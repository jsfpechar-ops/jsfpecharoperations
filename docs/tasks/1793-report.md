# 1793 report (executor run, stopped at brief §8)

Status: blocked. Steps 2 to 4 are committed. Stopped because the DB-backed tests skip (§8: "a test needs a skip").

## Commits
- de091a1 `1793 step 2`: host.go (SetQueueKick, kickQueue), host_codes.go (kick after ttlock and remove), cleaning_settings.tmpl (visible Delete code form; the `cleaning-remove` details block removed)
- a188a61 `1793 step 3`: go/cmd/ubyhost-web/cleaning_queue_kick.go (gated background pass)
- step 4 commit: host_codes_test.go (TestHostQueueKick, TestHostDeleteCodeButton), cleaning_queue_kick_test.go (gates, kick while running, failing pass)

## Command results (§6)
- `gofmt -l .` in go/: clean (no output).
- `go vet ./internal/web/cleaning/... ./cmd/...`: exit 0, silent apart from module download lines.
- `go test ./internal/web/cleaning/... ./cmd/ubyhost-web/... -count=1 -v`: exit 0, PASS, but 30 tests SKIP. Reason: `UBYHOST_TEST_DATABASE_URL is not set`. Skipped includes the new TestHostQueueKick and TestHostDeleteCodeButton, plus the existing host and golden DB tests. The four non-DB kick tests (TestCleaningKickGates, TestCleaningKickWhileRunning, TestCleaningKickFailingPass) pass. Unverified: the handler kick count, the Delete code form on the page, and that the existing DB tests still pass with the template change.
- `python3 scripts/context_lint.py`: "context lint: OK". The WARN lines name other open briefs about files this work did not touch.
- Browser layout lint (`test_layout_lint_browser.py`) and screenshots at 390, 768 and 1280 px: not run. No database and no browser in this run, so no screenshots and no per-page UX notes.

## Deviations
- The brief's §2 design says a `Kick` field on hostServer. §10.1 (exact diffs) uses a package variable `queueKick`. I followed §10.
- TestHostQueueKick's manual case posts an empty form. That only proves the rejected path (422), not a successful manual save.
- The template change was committed under step 2 (the brief lists it in §3 with no step of its own).

## Left undone
- Run the DB tests with `UBYHOST_TEST_DATABASE_URL` set, and confirm 0 skipped for the cleaning package.
- The browser layout lint and the three screenshots (rules 7 and 10).
- Full review of the diff before the PR (Tier B). No PR was opened, as the brief for this run said.

## Owner steps
- Set `UBYHOST_TEST_DATABASE_URL` to a test Postgres and rerun: `cd go && go test ./internal/web/cleaning/... ./cmd/ubyhost-web/... -count=1 -v | grep -- '--- SKIP' | tail -30`

## Orchestrator review (2026-11-16)

- Database tests run against a local Postgres 16: `go test ./internal/web/cleaning/... ./cmd/ubyhost-web/...` passes. The only skips are 3 old probe tests in `cmd/ubyhost-web`. The executor's first `TestHostQueueKick` used a property without a listed lock; fixed (locks_json set, pending code cleared).
- Page checked on the Go-rendered `/cleaning/properties/12` (property with a saved code), served with the repo's CSS, no JavaScript. One screenshot each at 390, 768 and 1280 px in the project folder `ux-shots/cleaning-code/`. At all three widths the panel shows the PIN, the pending notice, the **Remove saved code** button (outlined, danger) on its own row above **Create permanent TTLock code**, then the lock link. No overflow, no wrapped or squeezed labels. The `?` help icons look odd only because JavaScript was off in the screenshots; they are unchanged by this PR.
- `App/tests/layout_lint.js` (the lint behind `test_layout_lint_browser.py`) run on that page at 320, 360, 390, 768, 1024, 1280 and 1440 px: no findings. `test_layout_lint_browser.py` itself needs the Python app and does not cover the Go cleaning page, so it was not run.
- Design-system checklist: the button reuses `ui-btn ui-btn-danger`; no new copy, no new colour.
- Known limit: a kick that arrives while another pass is running is dropped; the 5-minute job picks that row up.
