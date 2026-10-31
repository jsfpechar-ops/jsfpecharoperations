# 0461: Remove the unused VAT-register module
Status: todo
Depends on: none | Base commit: main | Branch: task/0461-remove-dead-vat-register
Executor: Haiku 5.5 | Fits one session: 20 tool calls, 40k tokens
## 1. Objective
Delete dead code: `App/app/vat_register.py` is imported by no module (only i18n strings mention it). Owner rule 2026-10-31: no dead code, no extras. ARES (`App/app/ares.py`) is live (billing and invoices routes) and stays.
## 2. Context
Plan v3.0 called both ARES and VAT dead; only VAT is. Plan: [migration-plan-v4](../plans/postgresql/migration-plan-v4.md).
## 3. Files
`App/app/vat_register.py`, `App/tests/test_vat_register.py`, `vat_register.*` keys in `App/app/i18n.py`, `host_i18n.py`, `host_vi_i18n.py`, `guide_i18n.py`, `terms_i18n.py`, `public_guides.py`; any template using `t('vat_register.`.
## 4. Steps
1. Confirm: `grep -rn "vat_register" App/app App/tests --include=*.py --include=*.html | grep -v "vat_register\.\(source_note\|accounts\|use\|needs_dic\|unreliable\)"` returns only the module and its test. If any route, template or module imports or calls it, stop (section 8).
2. Delete the module and its test.
3. Delete the `vat_register.*` i18n keys in every language file and any template line that renders them. If a template line also renders live content, remove only the VAT part.
4. Run the i18n and guide coverage test rows from the test-map (`grep -n i18n docs/context/test-map.md`).
## 5. Do not touch
`ares.py`, billing or invoice logic, any other i18n key.
## 6. Commands
`cd App && .venv/bin/python -m pytest <test-map i18n/guide rows> -q --tb=short -x 2>&1 | tail -30`; `.venv/bin/ruff check app tests --select F401,F821 2>&1 | tail -10`.
## 7. Acceptance
No `vat_register` string left in `App/`; tests pass; ruff clean.
## 8. Stop and ask
Stop if the module is reached through a dynamic import or a template; report the path.
## 9. Report
`docs/tasks/0461-report.md`: files deleted, lines removed per i18n file, test tail.
