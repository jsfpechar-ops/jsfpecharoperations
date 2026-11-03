# 0831 Group I report (executor)

Status: blocked

## Files changed
- docs/design/catalog.json: added 11 classes (stays-title-row, stays-pills, police-deadline-row, e-page, picker-links, settings-help-line, settings-toggle-form, f1-tip, page-help, page-help-btn, page-help-body).
- No other file changed. No commit, no push.

## Commands and results
- `python3 scripts/design_lint.py`: OK (was FAIL with 8 uncataloged classes).
- `App/tests/test_payments_consent.py`: all pass (no edit needed; the file already monkeypatches STRIPE_MODE in its fixtures).
- `App/tests/test_billing*.py`: 164 passed, 0 skipped.
- `App/tests/test_design_shell.py` + `test_design_shell_browser.py`: 17 passed, 8 failed, 0 skipped.

## Item status
1. test_payments_consent: passes as is. No change.
2. billing_plan.html: lines 9-10 already turn the int from `billing_order.apartments()` (passed as `apartments`) into `apartment_count` and a list for the shell. Billing tests pass. No change.
3. Old-shell tests on /payments: BLOCKED. payments.html now sets `v2 = true`, so the /payments checks fail. The failures are not only a wrong page: `/payments` renders without `class="ui-sidebar" id="app-sidebar"`, which the v2 tests expect, and `_shell_v2.html` has no `ui-sidebar` class. Fixing this means changing shell markup, which is outside Group I. Failing tests:
   - test_design_shell.py::test_signed_in_pages_carry_the_v2_shell_and_not_the_drawer
   - test_design_shell.py::test_the_sidebar_lists_every_destination_with_a_lucide_icon
   - test_design_shell_browser.py::test_desktop_sidebar_is_240_wide_and_main_starts_after_it
   - test_design_shell_browser.py::test_phone_tab_bar_is_fixed_at_the_bottom_with_five_44px_tabs
   - test_design_shell_browser.py::test_collapsed_rail_expands_again_with_the_same_button
   - test_design_shell_browser.py::test_more_preserves_each_page_kind_and_sheet_links_work[/payments?lang=en-390-chromium] and [-820-chromium]
   - test_design_shell_browser.py::test_more_keeps_settings_fallback_without_javascript[chromium]
   Owner decision needed: is the v2 sidebar supposed to exist on /payments (shell regression), or should these tests move to a non-v2 host page? Non-v2 host pages found: invoices.html, stay_fees.html, housebook.html, submissions.html.
4. design_lint: done (see above).
5. Tests run: see above.

## Deviations
Done: steps 1, 2, 4, 5. Step 3 blocked (shell regression, needs owner decision).

## Owner steps left
- Decide the item-3 question above, then re-run `App/.venv/bin/python -m pytest tests/test_design_shell.py tests/test_design_shell_browser.py -q --tb=short -rs`.
