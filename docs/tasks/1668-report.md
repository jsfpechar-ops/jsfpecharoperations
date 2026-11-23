# 1668 report

Status: review

## Files
- `App/tests/go_web_harness.py`, `App/tests/test_go_pages_layout_lint_browser.py`
- `docs/context/test-map.md`, `docs/context/workflow.md`

## Commands (last 5 lines)
**pytest:** `1 failed, 2 passed, 1 warning in 16.93s`
**shots:** 15 PNGs in `/tmp/shots/layout-lint/`
**context_lint:** `context lint: FAIL` (test-map token cap)
**pgolint DBs:** none after drop
**pgrep ubyhost-web:** empty

## §7
- [x] Harness, 0 skipped, all route screenshots
- [x] guide-390: v2 shell, sidebar, Guest guide, CSS
- [ ] 6 lint findings (below)
- [x] Teardown on clean exit
- [ ] context lint (pre-existing)

## Findings
- help-stranded / guide / 390,768,1280
- multiple-save-in-form / guide-card-wifi Save / 390,768,1280

## Deviations
- Branch `cursor/1668-go-layout-harness-992e`; no push/PR.
- Static from `App/app/static`.
- `UBYHOST_AI_FEATURES=leon` in harness.
- Local `codefilter.go` edit to unblock go build (uncommitted).

## Owner steps
- Optional CI for `test_go_pages_layout_lint_browser.py`.
