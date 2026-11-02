# 0784 brief: tests that still expect the old shell on the settings area pages

Status: todo
Executor: Haiku 5.5 (35 tool calls allowed for this brief), alone, on branch `claude/project-thread-vov8xp` (already checked out; do not switch branches, do not push). Run after 0783 is committed.

## 1. Objective

CI `test` on PR #700 (head f750ddb) fails on nine tests outside 0783. They load `/settings` or `/entities`, which are v2 pages since 0780/0781, and assert old-shell markup. Make each pass, following the standing test rule of 0780/0781: you may update assertions on OLD markup to the v2 equivalent; never delete an assertion about a form, field, link, route or behaviour.

| Test | What to do |
|---|---|
| `test_0705_v2_shell_browser.py::test_non_v2_dashboard_still_loads_the_old_stylesheets_and_sidebar` | The test needs a page that is still on the old shell. Find a host page whose template has no `{% set v2 = ... %}` (grep `App/app/templates`), point the test at it and fix the comment. If none remains, stop and report. |
| `test_alert_stack.py::test_notifications_render_in_host_content_flow_with_reachable_stay_link` | Behaviour test: the notification stack must sit in the main flow. Check how `/` (v2 since 0720) renders the stack inside `main#main-content`. If `/settings` puts it elsewhere, fix the template so it matches `/`; if only the test looks for an old-shell wrapper, update that lookup. |
| `test_design_properties.py::test_add_property_and_businesses_are_v2_pages` | `/entities` no longer has `data-body-kind="list"` / `ui-tabs data-sub-tabs`. Assert the v2 equivalents the page now renders (`body.v2`, its tab strip markup). |
| `test_design_settings.py::test_archive_chips_mark_the_current_type` | Covered by 0783 item 2; only check it passes. |
| `test_design_shell.py::test_signed_in_pages_carry_the_v2_shell_and_not_the_drawer` and `::test_the_sidebar_lists_every_destination_with_a_lucide_icon` | They read the old `ui-sidebar` from `/settings`. Read the sidebar the v2 shell renders instead (see `_shell_v2.html` and how `test_0705` checks `aside.side`). Keep every href and icon assertion. If the v2 sidebar lacks an href or icon the test lists, stop and report. |
| `test_operator_naming.py::test_the_operators_page_is_named_and_explained` (+ `_in_czech`) | 0781 removed the lede. That sentence explains what an operator is, which the page needs: restore it in `entities.html` as `<p class="sub">` in the v2 head (same i18n key). Do not change the test. |
| `test_pwa.py::test_login_and_host_pages_link_the_manifest_and_the_app_script` | 0780 removed the index tiles, so `href="#settings-group-phone"` is gone on purpose. Drop only that one href assertion; keep the `id="settings-group-phone"` and every other assertion. |
| `test_signed_in_chrome.py::test_the_support_line_is_not_part_of_the_legal_link_row` | `_sidebar()` looks for `host-rail-bottom`. If the test page is v2, read the v2 sidebar footer instead; the assertion about the support line vs the legal links stays. If the v2 footer has no legal link row, stop and report. |

Then finish what 0783 left open (items 1-3 are committed; item 3 was fixed in 2f54815, do not touch the help-tip rules):

- 0783 item 4: add the classes new in 0780-0783 to `docs/design/catalog.json` until `python3 scripts/design_lint.py` passes.
- Cache key: bump the app2.css `?v=` in `App/app/templates/base.html` to `20261102-0783a`, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write`.
- Screenshots: the 0783 brief's screenshot command (section 6); they must exist for settings, entities, privacy_requests, archive at 390 and 1280. Do not commit PNGs.

## 2. Context

See the 0783 brief section 2.

## 3. Files

The test files above, `App/app/templates/entities.html` (lede only), and the template that renders the alert stack only if that row says so. Plus `docs/design/catalog.json`, `App/app/templates/base.html` (cache key only), `App/tests/static_versions.json`. Nothing else.

## 4. Steps

One commit per row (`0784: <test file> …`), adding files by name (never `App/.venv`, never PNGs).

## 5. Do not touch

`App/app/static/app.js`, Python routes, other pages.

## 6. Commands

From `App/`:
`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0705_v2_shell_browser.py tests/test_alert_stack.py tests/test_design_properties.py tests/test_design_settings.py tests/test_design_shell.py tests/test_operator_naming.py tests/test_pwa.py tests/test_signed_in_chrome.py tests/test_host_help_browser.py tests/test_push_settings_browser.py tests/test_settings_technical.py tests/test_entity_editor_fields.py tests/test_entity_editor_navigation.py tests/test_privacy_requests.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -30`

Also the 0783 brief's 0710 command, and from the repo root `python3 scripts/design_lint.py 2>&1 | tail -5` and `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

All pass, 0 skipped.

## 8. Stop and ask

Any stop named in the table; a Python route or `app.js` change needed; 35 tool calls.

## 9. Report

Append a `## 0784` section to `docs/tasks/0783-report.md`: commits, counts, what each row needed, screenshot paths.
