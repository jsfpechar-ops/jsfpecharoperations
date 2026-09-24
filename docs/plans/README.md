# Implementation plans (stay fee + guest invoices)

These plans are for the implementing agent (Cursor or similar). They are specs, not shipped features.

| File | What |
|---|---|
| `PLAN_POPLATEK_Z_POBYTU.md` | Local stay fee: host rate per property, one total + QR per stay, host marks paid. **Build first.** |
| `PLAN_GUEST_INVOICE_FEATURE.md` | One-off invoices for completed stays. Phase 1 = host issues; Phase 2 = guest requests. **Build second.** |
| `invoice-design/invoice_pdf_reference.py` | The finished invoice PDF renderer; copy it to `App/app/invoice_pdf.py` (3 edits in its docstring) |
| `invoice-design/sample-*.pdf`, `*.png` | What the invoices must look like |

Fonts used by the PDFs are committed at `App/app/static/fonts/` (DejaVu Sans; licence alongside).

`docs/POPLATEK_Z_POBYTU.md` is the older sketch; the owner merges it by hand. Do not edit it.

## How to run this with an agent

Give the agent **one step at a time**. Paste this prompt, changing the plan name and step number:

> Read `docs/plans/PLAN_POPLATEK_Z_POBYTU.md` completely, especially §0 "Rules for the implementing agent" and §1.1 "UX walkthrough".
> Implement **only step N** of §16. Follow the plan exactly: names, strings, placement.
> Run `.venv/bin/python -m pytest tests -q` from `App/`. Stop when the step's "Done when" column is met and the tests are green.
> If the repo doesn't match the plan, stop and tell me instead of guessing.
> Commit with the message `stay-fee step N: <short title>`.

Review each step's diff before starting the next one.
