# 0394 report

Status: blocked
Executor: Haiku 5.5 | Branch: claude/project-thread-kyxdtg

## Files changed (commits 0394 step 1 to step 6)

- App/app/vat_register.py (new): MFČR VAT register SOAP lookup, DIČ digits only, 24 h cache, stdlib XML
- App/app/routes/invoices.py: lookup fills account, BIC and VAT status; `_fill_register_account`
- App/app/routes/admin.py: `use_register_account` also runs the lookup
- App/app/templates/_entity_business_fields.html: `register_messages` source_key; `register_lookup_saved(ico, invoice)` with account buttons and alerts
- App/app/templates/entities.html: one macro call
- App/app/static/host.css: `.register-accounts` rule
- App/app/templates/base.html: `host.css?v=20261025-0394`
- App/app/host_i18n.py, App/app/host_vi_i18n.py: new `ares.field.bank_account`, `ares.field.bic`, `vat_register.*` keys

## Commands run

- `cd App && .venv/bin/python -c "from app import vat_register; print(vat_register.dic_digits('CZ 12345678'))"` → `12345678`
- `cd App && .venv/bin/python -c "import app.routes.invoices"` → no output (ok)
- `cd App && .venv/bin/python -c "from app import host_i18n, host_vi_i18n"` → `ok`

## Brief §7 acceptance

Nothing ticked. Steps 7 and 8 and all §6 tests were not run.

## Deviations

Done: steps 1 to 6. Left: steps 7 to 8.
The executor call budget (25) was reached, so the executor stopped here.

## Questions

- Security hook warned on `xml.etree.ElementTree` in `vat_register.py`. The brief requires stdlib (no new dependency). `defusedxml` would need an owner decision line in docs/context/decisions.md. Owner to decide.

## Owner steps left

- Run step 7 (`App/tests/test_vat_register.py`) and step 8 (decisions line), then the §6 test commands.
