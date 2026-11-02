# 0547: property page: restore the behaviours that the 0539 removal took away
Status: todo
Depends on: commit affc181 (this branch) | Branch: claude/project-thread-819gyo
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
0539 deleted `initPropertyViews` from `App/app/static/app.js` because the tabs are gone. That function also did four things the one-page layout still needs, and tests now fail on them. Put those four back as one small init for the v2 property page, and fix the save bar being covered at 1280 px.

## 2. Context
- Removed code: `git show 7b3cee4 -- App/app/static/app.js` (the `initPropertyViews` block). Reuse its code for the parts below; drop everything about views, tabs and groups.
- affc181 put a switch-status handler into `App/app/static/host.js`. Revert that host.js hunk; the logic belongs in app.js next to `initPropSectionLinks` and `initPhoneDefaultClosed`. Use `claimNode` like the other inits.
- The four behaviours, on `form#property-settings-form`:
  1. Switch status. For each `input[data-switch-saved]`, on change, update the status element named by its `aria-describedby`: text from `data-on`, `data-off` or `data-unsaved`, plus the classes `is-on` and `is-unsaved`. This is the exact old code. It also makes discard work, because discard dispatches change.
  2. Invalid field in a closed section. On `invalid` (capture), open the field's `closest("details.prop-sec")` so the browser can show the message and focus the field. Use the old "revealing" guard so it runs once per submit.
  3. Calendar connect panel. `#calendar-connect` (`_property_calendars.html`) starts with `is-collapsed` unless the server opened it. On load, if `add_calendar=1` is in the URL, or the hash targets `#calendar-connect` or something inside it, remove `is-collapsed` and open `details#sec-calendars`.
  4. Return URL after save. The hidden `input[data-property-return]` carries `?view=settings&section=<group>`. On submit, set it from the most recently opened section, so the page comes back with that section open. Map: sec-basics→property, sec-police→reporting, sec-fee→reporting, sec-messages→guests, sec-lock→lock. Calendars is outside the form, so it does not apply. Keep the server value when nothing was opened.
- Save bar at 1280 (bug B, affc181 tried z-index): `tests/test_host_unsaved_changes_browser.py::test_without_javascript_nothing_changes` (JS off) reports that `aside.preview` intercepts the click on `.savebar button[type=submit]`. Find out which element really covers it with JS off (`document.elementFromPoint` at the button centre, with `java_script_enabled=False`). Fix it in the property page block of `App/app/static/app2.css`, for example with z-index and `position` on the savebar without JS, or so the aside does not extend under the fixed bar.

## 3. Files
`App/app/static/app.js`, `App/app/static/host.js` (revert the affc181 hunk only), `App/app/static/app2.css` (page block), `App/app/templates/base.html` (keys), `App/tests/static_versions.json` (`--write`), `App/tests/test_0541_property_page_phone_browser.py` (add browser asserts for 1 to 4; seed a door-code lock for 1 the way `tests/test_door_code_window_browser.py` does). Report: section "0547" at the end of `docs/tasks/0536-report.md`.

## 4. Steps
1. JS 1 to 4, the host.js revert, key bump, `--write`. Commit.
2. Bug B. Commit.
3. Tests, then section 6. Commit.

## 5. Do not touch
Templates, routes, other pages, the unsaved dialog logic. No new dependency.

## 6. Commands (from `App/`)
`export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, then `.venv/bin/python -m pytest tests/test_0541_property_page_phone_browser.py tests/test_0534_property_page_v2.py tests/test_static_versions.py tests/test_door_code_window_browser.py tests/test_0503_page_inits_once_browser.py tests/test_0504_mixed_inits_once_browser.py -k "not webkit" -q --tb=line -p no:cacheprovider 2>&1 | tail -8`, ruff `--select E9,F63,F7,F82,F401,F841` on app tests tools, design_lint and context_lint from the repo root.

## 7. Acceptance
Toggle and discard update the switch status text. An invalid field in a closed section opens it. `?add_calendar=1` shows the connect panel open. Save returns to the last opened section. With JS off at 1280 px, the save button can be clicked. Tests pass with 0 skipped.

## 8. Stop and ask
Stop if the init-once tests (0503/0504) need a new expected count you can't explain.

## 9. Report
Section "0547" in `docs/tasks/0536-report.md`. Stage by name, never `git add -A`; never commit `App/.venv`. Do not push. Hand back with SubagentHandback; never post to the user.
