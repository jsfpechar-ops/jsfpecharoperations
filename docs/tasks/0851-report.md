# 0851 report

Status: review

## Files changed
- App/tests/test_design_fees.py: list primary check uses the v2 Yes button (`<button class="btn" type="submit">`); legacy btn/pill check exempts stay_fees.html (v2, 0792/0794).
- App/tests/test_design_invoices.py: header New invoice check uses `<a class="btn" href="/invoices/new">`; btn check exempts invoices.html (v2, 0792/0794).
- App/app/templates/stay_fees.html: one closed `details.ui-how[data-how="stay_fees"]` added under the h1 (same markup as invoices.html), links to /guide#stay_fee.
- test_stay_fee_pay_steps.py needed no change: it already asserts `class="card fee-pay"`.

## Command
`.venv/bin/python -m pytest tests/test_design_fees.py tests/test_design_invoices.py tests/test_page_help_0277.py tests/test_stay_fee_pay_steps.py -q --tb=short 2>&1 | tail -30`
Result: `12 passed in 3.03s` (0 failed, 0 skipped). Before the fix: 7 failed, 5 passed.

## §7 acceptance
- [x] The command: 0 failed.

## Deviations
- Brief §2 expected a `fee-pay` selector change; it was already done in the checkout.
- No commit, no push, no worktree. A temporary probe file in the scratchpad was removed.

## Questions
- None.

## Owner steps left
- Commit (orchestrator) and run the browser and geometry tests for stay_fees if the template change needs a screenshot (rule 7).
