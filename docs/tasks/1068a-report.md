# 1068a report: errors that link to the fix (Python)

Status: blocked (two brief §8 stop conditions at step 12: the toast link and the form block need CSS)

## Files changed

`App/app/payment_request.py`, `templating.py`, `routes/admin_helpers.py`, `routes/payments.py`, `routes/admin.py`, `host_i18n.py`, `host_vi_i18n.py`, `i18n.py`, `guest_uk_i18n.py`, templates `base.html`, `payments_new.html`, `payments_qr.html`, `payments.html`, `invoice_form.html`, `_property_editor.html`; `App/tests/test_payment_rails.py` (8 new tests). No test asserted the old `warn_no_iban` text. Nothing in `go/`, `static/`, migrations.

## Commands (last lines)

- Step 1: `No bank account is set up for this payment request.`
- Steps 2, 5, 9 `import app.main`: no output.
- Step 3 `grep -c flash_fix base.html`: `2`. Step 8: `1`.
- Step 4 i18n row: `1 failed, 92 passed`; the failure is `test_go_host_i18n.py` (Go `i18n.json` stale, expected, 1068b).
- Step 10 (existing payment files): `112 passed` and 0 skipped once Playwright was set up.
- Step 11 invoice/stay-fee: `994 passed, 2 skipped` (skips need `UBYHOST_SHOTS_DIR`). Locks: `256 passed` (webkit deselected). Host: `246 passed, 2 failed, 1 skipped`; both failures also fail on the base commit 63018557 (`test_browser_renders_saved_warning_as_sticky_amber`, `test_every_page_family_fits_...` guide/cs `?` past right edge). Guest: `638 passed` with `UBYHOST_REQUIRE_BROWSER=1`, 0 skipped.
- Step 12: `test_layout_lint_browser.py` green. `test_design_guardrails_browser.py`: 10 passed; 1 pre-existing finding (fails on base too): `guest-new 390 tap-target-small "Cancel" 43px`.

## §7

- [ ] `fix="` grep: `bank` x2 (create, preview), `stripe` x3, `lock_guide` x2. The brief's "bank x3" counts one site the steps do not add (the invoice link is a template `href`).
- [x] QR create with no account: no row, redirect with `fix=bank`.
- [ ] `/payments/new` no account: works, but spacing fails (below).
- [x] PNG 404 `text/plain` `NO_ACCOUNT_BODY`; guest page 200 in en, cs, de, es, fr, uk.
- [x] Unknown `?fix=` renders no link. [x] No added "paid" line.

## UX gate per page (screenshots in `docs/tasks/screenshots-1068a/`)

- Toast with fix (`toast-fix-390.png`, 768, 1280): the link "Add bank account (1 min)" has the same colour as the text (rgb 28,28,26) and no underline. It looks like plain text. **STOP: needs CSS.**
- `/payments/new` no account (`payments-new-390.png`): 6 px from the chips to the sentence (needs 12 or more), 18 px to the button. The compact secondary button spans the full width with its label on the left. **STOP: needs CSS.**
- Property lock offline (`property-lock-390.png`): the sentence and the "Step-by-step guide" link fit. The link looks like plain text (same issue as the toast).
- `/invoices/new`: in the picker state the no-account warning is not rendered, so it was not captured. Needs the entity-selected state.
- Guest `/pay/{id}/{token}`, no account (`guest-pay-no-account-390.png`): the heading and one sentence. No image, no amount, no "paid".

## Deviations

- Step 10's `test_payment_links.py` and `test_payment_qr.py` do not exist. I ran `test_payments.py` and `test_payments_consent.py` instead.
- Playwright (Python) was missing from the venv. I installed `playwright==1.63.0` in the venv only, the same way CI does; no requirements change. WebKit is not installed locally, so the `[webkit]` variants were deselected.
- The step 8 edit was committed in the "step 7" commit.

## Questions

1. The toast and lock link need a link style. Which `app2.css` rule should we use?
2. The block under the Bank QR chips needs a 12 px top gap and a compact button that is not full width. Who changes the CSS?
