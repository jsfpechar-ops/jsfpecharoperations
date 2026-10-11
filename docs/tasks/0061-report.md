# 0061 report: Invoice autofill

Status: review

## Worktree

`../uby-0061` could not be created (permission denied on `/`). Used `/workspace/uby-0061` with branch `task/0061-invoice-autofill` and linked `App/.venv` to the main checkout venv.

## Files

| Path | Change |
|---|---|
| `App/app/data/bank_codes.csv` | ČNB bank codes (UTF-8, source URL in header) |
| `App/app/payments.py` | `bic_for_account()` |
| `App/app/routes/invoices.py` | Guest fill button, last-price placeholder, BIC on settings save |
| `App/app/templates/invoice_form.html` | Fill button, price placeholder |
| `App/app/templates/invoice_settings.html` | BIC “filled from bank code” hint |
| `App/app/host_i18n.py` | `invoice.fill_guest.*`, `invoice.price_hint` (EN + CS) |
| `docs/privacy/ROPA.md` | Processing line for host-requested copy to invoice |
| `App/tests/test_invoice_autofill.py` | Unit + browser screenshot test |
| `App/tests/test_invoice_settings.py` | Expect auto BIC on `0800` save |
| `docs/tasks/0061-screenshots/` | Before/after screenshots (§7) |

## Tests

```text
cd App && .venv/bin/python -m pytest tests/test_invoice_autofill.py tests/test_invoice_settings.py tests/test_invoice_stay_browser.py -q
18 passed, 1 skipped, 1 warning in 8.18s
```

Full suite: 7 browser geometry failures on `origin/main` without this branch (unchanged host-wide tests); invoice autofill and settings pass.

## Screenshots

Captured at 360, 390, and 1280 px (`UBYHOST_SHOTS_DIR=docs/tasks/0061-screenshots`):

- `invoice-fill-before-{360,390,1280}.png`
- `invoice-fill-after-{360,390,1280}.png`

## ROPA line

Section A (processor record), **Processing operations**:

> on the host's button press, check-in name and address may be copied into that stay's invoice buyer fields
