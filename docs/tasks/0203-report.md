# 0203 report

Status: blocked
Branch: claude/project-thread-graf3i (not pushed, no PR)

## Files changed

- App/app/routes/stay_fees.py: step 1, commit 5469478.
- App/app/templates/stay_fees.html: step 2, commit 705b287.
- App/app/static/host2.css, App/app/templates/base.html, App/tests/static_versions.json: step 3, commit 36e1c0c.
- App/app/host_i18n.py, App/app/host_vi_i18n.py: step 4, commit 72fa3ef.
- docs/design/catalog.json, docs/design/pages/stay-fees.md: step 5, commit cbe4b94 (9 class names added, page line added, 29 lines).
- App/tests/test_design_fees.py (6a), App/tests/test_stay_fee_pay_steps.py (6b, new), App/tests/test_stay_fee_pay_steps_browser.py (6c, new): step 6, commit 99c1f55. The browser test fails (see below).
- docs/tasks/0203-report.md: this report.

## Commands

Step 6, command 1: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_invoice_*.py tests/test_stay_fee*.py tests/test_design_fees.py tests/test_host_fee_navigation.py -q --tb=short -x 2>&1 | tail -30`
- Last 5 lines:
```
=========================== short test summary info ============================
FAILED tests/test_stay_fee_pay_steps_browser.py::test_pay_steps_fit_every_width_and_language
ERROR tests/test_stay_fee_pay_steps_browser.py::test_pay_steps_fit_every_width_and_language
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 2 failures !!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 197 passed, 1 skipped, 1 warning, 1 error in 29.90s
```
- Same set without the browser test (`--deselect` of that one test): `223 passed, 1 skipped, 1 deselected, 1 warning in 40.95s`. The skip is tests/test_invoice_autofill.py:300 "set UBYHOST_SHOTS_DIR to capture acceptance screenshots" (existing test, env only).

Step 6, command 2: not run (stopped at command 1 failure).

Lint: `python3 scripts/context_lint.py` last line: `context lint: OK`. `python3 scripts/design_lint.py` last line: `design lint: OK`.

## Failure text (browser test, 6c)

Run alone: `test_pay_steps_fit_every_width_and_language` fails with
`AssertionError: [(('before', 'en', 390), 'more than one primary'), (('before', 'en', 1280), 'more than one primary'), ...]`
Every width and language fails in the "before" state. The check counts every `.ui-btn-primary`. The page already has the filter apply button with `ui-btn-primary filter-apply` (asserted in test_design_fees.py), and step 1 is primary when one property is shown (`pay_btn`, stay_fees.html line 13). So one property gives two primaries. No sideways scroll and no missing steps were reported.
The teardown of the module-scoped `acc` fixture also errors: `sqlite3.IntegrityError: FOREIGN KEY constraint failed` (seen when the browser file runs alone). Not investigated.

## Deviations

- Done: steps 1 to 5 committed, step 6 written and committed. Left: step 6 browser test (fails), step 6 command 2, the browser screenshots (not taken), and the step 7 acceptance tick.
- The browser test was not loosened or skipped. The 6c check and the page are unchanged.

## Questions

- Owner decision: which primary rule wins? Options: (a) step 1 is always secondary on this page; (b) the filter apply button becomes secondary; (c) the 6c check counts only pay-step primaries. The brief's §7 says at most one primary, so (c) would change the rule the brief sets. I did not pick one.
- Teardown FK error in the `acc` fixture: is it known?

## Owner steps left

- Decide the primary rule above, then the executor (or you) reruns step 6 command 1 and command 2.
