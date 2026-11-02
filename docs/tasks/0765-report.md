# 0765 report (executor, Haiku 5.5)

Status: blocked. Route, template and i18n are edited, but 0729 phone geometry fails. Not committed, not pushed (per the owner's instruction).

## Files changed (this executor only)
- App/app/routes/admin.py: new `_key_rows(rows, today)` helper; context `key_rows`; `next_arrival` is now a row, first stay after tomorrow. `today_rows` kept for the desktop table.
- App/app/templates/dashboard.html: `nav` set from `cal_view`; phone-only cal_view hiding (ph-top, needs-action, 14-day grid, full-calendar link, add button); phone Today loop over `key_rows` with kind labels and `stay_range`/`pass_date` globals; next-stay card when the window is empty.
- App/app/host_i18n.py, App/app/host_vi_i18n.py: added dashboard.ph.window, .kind.tomorrow, .kind.arrived, .kind.next (en, cs, vi); removed dashboard.ph.next (no other users).
- Not created: App/tests/test_0765_phone_today_window_browser.py (not written, step 4).

## Tests
- 0729 + test_dashboard_phone (after): `4 failed, 2 passed in 15.35s`. Failures: "stay card 0/1 off centre", "stay card 1 overflows the viewport" at 360, 390, 768.
- Same tests on HEAD copy (baseline): `6 passed in 12.96s`. So the phone failures are caused by this change.
- 0710 subset -k "dashboard or overview or today" (after): `2 failed, 10 passed`. HEAD copy: `6 failed, 6 passed`, so the baseline looks unstable; not resolved.

## Screenshots (390 px)
- docs/tasks/screenshots-0765/before-today-390.png, before-calendar-390.png (HEAD)
- docs/tasks/screenshots-0765/after-today-390.png, after-calendar-390.png, after-today-nothing-in-window-390.png (not yet visually reviewed)

## Deviations
- App/.venv lacked fastapi, requests and playwright. Ran `pip install -r requirements.txt -r requirements-dev.txt` in App/.venv. Playwright 1.64.1 wanted chromium 1248, which is absent. Used `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`.
- `stay_range` and `pass_date` are Jinja globals, called as functions, per the coordinator.
- `nav` set in the template, not the context.
- Throwaway screenshot script removed from App/tests.

## Open for the owner or next executor
- Diagnose the phone stay-card geometry failure (off-centre/overflow). Likely the longer `.meta` date prefix or the card markup; brief 0766 touches the same cards, so coordinate.
- Then write the 0765 test file, rerun the 0729 and dashboard phone tests, and review the after screenshots.
- The 0710 overview style failures need a clean baseline before anyone changes them.

## Follow-up run (section 7 plus the coordinator's A and B)

- Section 7.1: `test_today_phone_geometry` now checks the stay row when there are several stays (first card left = h2.sec left, equal tops, row scrolls only when the cards overflow 272 px cards + 12 px gap). Single stay keeps the centre checks.
- A (calendar at 390): cause was `{{ ' class="ph-hide" ' if cal_view }}` on #needs-action. Autoescape turned the quotes into `&quot;`, so the class was `"ph-hide"` and the section stayed visible. Now `{% if cal_view %} class="ph-hide"{% endif %}`.
- B (next stay): the next-stay card moved from .ov-head into the `.hs.ph-only` block (`{% else %}` of the key_rows loop), shown whenever key_rows is empty and not cal_view, with no need-card condition. The `.hs` shows when key_rows or next_arrival; the h2 is hidden when key_rows is empty.
- New test file App/tests/test_0765_phone_today_window_browser.py: 4 tests (window stays 2 days ago and tomorrow; far stay gives one card and a need card; calendar hides Today at 390; desktop calendar keeps #needs-action). All 4 pass.
- Screenshots retaken (390 px, full page): docs/tasks/screenshots-0765/after-today-390.png, after-calendar-390.png, after-today-nothing-in-window-390.png. The capture script ran from App/tests once and was deleted; it is not committed.

Test runs:
- 0729 + test_dashboard_phone + 0765: FAILED tests/test_0729_phone_today_geometry_browser.py::test_today_phone_geometry[today-320]
FAILED tests/test_0729_phone_today_geometry_browser.py::test_today_phone_geometry[today-360]
FAILED tests/test_0729_phone_today_geometry_browser.py::test_today_phone_geometry[today-390]
FAILED tests/test_dashboard_phone_browser.py::test_phone_dashboard_compact
4 failed, 6 passed in 49.12s
- test_static_versions.py: 2 failed, 1 passed in 0.17s
- scripts/context_lint.py: context lint: FAIL

Still failing (not fixed, status blocked):
- 0729 first stay card at 320, 360 and 390 px: card left 0.0, h2.sec left 20.0 (`.hs` padding 20px, margin -20px). Section 7 expects them equal. CSS is not to be changed, so either the row is meant to bleed to the edge (then the brief's check is wrong) or the CSS needs a fix. Owner or orchestrator to decide.
- test_dashboard_phone_browser::test_phone_dashboard_compact: `.needs-you-more > summary` is not visible at 390 px. It passed in the first run of this follow-up and failed after the #needs-action class fix. Cause not confirmed; the rendered markup for non-calendar views should be unchanged. Needs a look.
- The 0765 tests at 1280 and the 0765 calendar test pass.
- The 0710 subset and the non-browser dashboard tests were not run (budget).

## Follow-up 2 (section 8)

Files changed: `App/app/static/app2.css` (line 264: `scroll-padding-inline:20px` on `body.v2 .hs`), `App/app/templates/base.html` (app2.css `?v=` key 20261102-0732i to 20261102-0905a), `App/tests/static_versions.json` (rewritten by `test_static_versions.py --write`).

1. 0729 first card left 0 vs h2 left 20: fixed by the scroll-padding line. 0729 now passes (the three `test_today_phone_geometry` cases are not in the failure list).
2. `test_phone_dashboard_compact`: NOT fixed. Root cause: the test opens the calendar fixture URL (`cal_view`) at 390 px, and on that view section 88 `#needs-action` and its `.needs-you-more` are `ph-hide` by design (brief 0765 §4, line 34). The `<details>` computes to `display:block` inside `section.ph-hide` (`display:none`), so the summary has 0x0 size. Main's template showed the list here only because of the quote-escaping bug fixed in follow-up A. The template is not at fault. The test assumption (PIN alert reachable on the phone calendar view) is outdated. Open question for the owner or orchestrator: change the test to check the PIN line on `/` (the Today view) at 390, or keep the list on the phone calendar. I did not change the test.
3. Static version test (2 failed before this step too, since app2.css changed without a key bump): bumped the key and rewrote the manifest. Now 3 passed.

Test runs (from App/, browser env per brief):
- test_0729_phone_today_geometry_browser.py + test_dashboard_phone_browser.py: `1 failed, 5 passed in 42.41s` (the failure is test_phone_dashboard_compact, see 2)
- test_0765_phone_today_window_browser.py: `4 passed in 8.85s`
- test_static_versions.py: `3 passed in 0.18s` (after the bump)
- non-browser dashboard tests (test_dashboard_*.py without browser, test_design_dashboard, test_host_quiet_dashboard, test_needs_you_dashboard_0241, test_payments_dashboard): `94 passed in 5.19s`
- test_0710_v2_mockup_match_browser.py -k "dashboard or overview or today": `2 failed, 10 passed in 24.15s`. Failures are test_v2_page_matches_mockup_styles[overview-320] and [overview-390]: 5 style differences, mainly `.hs .card` 272 px wide vs mockup 350 px and `.meta` size. These come from the 272 px card row (#681), not from this step. Not fixed; needs a clean baseline (as the earlier note says).
- scripts/context_lint.py: `context lint: FAIL`, `ERROR docs/tasks/0766-phone-stay-cards-dates-and-empty-bar.md: missing section '## 9. Report'`. Not from this step; 0766's brief.

Screenshots: not retaken. The scroll-padding only changes where a scrolled row snaps, so the page at rest should look the same. Not checked visually.

Status: blocked (item 2 needs an owner decision; the 0710 overview failures and the lint error are pre-existing). Nothing committed.
