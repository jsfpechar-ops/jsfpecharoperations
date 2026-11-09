# qa-fix-errors-pay report

Status: review

Files: payments.py, payments_qr.html, main.py, admin.py, stay_fees.py; tests test_payment_rails, test_error_pages, test_host_unknown_ids (new), test_stay_fee_detail (one assertion to 404).

Commands:
- Step 1-3 set (payment_rails, unknown_ids, error_pages, test_host_*, stay_fee*, property_*, onboarding*): 1430 passed, 58 skipped (non-browser-required files, not the browser gate), 1 deselected.
- Browser gate `test_guest_browser_e2e.py test_host_geometry.py test_layout_lint_browser.py -rs`: 61 passed, 0 skipped.
- `python3 scripts/context_lint.py`: OK.

Deselected: `test_host_flash_outcomes.py::test_browser_renders_saved_warning_as_sticky_amber` fails identically on a clean origin/main (3d5ad78d). Pre-existing, not touched here.

Screenshot: `docs/tasks/qa-fix-errors-pay-390.png`. Amount (800 CZK) and Variable symbol (0000000001) both show values.

Deviations: branch rebased onto origin/main 3d5ad78d (was based on 8fb8047f). Step 3 changed one assertion in test_stay_fee_detail to 404 (as the brief allows).
