# 0716: v2 shell keeps every feature of the old shell
Status: todo
Depends on: 0715 | Base commit: claude/project-thread-50hyv5 | Branch: task/0716-v2-shell-parity
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
The v2 shell (`App/app/templates/_shell_v2.html`, used by `/`) lost features the old sidebar (`App/app/templates/_shell_sidebar.html`) has. Restore them in v2 markup and app2.css so these tests pass. The mockup look stays; features come back as quiet elements in the mockup's style.

## 2. Context and decisions (orchestrator, 2026-11-01)
Failing tests (local run of the non-browser suite on the branch):
- `test_environment_banner.py::test_production_shows_a_quiet_named_sidebar_badge` and `test_security.py::test_mock_environment_is_declared_on_every_host_page` (expects `class="env-badge ui-env mock"` on `/`): copy the env badge include/markup from `_shell_sidebar.html` into `_shell_v2.html` (same classes), placed under the logo; style it quietly in app2.css (small pill, `--ink2` on `--side2`).
- `test_havel_palette.py::test_no_match_opens_havel_with_the_query`: the old shell's search opens a palette that falls back to Havel. Make the v2 `.search` button carry the same hooks/attributes the old search has (compare the two templates; app.js is shared, do not edit it).
- `test_host_account_navigation.py::test_ordinary_user_sees_no_admin_controls`: v2 must show admin links only to admins, using the same condition as `_shell_sidebar.html`.
- `test_design_shell.py::test_signed_in_pages_carry_the_v2_shell_and_not_the_drawer` and `::test_the_sidebar_lists_every_destination_with_a_lucide_icon`: read both tests. Destinations and icons must match the old sidebar's list (same hrefs, same icon macro if the test checks it). If a test asserts old-shell-only classes on `/`, point it at `/reservations` (old shell) and add one assertion that `/` has `id="app-sidebar"` with every destination href.
- `test_accounts.py::test_host_admin_portal_shows_ubyhost_support_email`: show the support email where the old shell shows it (probably the help/support block); put it in the v2 bottom block as a quiet link.
- `test_host_redesign.py::test_all_host_destinations_render_with_valid_structure[en,cs]`: read the assertion and make `/` satisfy it (likely a landmark, skip link or heading structure).
- Shared phone rule: app2.css hides table columns 2 and 3 below 768 px for every v2 card table, which hides other pages' columns (the cleaning page's time and arrival columns). Scope that rule to the Overview's Dnes table only (give that card a class in the selector, e.g. `.ov-today`; read dashboard.html for the existing class, do not edit dashboard.html—if it has no class, use `#main-content .card:last-of-type table` only as a last resort and say so).
Rules: copy conditions and hooks from `_shell_sidebar.html` exactly; do not change `_shell_sidebar.html`, `app.js` or routes. Never skip or xfail.
- Bump the app2.css key in `base.html` to `20261101-0716`, then from App/ `.venv/bin/python tests/test_static_versions.py --write | tail -1`.

## 3. Files
`App/app/templates/_shell_v2.html`, `App/app/static/app2.css`, `App/app/templates/base.html` (key), `App/tests/static_versions.json`, the named test files (only where section 2 allows), report `docs/tasks/0716-report.md`.

## 4. Steps
Fix test by test; run only that file (`-q --tb=line | tail -15`); commit every 2-3 fixes with explicit paths.

## 5. Do not touch
`dashboard.html` (brief 0717 runs in parallel), `_shell_sidebar.html`, `app.js`, routes.

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_environment_banner.py tests/test_security.py tests/test_havel_palette.py tests/test_host_account_navigation.py tests/test_design_shell.py tests/test_accounts.py tests/test_host_redesign.py tests/test_0710_v2_mockup_match_browser.py tests/test_static_versions.py -q --tb=line -rs 2>&1 | tail -30` (0 skipped). Repo root: `python3 scripts/design_lint.py | tail -1; python3 scripts/context_lint.py | tail -1`.

## 7. Acceptance
All listed tests pass, 0 skipped; 0710 still green.

## 8. Stop and ask
Stop if restoring a feature needs a route or app.js change.

## 9. Report
`docs/tasks/0716-report.md`: status, test tails, change per test, deviations.
