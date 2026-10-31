# 0461: Admin section tabs (fixes "can't reach Funnel and Operations on phone")

Status: todo
Depends on: none | Base commit: main | Branch: task/0461-admin-section-tabs
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Every admin page shows one tab strip: Console, Customers, Billing, Users, Incidents, Operations, Funnel. On a phone the owner can reach every admin page from `/admin` (today Funnel and Operations have no link on phone at all).

## 2. Context
Bug report from the owner (iPhone, 2026-10-31): More sheet, Admin opens `/admin` (Operator console), which only has Customers and Payments buttons. Cause: commit 5583b1c pointed Admin at `/admin` and moved Users, Incidents, Operations, Funnel and Billing links into the desktop account menu (`_shell_sidebar.html:44-50`); the phone More sheet (`_shell_tabbar.html`) has no such block. `/settings` links only Users and Incidents. Fix: the tabs component of MASTER 5.2 and 7.6 (`ui_tabs` in `App/app/templates/_ui_layout.html:6`, scrolls horizontally on phone). One strip, one place: put it in a new partial so each page adds one line.

## 3. Files
- New: `App/app/templates/_admin_tabs.html` (a macro `admin_tabs(active)` returning `ui_tabs([...])`).
- Edit (add `{% block tabs %}{{ admin_tabs('<key>') }}{% endblock %}`): `admin_home.html` (console), `admin_customers.html`, `admin_customer.html` (active: customers), `admin_billing.html`, `users.html`, `admin_incidents.html`, `admin_operations.html`, `admin_funnel.html`.
- Edit: `App/app/host_i18n.py` only if a tab label key is missing; reuse existing keys first: `home.admin.title`, `customers.title`, `billing.admin.title`, `nav.users`, `users.incidents_link`, `ops.title`, `funnel.title`. Add each new key in en, cs and vi.
- Read first: `_ui_layout.html:1-30`, MASTER 5.2 and 7.6, `docs/design/pages/admin_customers.md`.

## 4. Steps
1. Read `ui_tabs` and one template that already passes `{% block tabs %}` (`grep -rn "block tabs" App/app/templates | head -5`).
2. Create `_admin_tabs.html`. Items in this order, hrefs: `/admin`, `/admin/customers`, `/admin/fakturace`, `/admin/users`, `/admin/incidents`, `/admin/operations`, `/admin/funnel`. Hide the Billing tab when `billing_enabled` is false only if `admin_home.html` already hides billing content that way; otherwise show it.
3. Add the one-line tabs block to each template in section 3. Do not remove any existing button or link.
4. Make `nav` consistent: all of these pages use `nav = 'admin'` (`admin_customers.html` currently uses `users`; check `grep -n "set nav" ` on the 8 files). Update `more_nav` in `_shell_tabbar.html:6` is already `admin`; leave it.
5. Fix the trailing-slash link `href="/admin/customers/{{ row.owner_user_id }}/"` in `admin_home.html` (trials queue) to match the other links (no trailing slash).
6. Update the page add-on docs `docs/design/pages/admin_customers.md` ("tabs: none" becomes the admin tab strip) and add one line to `docs/context/known-issues.md`: "Admin pages Funnel and Operations unreachable on phone: fixed by 0461".
7. Add `App/tests/test_admin_section_tabs.py`: log in as admin, GET each of the 7 pages with `?lang=en`, assert all 7 hrefs appear inside the tab strip and the current page's tab has `aria-current="page"`; as a non-admin host each page still returns 403/redirect as today.

## 5. Do not touch
Routes, auth, the sidebar, the More sheet, any CSS (the component already exists), billing logic, migrations. No new dependency.

## 6. Commands
From `App/`:
`.venv/bin/python -m pytest tests/test_admin_section_tabs.py tests/test_admin_operations.py tests/test_admin_funnel.py tests/test_admin_customers.py tests/test_billing_admin.py tests/test_design_admin.py tests/test_design_guardrails_browser.py -q --tb=short -x 2>&1 | tail -30`
Browser checks must show 0 skipped. From the repo root: `python3 scripts/context_lint.py | tail -30`.

## 7. Acceptance
- All 7 admin pages show the same strip; every tab link returns 200 as admin.
- At 390 px the strip scrolls sideways, no page overflow, the active tab visible; tap targets 44 px.
- Tests above pass, 0 skipped. Light mode, works without JavaScript (plain links).
- One 390 px screenshot per changed page (8) in the report.

## 8. Stop and ask
If `ui_tabs` cannot take 7 items without a CSS change, stop and report; do not edit CSS. If tests need the whole suite, stop at the named files.

## 9. Report
`docs/tasks/0461-report.md`, under 80 lines: files changed, test output tail, 8 screenshots.
