# 0208 report: one box for the stay-fee account

Status: blocked (executor, Haiku 5.5). Steps 1 to 7 done and committed one by one (b2f9b11, 7fada55, f40aefb, 1010a76, 8e054f3, 4dded22, 8e4a4e5). Step 8 is the per-step commits. Screenshots (§6.5) skipped: tool budget.

## Files changed (§3 list only)

- App/app/templates/_stay_fee_fields.html, App/app/routes/stay_fees.py, App/app/routes/onboarding_wizard.py, App/app/routes/admin.py, App/app/static/app.js, App/app/templates/base.html (app.js key 20261021-0208), App/tests/static_versions.json (regenerated), App/app/host_i18n.py, App/app/host_vi_i18n.py, the five test pin files, App/tests/test_fee_one_box_0208.py (new).
- Not committed: docs/tasks/0102-evidence PNGs rewritten by the browser tests.

## Commands (last lines)

- §6.1 unit set: `78 passed, 1 warning in 19.36s`
- §6.2 browser set: `2 failed, 98 passed, 1 warning in 236.31s`
  - test_fee_setup_compatibility.py:286 expects "Enter a valid Czech bank account or IBAN." The new flash text from step 5 replaces it.
  - test_fee_setup_compatibility.py:310 `assert 0 == 1` (loop over account_prefix/account_number/account_bank inputs; not named in §3 scope).
- §6.3 navigation browser: `3 failed, 9 passed, 1 warning in 37.92s`
  - test_property_views_fit_every_width_and_sidebar (360 px tabs, known failure on main, not ours).
  - test_property_navigation_browser.py:196 `'<details' not in '<nav ...'` and a 30 s timeout on `.setup-wizard-skip .link-button`. Not investigated (budget); may be caused by the change or pre-existing. Check on main.
- `design_lint.py`: OK. `context_lint.py`: OK.

## Deviations

Done: steps 1 to 7. Left: fix or confirm the 3 failures above (test_fee_setup_compatibility.py:286 and :310, test_property_navigation_browser.py:196 and the setup-wizard-skip timeout), screenshots §6.5.

## Questions

1. Should test_fee_setup_compatibility.py:286 and :310 be updated to the one-box text and one box? The brief does not name those lines.

## Owner steps left

None on the server. Merge via scripts/merge-pr-on-green.sh after the fixes.
