# 0729 report: phone v2 Today (Airbnb style)

Status: review (committed on phone-v2, not pushed, no PR)

Done: steps 1 to 11 and brief section 10 items 1 to 3. Step 12 done as a new commit (owner asked for no amend), message "0729: phone v2 Today, test updates, screenshots".

## Files changed
App/app/routes/admin.py, App/app/host_i18n.py, App/app/host_vi_i18n.py, App/app/templates/dashboard.html, App/app/static/app2.css, App/app/templates/base.html, App/tests/static_versions.json, docs/design/catalog.json, App/tests/v2_mockup.py, App/tests/test_0710_v2_mockup_match_browser.py, App/tests/test_0729_phone_today_geometry_browser.py (new), App/tests/test_host_quiet_dashboard_browser.py, App/tests/test_host_wide_geometry_browser.py, docs/tasks/0729-phone-v2-today-report.md, docs/tasks/screenshots-0729/overview-390.png, docs/tasks/screenshots-0729/overview-320.png (new).

## Test runs (section 6 set, from App/)
- Final: `3 failed, 47 passed in 269.37s (0:04:29)`. Failures: test_0710 `test_v2_page_matches_mockup_styles[menu-320]`, `[menu-390]`, `[menu-768]` only (brief 0735). 0 skipped.
- test_0729_phone_today_geometry_browser.py: `5 passed` (inside the full run).
- ruff E9,F63,F7,F82,F401,F841: `All checks passed!`
- design_lint: `design lint: OK`
- context_lint: `context lint: OK`

## Overrides (section 10 items 2 and 3, phone only, below 1024 px)
- test_host_quiet_dashboard_browser: the phone "+" header link check, `.ph-top .seg a` checks, and the needs-you card checks are on the new markup.
- test_host_wide_geometry_browser: below 1024 on `/`, the lane is measured on `.ph-top`, not `.head`.
- Added in this run (not in brief text, same rule): the needs-you `border` check runs only at width >= 768. Below 768 the card has `border:0` (brief 4b), and the shadow check already covers the frame.
- Added in this run: the 40 to 52 px `.need .ic` tile check runs only at width >= 1024. Below 1024 the test asserts the icon is not rendered (brief 4 / step 10: `.need .ic` not visible).

## Screenshots
- Taken with UBYHOST_SHOTS_V2=1 (step 11). Copied from docs/tasks/screenshots-0710/: docs/tasks/screenshots-0729/overview-390.png and docs/tasks/screenshots-0729/overview-320.png. Viewed overview-390 once: the phone Today page renders as designed.
- The run rewrote tracked PNGs in docs/tasks/screenshots-0710/ and created untracked menu-* and mockup-None-* files. Restored and removed, so they are not in the commit.

## Deviations
- Step 12 was a new commit, not `git commit --amend` as section 10 item 3 says. The owner's instruction for this run was a new commit. The earlier WIP commit 361ee4a stays in history.
- Two extra test guards (border at >= 768, icon size at >= 1024) beyond the brief's text. Both come from brief 4b and step 10 (`.need .ic` not visible on phone).
- Earlier deviations still apply: branch is phone-v2 (brief header named a different branch); extra width overrides for `.need .t` and `.need small`; empty-state geometry test not added.

## Questions
- None open. The 3 menu-* failures stay until brief 0735.

## Owner steps left
- Review, then merge with `scripts/merge-pr-on-green.sh` once a PR exists (none opened by the executor).
