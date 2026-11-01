# 0549: Cleaning phone layout, today card box, missing time, last three tests
Status: todo
Depends on: 0548 (same branch, pushed) | Branch: claude/project-thread-c1h7ok
Executor: Haiku 5.5 | Fits one session: 20 tool calls, 40k tokens

## 1. Objective
In `docs/tasks/screenshots-0548/cleaning-390.png` the today card is broken (its text sits on the left edge with white fragments around it) and rows read "next check-in 3 Nov Time not set". Fix both, make the last three cleaning browser tests pass, and take the phone screenshots for the owner.

## 2. Context
- The today card is `<a class="card cleaning-today">` in the `.cleaning-phone` block of `App/app/templates/_cleaning_table.html`. An `<a>` is inline, so the shared `.card` box breaks into line fragments. It needs `display:block` (cleaning block of `app2.css`, below 1024 px), plus `color:inherit;text-decoration:none` if the link colour shows.
- Missing check-in time: in the phone markup (today card meta line and the `.row small` line) `{{ item.checkinTime or ct('time_missing') }}` prints "Time not set" after the date. Print the time only when it exists: `{% if item.checkinTime %} {{ item.checkinTime }}{% endif %}`. Leave the desktop table cells and the first part of the meta line (cleaning window) as they are.
- 0548 report: `test_fractional_checkout_and_same_day_cleaning_geometry[1024-en/cs]` and `test_missing_property_hours_keep_full_day_cleaning_marker_without_saved_defaults` in `App/tests/test_cleaning_browser.py` fail at 1024 (pill 97 px < 120 px) and pass at 1280. Decision: run them at 1280.

## 3. Files
`App/app/templates/_cleaning_table.html` (phone block only), the `/* cleaning (0542) */` block at the end of `App/app/static/app2.css` (+ `?v=` key in `base.html`, `tests/static_versions.json` via `--write`), `App/tests/test_cleaning_browser.py` (those three tests' widths only). Screenshots `docs/tasks/screenshots-0549/`. Report `docs/tasks/0549-report.md`.

## 4. Steps
1. Today card `display:block` and the check-in time change. Bump the key, `--write`. Commit `0549 step 1`.
2. Move the three tests to 1280 px. Run `.venv/bin/python -m pytest tests/test_cleaning_browser.py tests/test_0540_cleaning_tables.py tests/test_0541_cleaning_header.py tests/test_design_cleaning.py tests/test_cleaning.py tests/test_static_versions.py tests/test_host_language.py -q --tb=line -rf 2>&1 | tail -20` and `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k cleaning -q --tb=short 2>&1 | tail -40`. Commit `0549 step 2`.
3. Screenshots: `UBYHOST_SHOTS_V2=1 UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k screenshots -q 2>&1 | tail -5`, copy `cleaning-390.png` and `cleaning-1280.png` from `docs/tasks/screenshots-0710/` to `docs/tasks/screenshots-0549/`, then `git checkout -- docs/tasks/screenshots-0710 && git clean -fq docs/tasks/screenshots-0710`. For the phone mockup Úklid screen write `/tmp/uklid_shot.py`: `sys.path.insert(0, "<repo>/App/tests")`, `from v2_mockup import phone_url, show_phone_screen`, open `phone_url()` in Chromium at viewport 390x844, `show_phone_screen(page, "uklid")`, wait 300 ms, screenshot the visible `.scr.on` element (or the full page if that fails) to `docs/tasks/screenshots-0549/mockup-uklid-390.png`. Commit `0549 step 3`.

## 5. Do not touch
Shared rules, the desktop tables, the cleaner's shared view, JS, routes, the mockups, `v2_mockup.py`. Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` only. Do not push.

## 6. Commands
From `App/` with `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`; then from the repo root `python3 scripts/design_lint.py 2>&1 | tail -3`.

## 7. Acceptance
Step 2 first set passes; cleaning compare left with only the shared items (tab, actbar, 768, 320 security prompt); lint OK; three screenshots.

## 8. Stop and ask
Stop if a fix needs a shared rule or a file outside section 3.

## 9. Report
`docs/tasks/0549-report.md`: Status, tails, screenshot paths.
