# 0782 brief: polish pass on the v2 settings area (Settings, Společnosti, Soukromí, Archiv)

Status: todo
Executor: Haiku 5.5, alone, in `/home/claude/jsfpecharoperations` on branch `claude/project-thread-vov8xp` (already checked out; do not switch branches, do not push).

## 1. Objective

0780 and 0781 moved `/settings`, `/entities`, `/privacy-requests` and `/settings/archived` onto the v2 shell. Fix what the orchestrator saw in the screenshots, plus one test, with CSS first and the smallest markup change otherwise:

1. **Help tips** (`help_tip` macro in `App/app/templates/_components.html`, script `initHelpTips` in `App/app/static/app.js`): on v2 pages the `?` is a grey square and the tip text is always shown inline. Port the old look from `App/app/static/host.css` / `components.css` (grep `help-tip`) into the `/* v2 ports of shared ui-* classes */` block of `app2.css`: a 24 px round quiet icon button (44 px tap area below 1024 px), text hidden until opened, opened text as a small popover or a line under the label, as the old CSS does. Do not edit app.js.
2. **Společnosti, desktop:** 16 px gap between the companies table card and the "Add an operator" card; form fields max 480 px wide (labels too); the phone field's prefix and number side by side on one row as before; "Fill from register" sits on the IČO row to the right of the input from 1024 px.
   **Společnosti, phone:** in the stacked company row, the Edit / Invoice settings / ⋮ actions are left-aligned on one row (wrap if needed), no centred grey blobs.
3. **Settings:** the `details.technical` sections inside a group card (Technical details, Activity log) get no border, background or shadow of their own: a 48 px summary row with the chevron at the right and a hairline above, like the other sections. The audit filter links (`.host-audit-filter`) look like the stays page `.chip` / `.chip.on` (`.is-active` = on).
4. **Test:** `tests/test_push_settings_browser.py::test_turning_alerts_on_sends_one_test_and_lists_this_device[en]` fails with a CSP `'unsafe-eval'` EvalError in `wait_for_function`; it passed before 0780. Find why (compare the CSP header and the script tags of `/settings` on `git show b3bebc2:App/app/templates/settings.html` vs now; v2 pages may skip a script the test waits for, e.g. the push settings script). Fix the page (include what the old page loaded) rather than the test. If only the test is wrong, change only its wait.

## 2. Context

- Rules for these pages: page-only rules go in their existing blocks (`/* 0780 settings page (v2) */`, `/* 0781 entities */`, …); generic ports only in `/* v2 ports of shared ui-* classes */` (another thread may also edit that block later: keep rules short and generic).
- From 1024 px controls are 40 px high, buttons 24 px tap minimum; below 1024 px 44 px.
- Screenshots of the current state: `/tmp/wt0780/docs/tasks/screenshots-0710/settings-*.png`, `/tmp/wt0781/docs/tasks/screenshots-0710/entities-*.png`.

## 3. Files

`App/app/static/app2.css`, `App/app/templates/settings.html`, `App/app/templates/entities.html`, `App/app/templates/_components.html` (help_tip only, if CSS cannot do it),
`App/app/templates/base.html` (cache key), `App/tests/static_versions.json`, `docs/design/catalog.json`, `App/tests/test_push_settings_browser.py` (only if item 4 says so), new `docs/tasks/0782-report.md`.

## 4. Steps

1. Items 1-4 in order; commit after each (`0782 item N: …`).
2. New classes into `docs/design/catalog.json`; `python3 scripts/design_lint.py 2>&1 | tail -5` from the repo root.
3. Cache key: app2.css `?v=` in base.html to `20261102-0782b` (then c, d… if the manifest refuses a reused key), then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.
4. Tests from `App/` (do NOT reinstall playwright):
   `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "settings or entities or privacy_requests or archive" -q --tb=short 2>&1 | tail -30`
   `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_push_settings_browser.py tests/test_design_settings.py tests/test_settings_technical.py tests/test_entity_editor_fields.py tests/test_entity_editor_navigation.py tests/test_privacy_requests.py tests/test_host_help_browser.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -30` (0 skipped).
5. Screenshots: `UBYHOST_SHOTS_V2=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k screenshots -q 2>&1 | tail -5`. Do not commit any PNG.
6. `python3 scripts/context_lint.py 2>&1 | tail -5` from the repo root. Never `git add` `App/.venv` or PNGs: add files by name.

## 5. Do not touch

`App/app/static/app.js`, the mockup, other pages' templates and app2.css blocks, Python routes.

## 6. Commands

The commands in section 4.

## 7. Acceptance

Section 4 tests pass with 0 skipped; items 1-4 visible in the 390 and 1280 screenshots.

## 8. Stop and ask

A test outside section 4 fails; item 4 needs a route or Python change; you reach 25 tool calls (commit what passes, report the rest).

## 9. Report

`docs/tasks/0782-report.md`: commits, test results with counts, what caused item 4, anything left.
