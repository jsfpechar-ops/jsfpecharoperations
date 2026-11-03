# 0783 brief: last fixes for the v2 settings area before review

Status: todo
Executor: Haiku 5.5, alone, on branch `claude/project-thread-vov8xp` (check it out from origin; do not switch branches).

## 1. Objective

Make the remaining tests of 0780-0782 pass and produce the review screenshots. Four open items, from the 0782 handback:

1. `tests/test_push_settings_browser.py::test_turning_alerts_on_sends_one_test_and_lists_this_device[en]`: Playwright `wait_for_function` with a string predicate hits the page CSP (`'unsafe-eval'` not allowed) on `/settings`. It passed before 0780 (commit `b3bebc2`). Find what differs on the v2 page (e.g. a script or element the predicate waits for that the v2 shell does not render, so the wait falls back to string evaluation, or a different page load path). Fix the page if it lost something; otherwise change only that wait to a non-eval form (`page.wait_for_selector` / `expect`).
2. `tests/test_design_settings.py::test_archive_chips_mark_the_current_type`: `/settings/archived` chips no longer carry `class="ui-chip"` (0781 changed them). Keep both classes on each chip (`class="chip ui-chip…"`) so the test and the v2 look both hold, unless the test only checks old markup: then update it (standing rule from 0781).
3. `tests/test_host_help_browser.py::test_host_wide_help_tips_are_wired_reachable_and_fit[360]` and `[390]`: the opened help popover (320 px) overflows on the property guests page and on `/entities`. 0782 removed `body.v2 details .help-tip-body{position:static}`; restore an equivalent so tips inside `details` and inside cards below 1024 px render in flow (static, full width), and keep the round 24 px button from 0782.
4. Add 0782's new classes to `docs/design/catalog.json` (`python3 scripts/design_lint.py`).

## 2. Context

CSS rules: page rules in their blocks (`/* 0780 settings page (v2) */`, `/* 0781 … */`); generic in `/* v2 ports of shared ui-* classes */` at the end of `App/app/static/app2.css`. Tablet layout (PR #698, approved): do not hard-code phone layout at 768.

## 3. Files

`App/app/static/app2.css`, `App/app/templates/settings_archived.html`, `App/app/templates/settings.html` (item 1 only), `App/tests/test_push_settings_browser.py`, `App/tests/test_design_settings.py` (items 1-2 only, as described), `App/app/templates/base.html` + `App/tests/static_versions.json` (cache key, next free letter after `20261102-0782b`), `docs/design/catalog.json`.

## 4. Steps

1. Items 1-4, one commit each (`0783 item N: …`), adding files by name (never `App/.venv`, never PNGs).
2. Cache key bump and `.venv/bin/python tests/test_static_versions.py --write` from `App/`.

## 5. Do not touch

`App/app/static/app.js`, the mockups, Python routes, other pages.

## 6. Commands

From `App/`:
`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "settings or entities or privacy_requests or archive" -q --tb=short 2>&1 | tail -30`
`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_push_settings_browser.py tests/test_design_settings.py tests/test_settings_technical.py tests/test_entity_editor_fields.py tests/test_entity_editor_navigation.py tests/test_privacy_requests.py tests/test_host_help_browser.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -30`
Screenshots: `UBYHOST_SHOTS_V2=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k screenshots -q 2>&1 | tail -5`
From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -5`, `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

All commands pass, 0 skipped. Screenshots exist for settings, entities, privacy_requests, archive at 390 and 1280.

## 8. Stop and ask

Item 1 needs a Python or app.js change; another test fails; 25 tool calls (commit what passes, report the rest).

## 9. Report

`docs/tasks/0783-report.md`: commits, test counts, the cause of item 1, screenshot paths.
