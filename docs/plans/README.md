# Implementation plans (stay fee + invoices)

These plans describe features. The stay fee is **on hold**; the invoice builder is **built**.

| File | What |
|---|---|
| `PLAN_POPLATEK_Z_POBYTU.md` | Local stay fee: host rate per property, one total + QR per stay, host marks paid. **ON HOLD — pulled back, not in the code.** |
| `PLAN_GUEST_INVOICE_FEATURE.md` | **Standalone, host-only invoice builder** (free-form, unlimited line items, VAT 0/12/21 %). Not connected to a stay; no guest access. The filename is historical. **Built.** |
| `invoice-design/invoice_pdf_reference.py` | The invoice PDF renderer (copied to `App/app/invoice_pdf.py`) |
| `invoice-design/sample-*.pdf`, `*.png` | What the invoices look like |
| `PLAN_TICKET_WALLET_V2.md` | **Guest registration, Ticket Wallet** (chosen 29 Sep 2026): every screen is a ticket with one coral button in the tear-off stub, a step tracker on the form, and a boarding pass per guest at the end. The handoff (foundation patch, full reference patch, real-app screenshots) is in `ticket-wallet/`. **Built.** |

## Session decisions (2026-09-26)

- **Stay fee** — the owner pulled the feature back; it is not in the app. When it returns it must default **off** (`stay_fee_policy` `off`, rate `0`).
- **Invoices** — **standalone and host-only.** The host builds a custom invoice at **Invoices → New invoice**: any number of line items (description, quantity, unit, unit price, VAT 0/12/21 %), full customer/supplier data. **Not tied to a stay.** No guest access; the host may e-mail a signed download link.
- **Process** — **every change goes through a pull request the owner reviews and merges.** Production deploy is **manual only** (`Actions → Deploy production → Run workflow`, `force_confirm=DEPLOY`); a push or merge to `main` does **not** deploy.
- **Code notes** — `validation.ico_ok()` exists; tokens use `config.secret_key()` and build serializers lazily.

Fonts used by the PDFs are committed at `App/app/static/fonts/` (DejaVu Sans; licence alongside).

`docs/POPLATEK_Z_POBYTU.md` is the older sketch; the owner merges it by hand. Do not edit it.

## How to run this with an agent

Give the agent **one step at a time**. Every change: push a feature branch, open a
pull request, run `.venv/bin/python -m pytest tests -q` from `App/`, and stop with
the tests green. Never commit to `main` directly.
