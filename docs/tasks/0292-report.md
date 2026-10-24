# 0292 report: stay fee list one step at a time

Status: review

## Files changed
- App/app/routes/stay_fees.py (step 1: step per card, fee_step_url)
- App/app/templates/stay_fees.html (step 2: pay loop replaced, pay_btn removed)
- App/app/host_i18n.py, App/app/host_vi_i18n.py (step 3: new keys, step2/step3 values)
- App/app/static/host2.css (step 4 append; step 6 width 7rem; entities name rule)
- App/app/templates/base.html (host2 cache key)
- App/tests/static_versions.json (regenerated with --write)
- App/tests/test_stay_fee_pay_steps.py, App/tests/test_stay_fee_pay_steps_browser.py (step 5)
- App/tests/test_design_fees.py (not named in brief, see Deviations)

## Commands
- `.venv/bin/python -m pytest tests/test_stay_fee*.py tests/test_design_fees.py tests/test_static_versions.py tests/test_design_guardrails_browser.py tests/test_host_i18n*.py tests/test_0285_rows_browser.py -q --tb=short -rfs 2>&1 | tail -30`
  last line: `174 passed, 2 warnings in 47.96s`. No skipped lines.
- Earlier run had 3 failures (static manifest, 0285 entities rows at 1280 px, design_fees primary assertion). Each fixed as listed below.

## Section 7
- [x] Unconfirmed card: step 1 current, figures, Yes (primary) + Edit (test 1, browser test).
- [x] Confirmed card: step 2 Download + Next; fee_step=3 shows QR, send line, Open datová schránka (test 2).
- [x] One primary per card; EN/CS/VI strings present (browser test, i18n tests).
- [x] Commands run; failures listed.
Screenshots not taken (orchestrator).

## Deviations
- Cache key: brief says `?v=20261024-0292`. The manifest refused a second CSS edit under the same key, so base.html uses `20261024-0292b`.
- App/tests/test_design_fees.py line 14 asserted the list has no `ui-btn ui-btn-primary`. The brief makes Yes a primary, so it now asserts exactly one. Not named in brief; reviewer to confirm.
- `.lc-entities` name links also failed at 1280 px. Added `.host-workspace .lc-entities tbody td.col-name .row-primary-link { max-width: calc(100% - 7rem); }` inside the 950px block, after the `+ .row-open` line.
- New CSS uses `3px` and `1.5rem` as the brief gives them. Not checked against any px lint.
- Old keys (lede, locked, confirmed_help, confirm_why) and the 0203 rules are left in place; i18n tests pass.
- Tool-call budget: this run went past the 25-call checkpoint (about 34 calls) while fixing test failures. No steps are left undone.
- No PR opened: this session may not push.

## Questions
- Confirm the test_design_fees.py change and the 0292b cache key.

## Owner steps left
- None.
