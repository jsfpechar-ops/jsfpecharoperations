# 0548: Cleaning phone layout, test data and tests that predate it
Status: todo
Depends on: 0547 (same branch, pushed) | Branch: claude/project-thread-c1h7ok
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
The 12 regression failures named in `docs/tasks/0547-report.md` pass, and the cleaning phone compare has a today card and a green row to check against the mockup.

## 2. Context
- Read `docs/tasks/0547-report.md` first.
- Orchestrator decisions (2026-11-01): the phone mockup has no calendar, so calendar checks in `test_cleaning_browser.py` run at 768 px and up (keep the test, change its phone viewports to 768 wide, same height); the page has one share button per layout (desktop head button from 1024 px, phone `.actbar` button below), so share-link counts assert one in `.cleaning-head` plus one in `.actbar.cleaning-phone`, and at a given width exactly one is visible.
- Shared, NOT yours (Overview thread, brief 0719): `.tab.on`, `.actbar` padding and the `.actbar .btn` alias, 768 px compare, and the security prompt hidden under the `.actbar` at 320 px (cleaning-320 `_open_app` timeout).
- Fixture: `dashboard_rich_host` in `App/tests/test_host_quiet_dashboard_browser.py`. Adding a departure-today stay changed the Overview baseline (0547). Use a cleaning event instead: `cleaning.save_event(apartment_id, values)` in `App/app/cleaning.py` (read it, lines 122-158, for the keys).

## 3. Files
`App/tests/test_host_quiet_dashboard_browser.py` (fixture, cleaning events only), `App/tests/test_cleaning_browser.py`, `App/tests/test_0541_cleaning_header.py`, `App/tests/test_design_cleaning.py`, `App/tests/v2_mockup.py` (cleaning entry only, only if step 1 changes a selector). Screenshots `docs/tasks/screenshots-0548/`. Report `docs/tasks/0548-report.md`.

## 4. Steps
1. **Fixture.** In `dashboard_rich_host`, after the apartments exist, add two manual cleaning events on the "Review Flat" apartment with `cleaning.save_event`: one today 11:00-14:00, one in 2 days 11:00-14:00, both without a conflict (check `/cleaning?lang=cs` shows the today card and a `p-ok` row: a throwaway script in `/tmp` that prints the `.cleaning-phone` HTML is enough). Run `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k overview -q --tb=line 2>&1 | tail -15` before and after: the result must not change (baseline: 1 failed at 768, 11 passed). If it changes, revert and report. Then `-k cleaning`: only the shared items in section 2 may remain. Commit `0548 step 1`.
2. **Calendar tests.** In `test_cleaning_browser.py`, the 10 tests named in the 0547 report that wait for the calendar at 360/390 px: change those viewports to 768 px wide. `cleaning_form_pages_fit[390]` and `add_stay_and_cleaning_dialogs[390-844]`: if they open the add dialog from the calendar, run them at 768; if they test a form page, find what they wait for and fix the wait, not the page. Commit `0548 step 2`.
3. **Share-link counts.** Update `test_0541_cleaning_header::test_header_has_one_primary_share_button_in_czech` and `test_design_cleaning::test_cleaning_pages_have_the_v2_shell_and_one_stylesheet` per section 2. Commit `0548 step 3`.
4. **Check.** `.venv/bin/python -m pytest tests/test_cleaning_browser.py tests/test_0540_cleaning_tables.py tests/test_0541_cleaning_header.py tests/test_design_cleaning.py tests/test_cleaning.py tests/test_static_versions.py tests/test_host_language.py -q --tb=line -rf 2>&1 | tail -30`. Fix test causes only. Commit if anything changed.
5. **Screenshots.** Throwaway script in `/tmp` (copy `test_v2_screenshots` from test_0710; dismiss the security prompt with `page.evaluate` removing `#security-prompt` if the click is blocked): `/cleaning?lang=cs` at 390 as `cleaning-390.png` and 1280 as `cleaning-1280.png`, and the phone mockup Úklid screen at 390 as `mockup-uklid-390.png` (`show_phone_screen(page, "uklid")` from `v2_mockup.py`). Commit `0548 step 5`.

## 5. Do not touch
App code, templates, CSS, `_open_app` and helpers in test_0710 / `v2_mockup.py`, other PAGES entries, the mockups. No new dependency, no migration. Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (no other model name). Do not push.

## 6. Commands
In the steps (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`), then from the repo root `python3 scripts/design_lint.py 2>&1 | tail -3`.

## 7. Acceptance
Step 4 passes (list anything left by name and cause); Overview results unchanged; cleaning compare differences only the shared ones; three screenshots.

## 8. Stop and ask
Stop if a fix needs app code, a template, CSS, or a shared test helper.

## 9. Report
`docs/tasks/0548-report.md` (required): Status, tails, each test changed and why, what is left with its owner, screenshot paths.
