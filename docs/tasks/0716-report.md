# 0716 report: v2 shell feature parity

Status: blocked (3 of 9 listed files still fail; two need an owner decision)

## Files changed
- App/app/templates/_shell_v2.html: logo wrapped in `div.ui-brand`, env badge under it (same classes as old sidebar), quiet support link (`mailto:`) above the account block, copied from `_shell_sidebar.html`.
- App/app/static/app2.css: env badge and support link styles; `.card > table` phone rule scoped to `.card[data-dashboard-refresh="work"]` (Overview Dnes card; dashboard.html untouched).
- App/app/templates/base.html: app2.css key `20261101-0716b`; the `/admin/*` speculation exclusion rendered only for admins.
- App/tests/test_design_shell.py: both tests point at `/reservations` (old shell); `/` gets one assertion for every destination href in `#app-sidebar`.
- App/tests/static_versions.json: regenerated.

## Section 6 run (last)
`9`-file command: 104 passed, 3 failed, 0 skipped.
- test_havel_palette::test_no_match_opens_havel_with_the_query: Timeout 30000ms, `waiting for locator("[data-command-open]:visible").first` (at 390 px on /guide).
- test_host_redesign::test_all_host_destinations_render_with_valid_structure[en] and [cs]: AssertionError: `/static/host.css` not in response for `/`.
- design_lint: OK. context_lint: OK.

## Fixed
- test_environment_banner, test_security (mock badge): pass.
- test_host_account_navigation::test_ordinary_user_sees_no_admin_controls: pass. The `/admin/` string was the speculation rule in base.html, not the sidebar.
- test_accounts::test_host_admin_portal_shows_ubyhost_support_email: pass.
- test_design_shell (both): pass after retarget.
- test_0710 (all geometry and style cases): pass.

## Deviations
- Key is `20261101-0716b`, not `20261101-0716`: test_static_versions refuses a changed app2.css under an unchanged key.
- Added `div.ui-brand` wrapper (required by test_environment_banner, which looks for `class="ui-brand"` in the sidebar).
- Support link and badge font raised to 12 px (0710 geometry minimum); badge margins reduced so the phone sidebar stays under 72 px.
- The brief's analysis of test_havel_palette was wrong: the test runs on /guide (old shell), not v2. The v2 `.search` already has `data-command-open`.

## Questions for owner
1. test_havel_palette: at 390 px the old shell has no visible `[data-command-open]` (the only one is in the closed More sheet). The fix is a phone-visible search trigger in the old top bar or tab bar (outside this brief). Approve?
2. test_host_redesign: the test requires `/static/host.css` on `/`. The v2 branch of base.html loads only tokens.css and app2.css by design; adding host.css brings old styles back. Approve adding it to v2 pages, or should the test be changed?

## Owner steps left
None until the two questions are answered.

## Not done
- The AGENTS rule 7 390 px screenshot of `/` is not in this report (not taken).
