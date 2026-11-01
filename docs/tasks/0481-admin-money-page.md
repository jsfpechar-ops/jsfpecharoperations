# 0481: Admin redesign 2/4: Money page leads with the two jobs (mark paid, export the month)
Status: review
Depends on: 0472 (merged) | Base commit: main | Branch: task/0481-admin-money
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 60k tokens
Plan: [admin-portal-review](../plans/admin-portal-review.md), approved by the owner 2026-11-01.
## 1. Objective
`/admin/fakturace` shows 12 sections in one column. The owner's two jobs, marking an invoice paid and exporting the month, sit at sections 9 and 12. After this brief the page opens with Unpaid invoices, then Month export, then one closed `<details>` "Reports" holding everything else. The separate Funnel page (PostHog link, ads export) moves into Reports too, and its tab goes.
## 2. Context
- `App/app/templates/admin_billing.html`: sections by id: revenue, trend, movement, funnel (trial funnel counts), discounts, watch, portfolio, accounts, unpaid, statement, payments, month.
- `App/app/templates/admin_funnel.html` (27 lines): sections `funnel-posthog` and `funnel-ads-export` (only when `signup_enabled`); its route (`grep -rn '"/admin/funnel"' App/app/routes`) supplies `posthog_url`, `signup_enabled`, `ads_export_days`.
- Czech value of `billing.admin.funnel.title` is "Tryskový trychtýř" (wrong); en "Trial funnel".
## 3. Files
Edit: `admin_billing.html`, the billing admin route (add the three funnel context values), the funnel route, `App/app/templating.py` (drop the `funnel` admin tab), `App/app/host_i18n.py` (cs title fix; one new key `billing.admin.reports` en "Reports", cs "Přehledy", and vi in `host_vi_i18n.py` "Báo cáo"). Delete `admin_funnel.html`. Tests: `tests/test_admin_funnel.py`, `tests/test_billing_admin.py`, `tests/test_admin_section_tabs.py`. Report `docs/tasks/0481-report.md`.
## 4. Steps
1. Reorder `admin_billing.html`: keep the page's top stats/filters as they are; then sections `unpaid`, `month`; then `<details class="ui-section" id="reports"><summary>{{ t('billing.admin.reports') }}</summary>` containing, in this order, portfolio, payments, statement, revenue, trend, movement, funnel, discounts, accounts, watch, then the two former Funnel-page sections (same ids, same forms, same `signup_enabled` guard). Move blocks; change no markup inside them.
2. If the watch list has rows, it stays outside Reports, directly after `month` (it is an action list); when empty it lives in Reports.
3. `GET /admin/funnel` becomes a 303 to `/admin/fakturace#reports`; its template goes; `POST /admin/ads-conversions.csv` is unchanged.
4. cs `billing.admin.funnel.title`: "Trychtýř zkušebních období".
5. `templating.py`: remove the `funnel` admin tab; `/admin/funnel` maps to `billing`.
6. Tests: funnel assertions read `/admin/fakturace`; add one test that the first `ui-section` heading on `/admin/fakturace` is the unpaid title and that `id="reports"` is a `<details>` without `open`.
## 5. Do not touch
Billing calculations, exports, invoice routes, CSS, JS, migrations.
## 6. Commands
From `App/`: `.venv/bin/python -m pytest tests/test_admin_funnel.py tests/test_billing_admin.py tests/test_admin_section_tabs.py tests/test_billing_*.py -q --tb=short -x 2>&1 | tail -30`, then `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py -q --tb=short -x 2>&1 | tail -30` (0 skipped). Repo root: `python3 scripts/context_lint.py | tail -5`.
## 7. Acceptance
Page opens with Unpaid, then Month; everything else is inside a closed Reports; the ads export still works; tests pass, 0 skipped.
## 8. Stop and ask
Stop if moving a block changes a test result outside §3, or a block depends on being outside `<details>` (JS by id).
## 9. Report
`docs/tasks/0481-report.md`, under 60 lines: files, both pytest tails, `git diff --stat origin/main`.
