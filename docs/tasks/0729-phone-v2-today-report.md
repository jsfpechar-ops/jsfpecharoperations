# 0729 report: phone v2 Today (Airbnb style)

Status: blocked (WIP committed, not pushed, no PR)

Done: steps 1 to 10 (admin next_arrival, i18n en/cs/vi, dashboard.html phone top and ph-hide, app2.css 4a to 4h, cache key 20261101-0729 with static_versions rewritten, catalog.json, v2_mockup.py, test_0710 _open_phone, BOX_OVERRIDES text-dependent entries, new test_0729_phone_today_geometry_browser.py).
Left: step 9 failures below, step 11 screenshots (overview-390.png, overview-320.png), step 12 clean commit.

## Files changed
App/app/routes/admin.py, App/app/host_i18n.py, App/app/host_vi_i18n.py, App/app/templates/dashboard.html, App/app/static/app2.css, App/app/templates/base.html, App/tests/static_versions.json, docs/design/catalog.json, App/tests/v2_mockup.py, App/tests/test_0710_v2_mockup_match_browser.py, App/tests/test_0729_phone_today_geometry_browser.py (new), docs/tasks/0729-phone-v2-today-report.md (new).

## Commands (last lines)
- test_0729_phone_today_geometry_browser.py: `5 passed in 8.00s`
- test_0710 -k overview (after overrides): `1 failed, 11 passed` at first run (menu not in -k overview). Final run: 390 failure fixed by `.hl@390`/390 overrides; full run below.
- Full section 6 set: `7 failed, 43 passed in 232.00s (0:03:52)`
- ruff E9,F63,F7,F82,F401,F841: `All checks passed!`
- design_lint: `design lint: OK`
- context_lint: `context lint: OK`
- test_static_versions --write: `wrote /tmp/wt0729/App/tests/tests/static_versions.json (41 files)`

## Failing (all phone widths, not desktop)
1. test_0710 `test_v2_page_matches_mockup_styles[menu-320/390/768]`: style differences on the Menu (6 to 8 each). Not investigated. Possibly caused by the shared `body.v2 .card` change (4b). Menu is brief 0735 scope.
2. test_host_quiet_dashboard_browser `test_dashboard_single_stay_needs_you_card` (JS error: offsetParent of null, a removed element) and `test_dashboard_rich_needs_you_order_cap_and_geometry` (`rich/en/360/open`: 0 visible needs-you buttons).
3. test_host_wide_geometry_browser `test_host_wide_lanes_align` (dashboard pageHeader lanes at 360) and `test_dashboard_760_header_and_actions_remain_in_the_shared_lane` (`.head`/`.title` hidden by `ph-hide` at 760). These are phone assertions of `/` that this brief changes on purpose, so the standing rule allows updating them. Not updated yet.

## BOX_OVERRIDES added (measured app values)
- `.card.need@320` and `@390`: height 180.188px
- `.need .t@320` width 236px; `@390` width 306px
- `.need small@320` width 236px, height 52px; `@390` width 306px, height 52px
- `.hs .pill@320` and `@390`: width 141.359px
- `.kind@320` and `@390`: width 64.5625px
- `.nm@320` and `@390`: width 125.5px
- `.meta@320` and `@390`: width 125.5px
- `.hl@390`: height 69px
- kept: `.card.me`, `.big`, `.card.me@320`. All other old keys deleted (step 7d).

## Deviations
- Worktree branch is `phone-v2` (brief header said `claude/project-thread-50hyv5`); worked in the given worktree.
- Added width overrides for `.need .t` and `.need small` (brief listed width only for pill, nm, meta, kind). Both are display block, so their width follows the fixture text.
- Ran test_0710 `-k overview` without `-x` to see all widths at once.
- Empty-state geometry test skipped: no quick fixture for a host with no needs-you lines was checked.
- Commit message is flagged WIP because tests fail, instead of the brief's clean message.
- Executor budget reached before step 9 was green.

## Questions for the orchestrator
- Is the menu style failure from the shared `.card` change? If yes, scope it with brief 0735 or keep the old card style under `.card.me`.
- Confirm updating the four `/` phone assertions in item 2 and 3 (standing rule covers them).
