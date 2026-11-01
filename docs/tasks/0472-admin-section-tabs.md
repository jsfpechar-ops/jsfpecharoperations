# 0472: Admin section tabs (owner can't reach Users or Operations from the Admin icon)
Status: review
Depends on: none | Base commit: main 0ee0152 | Branch: claude/project-thread-sq91vx
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 60k tokens
Replaces: 0461 in stale PR #599 (number taken on main; its 0462 "console polish" is dropped as extra).
## 1. Objective
Every admin page shows one tab strip: Console, Customers, Billing, Users, Incidents, Operations, Funnel. From the Admin icon (desktop sidebar or phone More sheet) the owner reaches every admin page in one tap. Today `/admin` links only Customers and Payments; Users, Incidents, Operations and Funnel sit only in the desktop account menu, and the admin pages show the Settings tabs (Settings, Archive, Privacy) instead.
## 2. Context
- `App/app/templating.py`: `_template_section_tabs()` (~line 410) builds a section's tabs; `_template_page_tabs()` (~line 450) picks them from `nav` and the path. Its last branch sends the admin navs (`users`, `incidents`, `operations`, `funnel`, `billing_admin`) to the settings section: that is the wrong strip.
- `ui_section_tabs()` in `_ui_layout.html:11` renders `page_tabs()`. `admin_billing.html`, `admin_funnel.html`, `admin_incidents.html`, `admin_operations.html`, `users.html` already have `{% block tabs %}{{ ui_section_tabs() }}{% endblock %}`. `admin_home.html`, `admin_customers.html`, `admin_customer.html` do not.
- All admin pages live under `/admin` (`/admin`, `/admin/customers[/id]`, `/admin/fakturace[...]`, `/admin/users`, `/admin/incidents`, `/admin/operations`, `/admin/funnel`). `users.html` and `admin_customers.html` both use `nav = 'users'`, so pick the admin tab from the path, not from `nav`.
- Label keys exist in en, cs, vi: `home.admin.title`, `customers.title`, `billing.admin.title`, `nav.users`, `users.incidents_link`, `ops.title`, `funnel.title`. No new key.
## 3. Files
Edit: `App/app/templating.py`, `App/app/templates/admin_home.html`, `admin_customers.html`, `admin_customer.html`, `App/app/templates/_shell_sidebar.html` (lines 44–50 only), `docs/design/pages/admin_customers.md`, `docs/context/known-issues.md`. New: `App/tests/test_admin_section_tabs.py`, `docs/tasks/0472-report.md`. Edit existing tests only where they assert the removed account-menu links or the Settings tabs on admin pages.
## 4. Steps
1. `_template_section_tabs()`: add `elif section == "admin":` with items `("console", "/admin", "home.admin.title")`, `("customers", "/admin/customers", "customers.title")`, `("billing", "/admin/fakturace", "billing.admin.title")`, `("users", "/admin/users", "nav.users")`, `("incidents", "/admin/incidents", "users.incidents_link")`, `("operations", "/admin/operations", "ops.title")`, `("funnel", "/admin/funnel", "funnel.title")`.
2. `_template_page_tabs()`: before the settings branch, `if path == "/admin" or path.startswith("/admin/"):` take the second path segment (`""` → `console`, `fakturace` → `billing`, `customers`/`users`/`incidents`/`operations`/`funnel` → same name, anything else → `""`) and return `_template_section_tabs(request, "admin", current)`. Then remove `users`, `incidents`, `operations`, `funnel`, `billing_admin` from the settings branch's tuple.
3. Add `{% block tabs %}{{ ui_section_tabs() }}{% endblock %}` plus the import line `{% from "_ui_layout.html" import ui_section_tabs with context %}` (copy from `admin_operations.html:4`) to `admin_home.html`, `admin_customers.html`, `admin_customer.html`. Skip the import where the file already has it.
4. `_shell_sidebar.html`: delete the admin block in the account menu (the `{% if current_user.role == 'admin' %}` with the six `/admin...` links, lines 44–50). The Admin rail entry (line 29) stays and now leads to the tabs. Change nothing else in this file.
5. `admin_home.html`: the trials-queue link `href="/admin/customers/{{ row.owner_user_id }}/"` loses its trailing slash.
6. `docs/design/pages/admin_customers.md`: tabs line says the admin tab strip. `docs/context/known-issues.md`: one line "Admin Users/Operations/Incidents/Funnel unreachable from the Admin icon (phone: no link at all): fixed by 0472."
7. `App/tests/test_admin_section_tabs.py` (fixtures: copy the admin login from `tests/test_admin_operations.py`): as admin GET each of `/admin`, `/admin/customers`, `/admin/fakturace`, `/admin/users`, `/admin/incidents`, `/admin/operations`, `/admin/funnel` with `?lang=en`; assert 200, all seven hrefs inside the `class="ui-tabs"` nav, the page's own tab has `aria-current="page"`, and no `/settings/archived` tab. As a non-admin host `/admin/users` and `/admin/operations` answer as today (403 or redirect). `/settings` still shows Settings, Archive, Privacy tabs.
## 5. Do not touch
Routes, auth, `_shell_tabbar.html`, `_shell_topbar.html`, `base.html`, any CSS or JS (another thread edits the top bar and CSS), billing logic, migrations. No new dependency.
## 6. Commands
From `App/`: `.venv/bin/python -m pytest tests/test_admin_section_tabs.py tests/test_admin_operations.py tests/test_admin_funnel.py tests/test_admin_customers.py tests/test_billing_admin.py tests/test_design_admin.py tests/test_design_shell.py tests/test_account_emails.py -q --tb=short -x 2>&1 | tail -30`, then `.venv/bin/python -m pytest tests/test_design_shell_browser.py tests/test_design_guardrails_browser.py -q --tb=short -x 2>&1 | tail -30` (0 skipped). From the repo root: `python3 scripts/context_lint.py | tail -5`.
## 7. Acceptance
All seven admin pages show the same strip with the right tab current; tests above pass, 0 skipped; plain links (no JS). One 390 px screenshot of `/admin` and `/admin/users` in `docs/tasks/screenshots-0472/`.
## 8. Stop and ask
Stop if `ui_tabs` needs a CSS change to fit seven items at 390 px, or if any test outside §6 must change.
## 9. Report
`docs/tasks/0472-report.md`, under 60 lines: files changed, both pytest tails, screenshot paths, `git diff --stat origin/main`.
