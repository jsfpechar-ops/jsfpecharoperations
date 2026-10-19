# 0139-fix-1 report

Status: review

## Files changed
- App/app/templates/guest_form_admin.html (action block split into two rows; Cancel quiet beside Save; four guest-data actions compact in row two; Save remains first submit button)
- App/tests/test_design_guest_admin.py (assertion updated to new markup, plus Save-button check)

## Commands
- `python3 scripts/design_lint.py 2>&1 | tail -2`: `design lint: OK`
- `cd App && .venv/bin/python -m pytest tests/test_design_guest_admin.py tests/test_host_guest_form.py -q 2>&1 | tail -3`: `22 passed, 1 warning in 1.80s`
- `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_host_geometry.py tests/test_shell_lane_browser.py -q -rs 2>&1 | tail -3`: `6 passed, 1 warning in 12.60s`, no skips

## Acceptance (§7)
- [x] Two action rows; Save first submit button; tests pass, 0 skipped.

## Deviations
- No 390 px screenshot taken. The brief has no screenshot step, but hard rule 7 requires one per changed page. Owner or orchestrator to capture `/guests/1` at 390 px.
- No push and no PR (run instruction: do not push).
- Temporary edit scripts were kept outside the repo and not committed.

## Questions
- None.

## Owner steps left
1. Push `claude/project-thread-5hw8cf` and open the PR.
2. Merge with `scripts/merge-pr-on-green.sh` once CI is green.
3. Capture the 390 px screenshot of `/guests/1` for the report.
