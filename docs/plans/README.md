# Implementation plans (stay fee + invoices)

These plans describe features that are now **implemented**. Use them as the spec of record.

| File | What |
|---|---|
| `PLAN_POPLATEK_Z_POBYTU.md` | Local stay fee: host rate per property, one total + QR per stay, host marks paid. **Off by default.** |
| `PLAN_GUEST_INVOICE_FEATURE.md` | **Standalone, host-only invoice builder** (free-form, unlimited line items, VAT 0/12/21 %). Not connected to a stay; no guest access. The filename is historical. |
| `invoice-design/invoice_pdf_reference.py` | The invoice PDF renderer (copied to `App/app/invoice_pdf.py`) |
| `invoice-design/sample-*.pdf`, `*.png` | What the invoices look like |

## Session decisions (2026-09-26)

- **Stay fee** — small, optional, per-property, **off by default** (`stay_fee_policy` defaults `off`, rate `0`). No filing, no payment processing; the host marks "paid". The QR is a SPAYD bank-transfer QR, **not** a payment link.
- **Invoices** — **standalone and host-only.** The host builds a custom invoice at **Invoices → New invoice**: any number of line items (description, quantity, unit, unit price, VAT 0/12/21 %), full customer/supplier data. **Not tied to a stay.** No guest access (no request flow, no public page); the host may e-mail a signed download link.
- **UX bar** — clear and simple: sensible defaults, no jargon, no clutter. Unused features render nothing.
- **Staging first** — deploy to `ubyhost-staging`. Note: `main` auto-deploys to production (Lightsail) via `deploy-production.yml`; the `staging` branch mirrors `main` for manual Render staging deploys.
- **Code notes** — `validation.age_on()` and `validation.ico_ok()` exist; tokens use `config.secret_key()`.

Fonts used by the PDFs are committed at `App/app/static/fonts/` (DejaVu Sans; licence alongside).

`docs/POPLATEK_Z_POBYTU.md` is the older sketch; the owner merges it by hand. Do not edit it.

## How to run this with an agent

Give the agent **one step at a time**, and make it run `.venv/bin/python -m pytest tests -q` from `App/`, stopping when the step's "Done when" is met and the tests are green. If the repo doesn't match the plan, it should stop and report instead of guessing.
