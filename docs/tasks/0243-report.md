# 0243 report: "What needs you" lands on a visible link, geometry tests

Status: review

## Files changed
- `App/app/needs_you.py` (step 1: `#stay-link` to `#now`)
- `App/tests/test_needs_you_0240.py` (step 1)
- `App/tests/test_signed_in_chrome.py` (step 1)
- `App/tests/test_host_quiet_dashboard_browser.py` (step 2: old tests replaced by card geometry tests)
- `App/tests/test_design_dashboard.py` (step 3: unused `import re` removed)
- `docs/tasks/0243-report.md`

## Commits
- `36b1172` 0243 step 1
- `bf744f1` 0243 step 2
- `9bf2e33` 0243 step 3
- plus this report commit

## Commands (last lines)
- Step 1: `tests/test_alert_stack.py tests/test_needs_you_0240.py tests/test_signed_in_chrome.py`: `35 passed, 1 warning in 2.81s`
- Step 2 ruff: `All checks passed!`
- §6 cmd 1 (`test_alert_stack` + `test_host_quiet_dashboard_browser`, `-rs`): `15 passed, 1 warning in 39.78s`, no skips
- §6 cmd 2 (with `UBYHOST_SHOTS_DIR=/mnt/project-files/foolproof-round2/dashboard`): `15 passed, 1 warning in 48.56s`; `ls ... | wc -l` = 36
- Step 3 ruff on `tests`: `All checks passed!`
- §6 cmd 3 (`test_alert_stack` + `test_host_list_layouts_browser`, `-rs`): `15 passed, 1 warning in 18.08s`, no skips

## Acceptance (§7)
- [x] Step 1 tests pass
- [x] §6 cmd 1 and 3 pass with 0 skipped; cmd 2 wrote 36 screenshots

## Screenshots (390 px, one per changed page)
- `/mnt/project-files/foolproof-round2/dashboard/dashboard-single-en-390.png`
- `/mnt/project-files/foolproof-round2/dashboard/dashboard-en-390-open.png`
- `/mnt/project-files/foolproof-round2/dashboard/dashboard-en-390-collapsed.png` is not produced (collapsed runs only at 1280+); the open one is the 390 px rich-state shot.

## Deviations
- None in the steps. The untracked `docs/tasks/0102-evidence/*` files were already in the working tree before this run; they were not added.

## Questions
- None.

## Owner steps left
- None for this brief. Push and PR are left to the owner's flow (not done here).
