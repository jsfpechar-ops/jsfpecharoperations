# 0490: Admin redesign 1/4: one place per host (Users merges into Customers)
Status: todo
Depends on: 0472 (merged) | Base commit: main | Branch: task/0490-admin-customers-merge
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 70k tokens
Plan: [admin-portal-review](../plans/admin-portal-review.md), approved by the owner 2026-11-01.
## 1. Objective
Today every host appears in two lists, `/admin/customers` (billing) and `/admin/users` (account), and the customer page has two buttons (Manage, Preview) that open the same `/admin/users?manage=` link. After this brief a host is managed in one place: the customer detail page. The Users page and its tab go away.
## 2. Context
- Roles are only `host` and `admin`. Customers lists `role = 'host'` (`App/app/admin_customers.py`).
- `users.html` (122 lines) holds: the manage panel (change email with reason, open workspace with reason, schedule deletion with typed confirm), a row menu per user (disable/enable, send invite, withdraw Meta/Google ads consent, export data), the "missing email" banner, and the create-host form (`POST /admin/users`). Routes: `App/app/routes/admin_accounts.py` from `@router.get("/admin/users")` (~line 686) on; they redirect back with `_back("/admin/users", ...)`.
- `admin_customer.html` already has disable/enable (`customer_toggle_active`) and resend verification in `routes/admin_customers.py`; its header has Manage and Preview buttons (lines 9 and 11) that both go to `/admin/users?manage=`.
- Admin accounts (role admin) are not managed from the UI after this brief; the owner is the only admin.
## 3. Files
Edit: `App/app/templates/admin_customer.html`, `admin_customers.html`, `App/app/routes/admin_accounts.py`, `App/app/routes/admin_customers.py` (only if the detail context needs the user row fields), `App/app/templating.py` (drop the `users` admin tab), `App/app/host_i18n.py` / `host_vi_i18n.py` (only to delete keys no template uses any more). Delete: `App/app/templates/users.html`. Tests: the ones that hit `/admin/users` (`grep -ln "admin/users" App/tests`), `tests/test_admin_section_tabs.py`. Report `docs/tasks/0490-report.md`.
## 4. Steps
1. On `admin_customer.html`, put the account actions in the existing `customers.account` section (line ~18), using the same macros as today: change email (with reason when one exists), send invite (active + email), open workspace (reason optional), export data, withdraw Meta/Google consent (only when given), schedule deletion (typed confirm). Keep every form's `action` URL and field names exactly as in `users.html`. Not for the signed-in admin's own id, same as today.
2. Delete the header buttons Manage and Preview (lines 9 and 11). Keep Payments.
3. On `admin_customers.html`, add the create-host form (same fields and `POST /admin/users`) in a section below the table, and the missing-email banner above it.
4. `admin_accounts.py`: every per-user POST under `/admin/users/{id}/...` redirects to `/admin/customers/{id}` (flash messages unchanged); `POST /admin/users` redirects to `/admin/customers`; `/admin/users/{id}/toggle` is removed if `customer_toggle_active` does the same (compare both; if they differ, keep the one that bumps `session_version` and say so in the report). `GET /admin/users` becomes a 303 to `/admin/customers` (old links in mails keep working); `_render_users` and its query go. Delete `users.html` and any i18n key used only there.
5. `templating.py`: remove the `users` item from the admin tabs; `/admin/users` maps to the `customers` tab.
6. Tests: move assertions from the users page to the customer page (same forms, same POSTs), add one test that `GET /admin/users` answers 303 to `/admin/customers`, one that the customer page no longer contains `/admin/users?manage=`.
## 5. Do not touch
Billing logic, migrations, auth, CSS, JS, `_shell_*.html`. No new route, no new dependency.
## 6. Commands
From `App/`: `.venv/bin/python -m pytest tests/test_admin_section_tabs.py tests/test_admin_customers.py tests/test_account_emails.py $(grep -ln "admin/users" tests/*.py | tr '\n' ' ') -q --tb=short -x 2>&1 | tail -30`, then `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_design_shell_browser.py -q --tb=short -x 2>&1 | tail -30` (0 skipped). Repo root: `python3 scripts/context_lint.py | tail -5`.
## 7. Acceptance
Every action that existed on the Users page works from the customer page with the same POST; no page links to `/admin/users?manage=`; tests above pass, 0 skipped; one 390 px screenshot of a customer page in `docs/tasks/screenshots-0490/` if a browser fixture allows it.
## 8. Stop and ask
Stop if a test outside §3 fails, or if a Users-page action has no matching route.
## 9. Report
`docs/tasks/0490-report.md`, under 60 lines: files, both pytest tails, removed keys, `git diff --stat origin/main`.
