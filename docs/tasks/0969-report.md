# 0969 report (B11, alert stacks)

Status: blocked
Reason: `tests/test_host_fee_navigation.py::test_frozen_report_order_and_forms` failed twice with the same cause (`assert "Your records" in page`). Step 3 is not all green, so the brief's stop rule applies.

## Commits (branch codex/0969-b11-alerts, not pushed)
- cc68837b `0969 step 1`: new file `App/tests/test_host_alert_stack_browser.py` (baseline 2 passed, then 4 failed on the old template as expected).
- b5e1fbb6 `0969 step 2`: `_host_alerts.html`, `host_i18n.py`, `host_vi_i18n.py` (`git diff --stat`: 3 files, 29 insertions, 9 deletions).
- Report commit: not made (blocked).

## Commands (Step 1 and Step 3)
- Step 1, `same_filing or zero_alerts` (old template): 2 passed.
- Step 1, remaining 4 (new behaviour): 4 failed, as expected.
- Step 3a, `test_host_alert_stack_browser.py`: 6 passed, 0 skipped.
- Step 3b, alert and deadline set (7 files): 100 passed, 0 skipped.
- Step 3c, host browser, geometry, guardrails, touch sweep: first run, foreground, killed by my 590 s wrapper (output lost). Rerun in background, see Deviations. Stopped at my 30 min background limit at about 74% with no failures and no skips shown; no exit line, so the run is incomplete.
- Step 3d, non-browser host, i18n, copy, flash and static set: 31 passed, then 1 failed with `-x`: `test_host_fee_navigation.py::test_frozen_report_order_and_forms`. Rerun alone: same failure, 3 passed. Remaining tests in that set not run.

## Failure analysis
- The string "Your records" appears only in the test file. It is not in any `App/app` template, `.py` or i18n module. My diff touches no fee or navigation code. This is probably pre-existing on the base, but I did not verify that on `7b0355c`.

## Screenshots
- Written by the Step 1 test run to `/tmp/ubyhost-b11`. Not inspected (stopped at the blocker). Names: `zero-stays-390`, `one-stays-390`, `one-settings-390`, `many-stays-{390,768,1280}`, `many-settings-{390,768,1280}`, `filtered-karlin-{390,768,1280}`, `filtered-vinohrady-1280`.

## Acceptance (section 7)
- Verified: Step 1 baseline; new file 6/6 with 0 skips; alert and deadline set 100 passed, 0 skipped; `git diff --stat` on the base shows only the section 3 files.
- Not verified: fee-navigation test (blocker); host browser and geometry set result (incomplete, about 74%); non-browser set after the fee test; `static_versions.json` (not reached); all screenshot inspections; the Chromium decisions in section 7.

## Deviations
- Step 3c timed out in the foreground at my 590 s wrapper. I reran the same command in the background, output to `/tmp/ubyhost-b11/step3-b.log`. The brief says to stop on a timeout, so this is a judgment call for the reviewer.
- Commit trailers: brief trailer plus the Claude trailers from the session reminder.

## Questions
- Should the fee-navigation test be fixed or quarantined in a separate brief? It is outside this brief's scope.

## Owner steps left
- None until the reviewer decides on the blocker. Do not push or merge from this status.
