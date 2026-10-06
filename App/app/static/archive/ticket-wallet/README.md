# Ticket Wallet (archived)

The **Arrival lane** guest UI is the active default again (`guest.css`,
`guest-enhancements.js`, templates under `templates/guest/`). Ticket Wallet v2 assets
live here so they can be revived without digging through git history.

## Files

| Path | Role |
|------|------|
| `guest-ticket.css` | Skin under `<body class="tw">` |
| `ticket.js` | Progressive enhancements (PIN cells, DOB boxes, country search, stepper, …) |
| `../templates/guest/archive/ticket-wallet/_ticket.html` | Jinja macros (route line, boarding passes) |
| `../templates/guest/archive/ticket-wallet/form.html` | Reference TW markup for tests |

## Re-enable Ticket Wallet

1. Copy `guest-ticket.css` and `ticket.js` back to `App/app/static/`.
2. Copy `_ticket.html` to `App/app/templates/guest/`.
3. Restore TW templates from `templates/guest/archive/ticket-wallet/` or from commit history
   (see `docs/archive/plans/PLAN_TICKET_WALLET_V2.md`).
4. In `templates/guest/base.html`:
   - Add `<link rel="stylesheet" href="/static/guest-ticket.css?v=…">`
   - Set `<body class="tw">`
   - Add the `tw_route` / `tw_progress` blocks and `<script src="/static/ticket.js?v=…">`
5. Bump `?v=` cache keys on every touched CSS/JS file.
6. Run `pytest tests/test_ticket_wallet_v2.py tests/test_guest_browser_e2e.py -q`.
