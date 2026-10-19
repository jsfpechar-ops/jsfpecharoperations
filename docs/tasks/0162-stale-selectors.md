# 0162: admin heading placeholder and two stale test selectors

Status: done
Depends on: 0161 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

Three small faults found in the orchestrator review:
1. `/admin/users?manage=<id>` shows the heading "Manage {name}" literally: `host_i18n` formats with `%(name)s`, not `{name}`.
2. `test_property_create_browser.py` line 437 looks for `.setup-wizard-skip .link-button`; the skip control is now a `ui-btn` button.
3. `test_host_properties_navigation.py` `_FIT_JS` looks for `.properties-table .row-actions > a.btn`; each row now has a row menu trigger instead of an Open button.

## 2. Context

Only the selectors are stale; the pages are correct. Do not loosen any other assertion.

## 3. Files

`App/app/host_i18n.py`, `App/tests/test_property_create_browser.py`, `App/tests/test_host_properties_navigation.py`, `docs/tasks/0162-*`.

## 4. Steps

1. In `App/app/host_i18n.py` replace `"users.manage.title": 'Manage {name}',` with `"users.manage.title": 'Manage %(name)s',` and `"users.manage.title": 'Správa účtu {name}',` with `"users.manage.title": 'Správa účtu %(name)s',`. Each occurs once; if not, stop.
2. In `App/tests/test_property_create_browser.py` replace `page.locator(".setup-wizard-skip .link-button").count() == 1` with `page.locator(".setup-wizard-skip button").count() == 1`.
3. In `App/tests/test_host_properties_navigation.py` replace `'.properties-table .row-actions > a.btn'` with `'.properties-table .row-actions .row-menu-trigger'`.
4. Tests from `App/`:
   - `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_admin_users.py -q 2>&1 | tail -3` (skip any file that does not exist; run `ls tests | grep -i -E "i18n|admin_user"` to find them)
   - `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_property_create_browser.py tests/test_host_properties_navigation.py tests/test_design_guardrails_browser.py -q -rs 2>&1 | tail -6` (foreground, timeout 600000)
   - Then from the repo root: `git checkout -- docs/tasks/0102-evidence && git clean -fdq docs/tasks/0102-evidence`

   Expected: all passed, 0 skipped. If a test fails twice, stop and report its message verbatim.
5. Commit: `git add App/app/host_i18n.py App/tests/test_property_create_browser.py App/tests/test_host_properties_navigation.py docs/tasks/0162-* && git commit -m "0162: admin manage heading placeholder, two stale test selectors"`.

## 5. Do not touch

Anything else; hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] Three replacements made, all named tests pass with 0 skipped.

## 8. Stop and ask

An anchor is missing, or a test fails twice.

## 9. Report

`docs/tasks/0162-report.md`, short; `Status: review`.
