# 0547: Cleaning phone layout, close the remaining 390 px differences
Status: todo
Depends on: 0546 (same branch, pushed at d0a95bf) | Branch: claude/project-thread-c1h7ok
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
The `cleaning-390` and `cleaning-320` style cases of `App/tests/test_0710_v2_mockup_match_browser.py` have no differences left that come from cleaning files, and the step 5 regression set of 0546 passes or lists only non-cleaning failures by name.

## 2. Context
- Read `docs/tasks/0546-report.md` first (the 13 differences at 390 px).
- Phone mockup Úklid screen: `docs/design/mockup/ubyhost-phone-v1.html`, `grep -n 'data-s="uklid"'` (about 18 lines). Its subtitle is "Vzniká sám z odjezdů."; its today card has inline `margin-top:8px`; its first row pill is `p-ok`.
- NOT yours (the Overview thread fixes them in shared files in brief 0719, including comparing 768 px against the phone mockup): `.tab.on` missing, `.actbar` padding-bottom 12 vs 30 and height, `.actbar .btn` "missing in mockup", and every 768 px difference. Leave those failing and list them.
- Test data: `dashboard_rich_host` in `App/tests/test_host_quiet_dashboard_browser.py` (stays via `stay(label, arrival, departure)`, `today = claim.prague_today()`). Cleanings come from departures (`App/app/cleaning.py`, `grep -n '^def '`).

## 3. Files
`App/app/templates/cleaning.html`, `App/app/templates/_cleaning_table.html`, the `/* cleaning (0542) */` block at the end of `App/app/static/app2.css` (+ `?v=` key in `base.html`, `tests/static_versions.json` via `--write`), `App/app/cleaning_i18n.py` + `App/app/host_vi_i18n.py` (one key), `App/tests/v2_mockup.py` (cleaning entry only), `App/tests/test_host_quiet_dashboard_browser.py` (one stay, step 3 only), the failing cleaning tests from step 5. Report `docs/tasks/0547-report.md`.

## 4. Steps
1. **Subtitle.** New key `subtitle_short` at the END of `CLEANING_WORDS` / `WORDS`: cs "Vzniká sám z odjezdů.", en "Created from departures.", vi "Tự tạo từ lượt trả phòng.". In `cleaning.html` add `<p class="sub cleaning-phone">{{ ct('subtitle_short') }}</p>` right after the h1, and give the existing `.sub` the class `cleaning-desk-only`; in the cleaning block below 1024 px hide `.cleaning-desk-only`. Commit `0547 step 1`.
2. **Title height.** At 390 px the h1 `.big` is 47.8 px tall, the mockup's 36.8 px. Find the cause with a throwaway Playwright script in `/tmp` (print computed `padding`, `border`, `margin`, `line-height`, and `::after` `display/height` of `.cleaning-head h1` at 390). If it comes from the desktop `.head h1` rule (coral underline or padding), neutralise it in the cleaning block below 1024 px (`body.v2 .cleaning-head h1{...}` and `body.v2 .cleaning-head h1:after{display:none}`). If only a shared phone rule can fix it, stop and report. Commit `0547 step 2`.
3. **Today card.** Add `margin-top:8px` to `body.v2 .cleaning-today` below 1024 px. Then make the fixture show one cleaning today: find why `/cleaning` has no today item (print `_sections(...)` keys or look at the stays in the fixture). If no stay departs today, add one `stay("cleaning-today", today - timedelta(days=2), today)` (check the helper's real signature). Run `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k overview -q --tb=line 2>&1 | tail -15` before and after: if overview results change, revert the fixture line and report it (no test exemption for the today card). Commit `0547 step 3`.
4. **Data-independent row selectors.** In the cleaning entry of `v2_mockup.py` replace `".list .row"` with `".list .row:has(.p-ok)"` and `".row .t .pill"` with `".row .t .pill.p-ok"`, so the row compared has the same tone as the mockup's first row. Run `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k cleaning -q --tb=short 2>&1 | tail -60` and fix remaining cleaning differences in the cleaning files only. Commit `0547 step 4`.
5. **Regression with names.** `.venv/bin/python -m pytest tests/test_cleaning_browser.py tests/test_0252_touch_sweep_browser.py tests/test_0540_cleaning_tables.py tests/test_0541_cleaning_header.py tests/test_design_cleaning.py tests/test_cleaning.py tests/test_static_versions.py tests/test_host_language.py -q --tb=line -rf 2>&1 | tail -40`. For cleaning failures: tests that click host rows or the header button at widths below 1024 should use the phone markup (`.cleaning-phone .row`, `.actbar .btn`); "element intercepts pointer events" from the fixed `.actbar` or tab bar means the click target is under the bar: scroll it to the middle first (`locator.evaluate("e => e.scrollIntoView({block:'center'})")`) or click at 1280 if the test is about desktop behaviour. List every change. Commit `0547 step 5`.
6. **Screenshots.** Throwaway script in `/tmp` (copy `test_v2_screenshots` from test_0710): `/cleaning?lang=cs` at 390 as `docs/tasks/screenshots-0547/cleaning-390.png`, and the phone mockup Úklid screen at 390 as `mockup-uklid-390.png` (use `show_phone_screen(page, "uklid")` from `v2_mockup.py`). Commit `0547 step 6`.

## 5. Do not touch
Shared `app2.css` rules above the cleaning block, `_shell_v2.html`, `SELECTOR_ALIASES` and helpers in `v2_mockup.py`, other PAGES entries, the mockups, the cleaner's shared view (`cleaning_shared.html`, `_cleaning_list.html`), JS, routes. No new dependency, no migration. Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (no other model name). Do not push.

## 6. Commands
In the steps (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`), then from the repo root `python3 scripts/design_lint.py 2>&1 | tail -3`.

## 7. Acceptance
At 320 and 390 the only cleaning differences left are the four shared ones in section 2; 1024-1440 still pass; step 5 lists failures by name with their cause; lint OK; two screenshots.

## 8. Stop and ask
Stop if a fix needs a shared rule or a file outside section 3.

## 9. Report
`docs/tasks/0547-report.md` (required): Status, test tails, each difference fixed, each left with its owner, regression failures by name, screenshot paths.
