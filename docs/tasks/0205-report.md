# 0205 report

Status: blocked
Done: steps 1 to 15 (one commit each, "0205 step k"). Not done: §7 acceptance, screenshots, and the two copy-pin test failures below.

## Files changed
Per brief §3: `_stay_fee_fields.html`, `_account_parts.html`, `setup_wizard/stay_fee.html`, `setup_wizard/police.html`, `routes/stay_fees.py`, `static/host.js`, `base.html` (host.js key 0205), `host_i18n.py`, `host_vi_i18n.py`, `tests/test_reporting_help_0097.py`, `tests/test_fee_setup_compatibility.py`, `tests/test_host_ux_acceptance.py`, `tests/test_property_navigation_browser.py`, `tests/test_fee_form_partial.py` (new), `tests/static_versions.json` (regenerated, 32 files).

## Commands (last lines)
1. §6.1 without test_host_i18n.py, -x: stopped at `test_reporting_help_0097.py::test_police_fields_have_plain_help_with_the_letter_line`. Without -x: 2 failed, 85 passed.
2. `test_host_i18n.py` (known): 3 failed, 11 passed.
3. §6.2 `test_stay_fee*.py test_invoice_*.py`: 214 passed, 1 skipped (not traced).
4. §6.3 browser, -rs: 5 failed, 106 passed, no skips reported. Captured failures: `test_property_navigation_browser.py:578` (360 px settings tabs overflow: Reporting & fees, Door lock, Automation); `test_onboarding_wizard_browser.py:1011` (police step shows `.err-text` after "Demo stay deleted"). The other 3 names were not captured.

## Failures (copy pins the brief did not anticipate)
- `test_reporting_help_0097.py`: asserts the literal "Zkratka ubytovacího zařízení". Step 8 Czech `mark_hint` (verbatim from brief) has the inflected "Zkratku". Fix needs a decision.
- `test_smart_locks_page.py::test_after_connecting_three_essentials_and_every_tap_in_the_guide`: asserts old TTLock text "Open your lock in TTLock.", replaced by step 8. This file is not in brief §3.

## Deviations
- Steps 10 to 13 matched the anchors as substrings that start mid-line, so the leading indentation is untouched. All anchors matched once.
- Step 14: `fee_form_values` returns `30` as an int, so no comparison change was needed.
- Step 9: the `smart_locks.check` button text is "Kiểm tra kết nối", same as the brief, so `essential3` was not changed.
- Browser run wrote evidence PNGs under `docs/tasks/0102-evidence/`. Removed the untracked ones and restored tracked ones. Nothing from that run is committed.
- `docs/tasks/0207-design-lint-for-onboarding-fixes.md` was already untracked before this run. Not touched.

## Questions
1. Czech police help: reword the copy to the literal nominative phrase, or change the test to match the inflected form?
2. Update the `test_smart_locks_page` pin to the new essential1 text? (Likely yes.)
3. The 5 browser failures: rerun with `-rf` and check whether they also fail on main.

## Owner steps left
None until the questions are answered. Then merge and deploy as usual; new cache keys ship with it.
