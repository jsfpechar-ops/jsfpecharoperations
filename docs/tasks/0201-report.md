# 0201 report

Status: blocked

## Files changed
- App/app/templates/base.html: viewport meta now `width=device-width, initial-scale=1, viewport-fit=cover`; host2.css key `?v=20261021-0201`.
- App/app/static/host2.css: appended the `/* 0201 */` block (brief step 2). The `.ui-topbar` has no sticky or fixed position, so the optional top-inset padding was not added.
- App/tests/static_versions.json: regenerated (2 lines changed).
- App/tests/test_0201_tabbar_safe_area_browser.py: new (brief step 4).

Not committed, per the owner's instruction (no commit, stash, checkout, reset or clean). No PR opened.

## Commands
Brief §6 set (browser required): `27 passed, 5 failed, 1 warning in 103.59s`
- All 5 failures are in the new test file: 4 x `/dashboard` (viewport meta check) and 1 x `test_phone_tab_bar_is_hidden_at_1280` (no `.ui-tabbar` on the page).
- test_static_versions, test_design_shell_browser, test_shell_lane_browser and test_design_guardrails_browser all pass.

Measured, `/stay-fees` (4 passed, en and cs at 360 and 390):
- 390 en: inner_h 844, bar_top 780, bar_bottom 844, bar_h 64, max_link_bottom 836, scrollWidth 390
- 390 cs: same bar values, content_bottom 256.6
- 360 en: inner_h 780, bar_top 716, bar_bottom 780, bar_h 64, max_link_bottom 772, scrollWidth 360
- 360 cs: same bar values, content_bottom 173.1

## Deviations
- Brief §4 names `/dashboard`, but there is no `/dashboard` route in App/app/routes (only `/dashboard/calendar`). The page at `/dashboard` does not carry the base.html meta, so the test fails. The home route is probably `/` in App/app/routes/admin.py:398, but that is a guess and that file is not named in the brief.
- The 390 screenshots of `/dashboard` were not taken because the page does not exist. Nothing was written to /mnt/project-files.
- Done: steps 1 to 3 and the test file (step 4). Left: the `/dashboard` URL choice and the 1280 check, which depend on it, and the screenshots.

## Questions
1. Which route is the host dashboard: `/`, or another URL? Once confirmed, I will change the test's path and rerun.
2. The executor doc says to commit each step, but the brief §5 and the owner's instruction say no commit. I followed the owner.

## Owner steps left
- Answer question 1, then the executor (or owner) can finish the test and take the 390 screenshots.
- Review the uncommitted changes listed above, then commit and open a PR when ready.

## Orchestrator follow-up

The host dashboard is `/`, not `/dashboard`. Test paths changed to `/`; the brief set now passes: 32 passed, 0 skipped. Screenshots saved.
