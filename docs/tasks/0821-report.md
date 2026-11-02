# 0821 report

Status: review

## Files changed
- App/app/billing.py, go/internal/billing/quote.go: new add-on prices (step 1)
- go/internal/billing/testdata/quote_fixtures.json: regenerated with App/scripts/billing_fixtures.py (step 2)
- go/internal/billing/snapshot_test.go: account 2 expected 2036 / 1831 / 1831 (step 2)
- App/app/landing_i18n.py: anchor copy EN and CS replaced, pricing.addon.ttlock.body removed (step 3)
- App/tests/test_billing_core.py, App/tests/test_billing_invoices.py, App/tests/test_0412_pricing_browser.py: expected amounts only (step 4)
- docs/context/decisions.md: one line (step 5)
- docs/tasks/screenshots-0821/cenik-390.png: /cenik, English, 390 px, default state (1 apartment, yearly)
- docs/tasks/0821-report.md: this file

## Expected-amount arithmetic (slabs per apartment: 1-4 / 5-9 / 10+)
- Max monthly extra: n=1 59; n=5 4x59+45=281 (715+281=996); n=12 4x59+5x45+3x29=548 (1488+548=2036); n=20 4x59+5x45+11x29=780 (2280+780=3060).
- Max yearly extra: n=1 570 (1760); n=3 1710 (5280); n=5 2280+430=2710 (8420); n=12 2280+2150+840=5270 (17150); n=20 2280+2150+3080=7510 (25710).
- TTLock yearly test: 470/12 = 39.2 -> carry 39 (was 40). Upgrade proration: 570 x 6/12 = 285 (was 359).
- Add-on test: 2 apartments x 49 = 98, 298+98 = 396.

## Commands (last lines)
1. `pytest tests/test_billing_*.py tests/test_signup_selection.py` (App): `73 passed in 5.09s`
2. `pytest` browser set with UBYHOST_BROWSER_EXECUTABLE: `27 passed in 88.91s (0:01:28)`, no skipped lines
3. `go test ./internal/billing/`: `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing (cached)` (uncached run at step 2: `0.015s`)
4. `grep -rn "50 000\|50,000" App/app/landing_i18n.py`: no output
5. `python3 scripts/context_lint.py`: `context lint: OK` (WARN lines are pre-existing: catalog.json, RETENTION.md, status.md is 6 commits behind)

## Section 7 acceptance
- /cenik figures for 1 apartment yearly (99 / 147 / +39) and monthly Max 208: asserted by the tests above. Monthly Standard + TTLock 198 (149+49) is covered by the browser loop, not by a separate assertion.
- Screenshot saved. I did not look at the image myself.

## Deviations
- Step 4 has two commits labelled "0821 step 4" (billing tests, browser tests).
- The browser test writes screenshots to a default folder and the onboarding/signup tests write to UBYPORT shots dir when env is set. I set UBYHOST_SHOTS_DIR to docs/tasks/screenshots-0821 for the run, then deleted every file there except cenik-390.png. The stray default folder docs/tasks/screenshots-pricing-panel was created by my first run and removed.
- Commit trailer uses Claude Opus 5.5 as the brief request said.
- Done: steps 1 to 5 and the report. Nothing pushed, no PR.

## Owner steps left
1. Before deploy, run the psql query in the brief (Owner steps). Standard monthly TTLock rows go from 40 to 49 Kr: the Terms need 30 days' notice, so tell the thread first.
2. Review and merge through scripts/merge-pr-on-green.sh. Deploy is manual.
