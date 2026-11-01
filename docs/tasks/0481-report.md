# 0481 report: Money page leads with the two jobs

Status: review

## Files
- App/app/templates/admin_billing.html: Unpaid, Month, Watch (if rows), then closed `<details id="reports">` with the rest and the two former Funnel sections.
- App/app/templates/admin_funnel.html: deleted.
- App/app/routes/admin_billing.py: passes posthog_url, signup_enabled, ads_export_days.
- App/app/routes/admin_accounts.py: GET /admin/funnel is a 303 to /admin/fakturace#reports; unused `analytics` import removed.
- App/app/templating.py: funnel tab removed; "funnel" maps to "billing".
- App/app/host_i18n.py, App/app/host_vi_i18n.py: billing.admin.reports added (en, cs, vi); cs billing.admin.funnel.title fixed; unused bare `funnel.title` removed (en, cs, vi).
- App/tests/test_admin_funnel.py, test_admin_section_tabs.py, test_billing_admin.py: updated to the new page; one order and closed-details test added.

## Tests
- `.venv/bin/python -m pytest tests/test_admin_funnel.py tests/test_billing_admin.py tests/test_admin_section_tabs.py -q --tb=short`: `19 passed in 2.95s`
- Earlier, `tests/test_billing_*.py` with the three files: `175 passed in 13.37s`
- `UBYHOST_BROWSER_EXECUTABLE=... tests/test_design_guardrails_browser.py -q -rs`: `11 passed in 69.30s`, 0 skipped
- `python3 scripts/context_lint.py`: `context lint: OK`

## Open
- 390 px screenshot of /admin/fakturace not taken (rule 7).
- Brief file docs/tasks/0481-admin-money-page.md is not on this branch; its Status line could not be set here.
