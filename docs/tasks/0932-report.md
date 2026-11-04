# 0932 report: guest pay panel on the stay hub + form estimate + residence order

Status: review

## Done (working tree, not committed)
- Hub card gate in `App/app/routes/guest.py` `stay_overview()`: `remaining is None or remaining <= 0`.
- `_fee_estimate()` checked; unit tests `App/tests/test_stay_fee_estimate_0910.py` pass.
- Root cause of the failing card rows was the TEST, not app code: the seeded guest never went through claim mail, so the claim page rendered (its body says "Skip to the form", which is why it looked like the form). Fix: `monkeypatch.setattr(mail, "mail_enabled", lambda: False)` in the three fee tests (same switch as `test_0376_ai_gates.py`).
- Zero-fee row now asserts the hub rendered ("/new" not in URL, "Person 1" in body) before asserting the card is absent.
- Estimate row: Save button sits in a later wizard step, so the form is submitted with `requestSubmit()` (noValidate already set).
- CSS: `.g-fee dd, .g-fee-estimate dd` changed from `overflow-wrap: anywhere` to `break-word`. At 320 the variable symbol broke mid-number ("0000000 001"); now it stays whole, IBAN still wraps.
- Cache key bumped `guest.css?v=20261104-0932` to `...-0932b` in `app/templates/guest/base.html`; `tests/static_versions.json` rewritten with `--write`; `test_static_versions.py` 3 passed.

## Tests
- `UBYHOST_REQUIRE_BROWSER=1 ... tests/test_guest_browser_e2e.py -k fee`: 5 passed, 0 skipped. `-k estimate`: 1 passed.
- Full set (`test_guest_browser_e2e.py`, `test_host_geometry.py`, `test_layout_lint_browser.py`, `test_stay_fee_estimate_0910.py`): 38 passed, 0 skipped, 0 failed (run after the CSS change).

## Screenshots (docs/tasks/screenshots-0932/)
- hub-fee-card-320/390/768/1280.png: card with QR open; QR, IBAN, amount, VS, message readable. Hub 390 has one coral action (Continue, headcount step) above the card.
- hub-full-320/390/768/1280.png: full hub pages.
- iban-open-320.png: removed (capture picked the QR summary, not Bank transfer).
- revolut-open-390.png: Revolut row open, link text fits.
- form-estimate-390.png: "About 150 CZK for you (3 counted days x 50 CZK)". Clear.
- form-end-390.png: signature step with error (test submitted without signing); estimate sits further down.
- hub-cs-390.png: Czech, "Poplatek za pobyt" card, one coral button.
- hub-fee-zero-390.png: hub renders, no card.
- Not seen: Bank transfer row open at 320 (not captured).

## Not done / concerns
- Fee copy and translations not reviewed by a native speaker.
- Bank transfer row at 320 not re-shot.

## Owner steps
- None for this brief. Review and merge follow the normal PR gate.
