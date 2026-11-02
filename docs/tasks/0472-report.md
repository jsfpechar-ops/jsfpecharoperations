# 0472 report: admin section tabs
Status: blocked

## Files changed
- App/app/templating.py: `_template_section_tabs()` gets an `admin` section (7 tabs); `_template_page_tabs()` routes `/admin*` paths to it (second path segment picks the current tab); the settings branch no longer lists the admin navs.
- App/app/templates/admin_home.html, admin_customers.html, admin_customer.html: import + `{% block tabs %}{{ ui_section_tabs() }}{% endblock %}`. admin_home trailing slash removed from the trials-queue link.
- App/app/templates/_shell_sidebar.html: admin block removed from the account menu.
- App/tests/test_admin_section_tabs.py (new): 2 tests.
- docs/design/pages/admin_customers.md (tabs line), docs/context/known-issues.md (one line).

## Commands
1. `cd App && .venv/bin/python -m pytest tests/test_admin_section_tabs.py tests/test_admin_operations.py tests/test_admin_funnel.py tests/test_admin_customers.py tests/test_billing_admin.py tests/test_design_admin.py tests/test_design_shell.py tests/test_account_emails.py -q --tb=short -x`
   Tail: `43 passed in 4.27s` (0 failed, 0 skipped)
2. `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome .venv/bin/python -m pytest tests/test_design_shell_browser.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs`
   Tail: `26 passed in 109.42s` (0 failed, 0 skipped)
   Note: the Python playwright package was missing from the venv and is not in requirements-dev. I installed it into the local venv only (no repo change). Without `UBYHOST_BROWSER_EXECUTABLE` Playwright's bundled headless shell is absent, so the browser tests skip.
3. `python3 scripts/context_lint.py`
   Tail: `ERROR docs/context/known-issues.md: ~2503 tokens > cap 2500` then `context lint: FAIL`. The one-line addition from §4 step 6 pushed the file over its cap.

## Acceptance (§7)
- Tests: pass with 0 skipped (commands 1 and 2).
- Screenshots: NOT taken. docs/tasks/screenshots-0472/ does not exist. No existing browser fixture serves the admin pages, and I ran out of the tool-call budget.

## Deviations
- §4 step 4 says lines 44–50; the admin `{% if %}` block runs 44–51 (the `{% endif %}` is line 51). I removed 44–51, otherwise the template would not parse.
- §4 step 7 says `/settings` shows Settings, Archive, Privacy tabs. On this branch `settings.html` renders no tab strip at all (no `tabs` block, no page_header tabs). Test does not assert that; nothing was changed there.
- Browser-test environment: see command 2 note.
- `git diff --stat origin/main` is not meaningful here: the branch is far behind origin/main (194 files). Diff of this brief's commits only: `git diff --stat 8363c51..HEAD`.
- Commits: `0472 step 1` (f517628), `0472 step 3-5` (1f2e01d), `0472 step 6-7`, plus this report commit.

## Stopped on / owner steps left
1. Context lint is red. Compact one line in docs/context/known-issues.md by about 3 tokens (or the orchestrator does it), then rerun `python3 scripts/context_lint.py`.
2. Screenshots at 390 px of `/admin` and `/admin/users` into docs/tasks/screenshots-0472/ are still missing.
3. Decide whether `/settings` should show the Settings/Archive/Privacy strip (brief assumes it does; it does not today).
