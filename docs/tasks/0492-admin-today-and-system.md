# 0492: Admin redesign 3+4/4: Today shows system problems; System page folds in Incidents; four tabs
Status: review
Depends on: 0490 and 0491 merged (they edit the same tab list) | Base commit: main after both | Branch: task/0492-admin-today-system
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 70k tokens
Plan: [admin-portal-review](../plans/admin-portal-review.md), approved by the owner 2026-11-01.
## 1. Objective
The owner opens Admin and sees only what needs a decision. After 0490/0491 the tabs are Console, Customers, Billing, Incidents, Operations. After this brief they are four: **Today** (`/admin`), **Customers**, **Money** (`/admin/fakturace`), **System** (`/admin/operations`, with Incidents inside). Today also lists system problems; System shows each health block collapsed to one line unless it has a problem.
## 2. Context
- `/admin`: `admin_home` in `App/app/routes/admin_customers.py` (~line 26) renders `admin_home.html` (stats + four queues: overdue, ending, trials, unverified).
- `/admin/operations`: `operations_admin` in `routes/admin_accounts.py` (~line 953), `admin_ops.overview()` returns `filings`, `stuck`, `feeds`, `jobs`, `mail`, `alerts` (each `{"count", "rows"}`) and `ttlock`; plus `havel.admin_overview()`. Template sections `ops-filings` (with stuck inside), `ops-feeds`, `ops-jobs`, `ops-mail`, `ops-ttlock` (only when enabled), `ops-alerts`, `ops-havel`.
- `/admin/incidents`: `incidents_admin` (~line 930) renders `admin_incidents.html` (list + create form, `review_alerts` from `incidents.open_review_alerts()`); POST routes stay.
- `admin_operations.html` macro `workspace_link` links `/admin/users#user-<id>`; after 0490 that is a redirect.
## 3. Files
Edit: `admin_home.html`, `routes/admin_customers.py` (admin_home context), `admin_operations.html`, `routes/admin_accounts.py` (operations + incidents GET), `App/app/templating.py` (tabs), `App/app/host_i18n.py`/`host_vi_i18n.py` (new keys below). Delete `admin_incidents.html` (its markup moves). Tests: `tests/test_admin_operations.py`, `tests/test_admin_section_tabs.py`, tests that GET `/admin/incidents` (`grep -ln "admin/incidents" App/tests`), `tests/test_admin_customers.py`. Report `docs/tasks/0492-report.md`.
## 4. Steps
1. Tabs (`templating.py`): `("today", "/admin", "admin.tab.today")`, `("customers", "/admin/customers", "customers.title")`, `("money", "/admin/fakturace", "admin.tab.money")`, `("system", "/admin/operations", "admin.tab.system")`. Path mapping: `/admin` → today; `customers`, `users` → customers; `fakturace`, `funnel` → money; `operations`, `incidents` → system. New keys en/cs/vi: `admin.tab.today` Today / Dnes / Hôm nay; `admin.tab.money` Money / Peníze / Tiền; `admin.tab.system` System / Systém / Hệ thống; `admin.today.system` "System problems" / "Problémy systému" / "Sự cố hệ thống"; `admin.today.clear` "All clear. Nothing needs you today." / "Vše v pořádku. Dnes nic nečeká." / "Mọi thứ ổn. Hôm nay không có việc gì."
2. `admin_home`: add `ops = admin_ops.overview()` and `review_alerts = incidents.open_review_alerts()` to the context. In `admin_home.html` add one section `admin.today.system` before the queues, listing only blocks with `count > 0` (filings, stuck, feeds, jobs, mail, alerts, plus open incident reviews) as one line each: the block title key already used on the operations page, its count badge, linking to `/admin/operations#ops-<block>` (incidents: `#incidents`). Hide the section when all are zero. When the system section and all four queues are empty, show `ui_empty(t('admin.today.clear'))` instead of empty queues.
3. `admin_operations.html`: wrap each health block in `<details class="ui-section" id="ops-...">` with its heading and badge in `<summary>`; add `open` when its count > 0 (ttlock: when failed > 0 or used ≥ 80 % of limit; havel: when gaps exist). Keep ids and inner markup. `workspace_link` points to `/admin/customers/<owner_user_id>`.
4. Move the incidents list, create form and review alerts from `admin_incidents.html` into a last section `id="incidents"` on the operations page (operations route also passes `rows` and `review_alerts`, built as in `incidents_admin`). `GET /admin/incidents` becomes a 303 to `/admin/operations#incidents`; incident POSTs redirect there too. Delete `admin_incidents.html` and keys used only by its page header.
5. `admin_home.html` header: drop the Customers and Payments buttons (the tabs carry them).
6. Stale links after 0490: `settings.html` (~line 81), the command palette entry (`grep -n '/admin/users' App/app/api.py`) and `stop_impersonating`'s redirect point to `/admin/customers` (or `/admin/customers/<id>` where an id is known) instead of `/admin/users`.
7. Tests: section-tabs test expects the four tabs and current tab per path; operations test asserts blocks are `<details>`, open only with problems; incident tests follow the redirect; one test that `/admin` shows the clear state with no data and a system line when a job is late.
## 5. Do not touch
`admin_ops.py` queries, billing, migrations, CSS, JS, `_shell_*.html`.
## 6. Commands
From `App/`: `.venv/bin/python -m pytest tests/test_admin_operations.py tests/test_admin_section_tabs.py tests/test_admin_customers.py $(grep -ln "admin/incidents" tests/*.py | tr '\n' ' ') -q --tb=short -x 2>&1 | tail -30`, then `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_design_shell_browser.py -q --tb=short -x 2>&1 | tail -30` (0 skipped). Repo root: `python3 scripts/context_lint.py | tail -5`.
## 7. Acceptance
Four tabs on every admin page; Today lists only problems or says All clear; System blocks collapsed unless failing; Incidents works inside System; tests pass, 0 skipped.
## 8. Stop and ask
Stop if 0490 or 0491 is not on main, or a test outside §3 fails.
## 9. Report
`docs/tasks/0492-report.md`, under 60 lines: files, both pytest tails, `git diff --stat origin/main`.
