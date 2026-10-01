# Implementation plans

These plans describe features. The **guest-facing** stay fee is **on hold**; the invoice builder and the separate **host-only** stay-fee remittance tool are **built**.

**Host-app redesign:** [Implementation and Cursor handoff](host-app-redesign/README.md). Actual source changes, selected design, route coverage and verified tests.

| File | What |
|---|---|
| `stay-fee-remittance/PLAN_STAY_FEE_REMITTANCE.md` | **Built. Host-only remittance tool**: **optional opt-in, not onboarding**. Per-property rate + council details + úřad template, one-time fill, on-demand report PDF + §3g evidence CSV + QR Platba for the council. No guest input. |
| `stay-fee-remittance/*.html`, `*.jpg`, `*.png` | Design references for the remittance tool: report document (Praha 3 + Brno variants) and host fee list and detail screens. |
| `PLAN_POPLATEK_Z_POBYTU.md` | The **guest-facing** stay fee (show a total + QR to guests, host marks paid). **ON HOLD — pulled back, not in the code.** Distinct from the host remittance plan above. |
| `PLAN_GUEST_INVOICE_FEATURE.md` | **Standalone, host-only invoice builder** (free-form, unlimited line items, VAT 0/12/21 %). Not connected to a stay; no guest access. The filename is historical. **Built.** |
| `invoice-design/invoice_pdf_reference.py` | The invoice PDF renderer (copied to `App/app/invoice_pdf.py`) |
| `invoice-design/sample-*.pdf`, `*.png` | What the invoices look like |
| `PLAN_TICKET_WALLET_V2.md` | **Guest registration, Ticket Wallet** (chosen 29 Sep 2026): every screen is a ticket with one coral button in the tear-off stub, a step tracker on the form, and a boarding pass per guest at the end. The handoff (foundation patch, full reference patch, real-app screenshots) is in `ticket-wallet/`. **Built; v3 fixes in `ticket-wallet/V3_FIXES.md`, guarded by a browser test.** |

## Session decisions (2026-09-26)

- **Stay fee** — the guest-facing feature remains on hold. The host-only remittance tool is built and remains optional per property (rate `0` by default).
- **Invoices** — **standalone and host-only.** The host builds a custom invoice at **Invoices → New invoice**: any number of line items (description, quantity, unit, unit price, VAT 0/12/21 %), full customer/supplier data. **Not tied to a stay.** No guest access; the host may e-mail a signed download link.
- **Process** — **every change goes through a pull request the owner reviews and merges.** Production deploy is **manual only** (`Actions → Deploy production → Run workflow`, `force_confirm=DEPLOY`); a push or merge to `main` does **not** deploy.
- **Code notes** — `validation.ico_ok()` exists; tokens use `config.secret_key()` and build serializers lazily.

Fonts used by the PDFs are committed at `App/app/static/fonts/` (DejaVu Sans; licence alongside).

`docs/POPLATEK_Z_POBYTU.md` is the older sketch; the owner merges it by hand. Do not edit it.

## How to run this with an agent

Give the agent **one step at a time**. Every change: push a feature branch, open a
pull request, run `.venv/bin/python -m pytest tests -q` from `App/`, and stop with
the tests green. Never commit to `main` directly.
