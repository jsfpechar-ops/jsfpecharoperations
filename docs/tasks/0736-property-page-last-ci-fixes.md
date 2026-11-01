# 0736: property pages: last CI fixes before merge
Status: todo
Depends on: 0735 (merge done) | Branch: claude/project-thread-819gyo
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Fix the failures left after 0547 so CI is green on the properties PR.

## 2. Context (orchestrator decisions)
1. `tests/test_host_unsaved_changes_browser.py::test_save_bar_discard_changes_button` line ~283 (`'Zapnuto' == ''`): `#sec-lock` is closed at load, so `inner_text()` is "". Read `loaded_status` after `page.locator("#sec-lock > summary").click()`. Test only.
2. `tests/test_property_navigation_browser.py` line ~464: after save from `section=automation`, the page returns to `section=reporting` (automation opens police, and police maps to reporting). Expect `section=reporting`. Test only.
3. `tests/test_a11y_guard_browser.py` on property pages:
   - Heading skip: `h3.property-section-title` right after `h1`. In `_property_editor.html` (and any other property partial with it), make those `h2` with the same class; if the class has a size rule, check the look stays the same.
   - `setup-continue` "Pokračovat" (`ui-btn-primary`, dark text on coral, contrast 3.72): on v2 in the page block of `App/app/static/app2.css`, give it `color:#fff` and a background that reaches 4.5:1 (use `var(--acc-text)` or the darker coral already in tokens.css; `grep -n acc tokens.css`).
   - Toast close 24x21 on smart-locks: make `.toast-stack .toast > [data-toast-close]` at least 24x24 at every width on v2 (the 44 px phone rule already exists near the top of app2.css).
4. Guest card overflow without JS at 360/390 (`div.guest-btns` and its copy buttons reach x=420). Without JS the copy buttons are wider; make `.guest-btns` children `min-width:0` and the buttons `max-width:100%` with text wrapping, below 1024. This must fix `tests/test_onboarding_wizard_browser.py::test_wizard_polish_and_overview_cards` [False-360-en, False-360-cs, False-390-cs].
5. `tests/test_0252_touch_sweep_browser.py` noCue on `/apartments` at ipad1024, 1180, desk2000 (demo rows). Read what "cue" the test needs (a chevron, an arrow or a hover style on a tappable row) and add it to the `/apartments` row in the page block, matching the computer mockup `props` view (`docs/design/mockup/ubyhost-redesign-v2.html`). If the mockup row has no cue, change the test to accept the v2 row (`a.card.prop` or the table row link) and say so.
6. `tests/test_host_property_controls_browser.py` line ~448: `#calendar-add #label_other` is not visible because `#sec-calendars` is closed. Open it first (`page.locator("#sec-calendars > summary").click()` or load `?view=bookings`). Test only.
7. `tests/test_0541_property_page_phone_browser.py`: add browser asserts for the 0547 behaviours: switch status text changes on toggle (seed a door-code lock as `tests/test_door_code_window_browser.py` does), an invalid required field in a closed section opens that section on submit, `?add_calendar=1` shows `#calendar-connect` without `is-collapsed`, and after save from the opened lock section the URL has `section=lock`.
8. `python3 scripts/design_lint.py`: fix any error it reports on our files (add a class to `docs/design/catalog.json`, or fix the rule). Report errors in other pages' files as not ours.

## 3. Files
The tests above, `App/app/templates/_property_editor.html` (heading level only), `App/app/static/app2.css` (page block; key bump in `App/app/templates/base.html`, then `--write`), `docs/design/catalog.json`.

## 4. Steps
1. Items 1, 2, 6 (tests). Commit.
2. Items 3, 4, 5 (CSS and heading); key bump, `--write`. Commit.
3. Items 7, 8. Commit.
4. Run section 6. Commit the report.

## 5. Do not touch
Routes, JS, other pages, the Overview and menu files. No new dependency.

## 6. Commands (from `App/`)
`export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, then each changed test file with `-k "not webkit" -q --tb=line -rfs -p no:cacheprovider 2>&1 | tail -8` (webkit is not installed; say so), then `tests/test_0534_property_page_v2.py tests/test_static_versions.py tests/test_0710_v2_mockup_match_browser.py tests/test_0503_page_inits_once_browser.py tests/test_0504_mixed_inits_once_browser.py`. Ruff `--select E9,F63,F7,F82,F401,F841` on app tests. From the repo root: design_lint and context_lint.

## 7. Acceptance
Every file named passes on chromium with 0 skipped, apart from not-ours failures listed with their failing line. The property page and list look the same at 390 and 1280 (one screenshot each in `docs/tasks/screenshots-0736/`, `?lang=cs`).

## 8. Stop and ask
Stop if a fix needs a route or JS change, or a save/POST does not save.

## 9. Report
Section "0736" at the end of `docs/tasks/0536-report.md`. Stage by name, never `git add -A`; never commit `App/.venv`. Do not push. Hand back with SubagentHandback; never post to the user.
