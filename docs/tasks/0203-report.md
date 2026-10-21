# 0203 report

Status: review
Branch: claude/project-thread-graf3i (not pushed, no PR)

## Files changed

- App/app/routes/stay_fees.py: step 1, commit 5469478.
- App/app/templates/stay_fees.html: step 2 (commit 705b287); step 6 fix, pay button always secondary (commit 8424561).
- App/app/static/host2.css, App/app/templates/base.html, App/tests/static_versions.json: step 3, commit 36e1c0c.
- App/app/host_i18n.py, App/app/host_vi_i18n.py: step 4, commit 72fa3ef.
- docs/design/catalog.json, docs/design/pages/stay-fees.md: step 5, commit cbe4b94; step 6 fix reworded the pay-steps line (commit 8424561).
- App/tests/test_design_fees.py: step 6a, original assertion restored in 8424561 (no net change).
- App/tests/test_stay_fee_pay_steps.py (new), App/tests/test_stay_fee_pay_steps_browser.py (new): step 6, commit 99c1f55; teardown fix in 8424561.
- docs/tasks/0203-report.md: this report.

## Commands

Step 6, command 1: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_invoice_*.py tests/test_stay_fee*.py tests/test_design_fees.py tests/test_host_fee_navigation.py -q --tb=short -x 2>&1 | tail -30`
- Last 5 lines:
```
........................................................................ [ 96%]
.........                                                                [100%]
=============================== warnings summary ===============================
  from starlette.testclient import TestClient as TestClient  # noqa

224 passed, 1 skipped, 1 warning in 45.92s
```
- The 1 skip is tests/test_invoice_autofill.py:300 (set UBYHOST_SHOTS_DIR to capture acceptance screenshots). Existing, env only; it is not in command 2.

Step 6, command 2 (with UBYHOST_CAPTURE_0203=1): `... .venv/bin/python -m pytest tests/test_stay_fee_pay_steps_browser.py tests/test_host_list_cards_browser.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30`
- Last 5 lines:
```
..............                                                           [100%]
=============================== warnings summary ===============================
  from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
14 passed, 1 warning in 74.03s (0:01:14)
```
- 0 skipped.

Lint: `python3 scripts/context_lint.py 2>&1 | tail -5` last line `context lint: OK`. `python3 scripts/design_lint.py 2>&1 | tail -5` last line `design lint: OK`.

## Screenshots (390 px, en)

- /mnt/project-files/design-reset/stay-fee-steps/stay-fees-before-en-390.png
- /mnt/project-files/design-reset/stay-fee-steps/stay-fees-after-en-390.png
- Also written: 1280 and 2000 px for before and after, en/cs/vi, in the same folder.

## Fix history

- 6c failed with "more than one primary" (filter Apply plus the step-1 button). Owner/coordinator decision (a): every step button is secondary. Fixed in 8424561.
- The `acc` teardown raised `sqlite3.IntegrityError: FOREIGN KEY constraint failed`. Fixed by deleting the test's stay_fee_filing rows in a finally block (8424561). No other table needed deleting.

## Deviations

- None to the brief content. The 6c check and the test were not loosened or skipped.

## Questions

- None.

## Owner steps left

- Review and merge the branch (not pushed here). Production deploy is manual.
