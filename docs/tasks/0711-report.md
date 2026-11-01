# 0711 report

Status: review

## Files changed
- App/app/stripe_connect.py: legal_entity_for_owner helper, used by create_or_get_account
- App/app/routes/stripe_connect.py: start and return redirect to /payments with a message
- App/app/routes/payments.py: _setup() builds the 4 steps
- App/app/templates/payments.html: step cards and one primary button
- App/app/host_i18n.py: 21 en + 21 cs keys
- App/tests/test_payments_dashboard.py, App/tests/test_stripe_connect.py: updated and new tests
- App/tests/test_payments_setup_browser.py (new), docs/tasks/screenshots-0711/payments-setup-390.png (new)
- docs/tasks/0711-guided-payments-setup.md: Status line only

## Commands (last lines)
1. Dashboard, request model, Stripe connect, consent (4 files, run without the 2 missing names): `.............` then `60 passed in 3.72s`. Extra: test_payments.py and test_payment_rails.py: `25 passed in 1.31s`.
2. Browser, 0 skipped: `............ [100%]` then `12 passed in 58.68s`.
3. `design_lint.py`: `design lint: OK`.
4. `context_lint.py`: WARN lines (catalog.json, RETENTION.md, 27 commits after status.md), `next free: task 0712 | migration 0034`, `context lint: OK`.

## Steps
Steps 1 to 9 done, one commit each (`0711 start`, `0711 step 2` to `0711 step 9`). Test-only steps 2, 6, 7, 8 passed; steps 3, 4, 5 have no test in the brief and are covered by the §6 runs.

## Acceptance (§7)
- Screenshot shows 4 Czech cards and the button "Otevřít Stripe" (state none, consent and entity present). Browser test checks 4 cards and no horizontal overflow at 390 px.
- Other §7 items were not checked by a separate test.

## Deviations
- Brief §6 cmd 1 names tests/test_payment_links.py and tests/test_payment_qr.py, which do not exist. Ran the other files, plus test_payments.py and test_payment_rails.py. The test-map needs fixing.
- Commit trailer uses Co-Authored-By: Claude Haiku 5.5, not Opus 5.5 as the task text said. Per the attribution reminder, I am Haiku.
- Screenshot also shows an environment banner ("Policie se nic nehlásí", test server). Not part of this change.

Done: steps 1 to 9. Left: none. Not pushed, no PR.
