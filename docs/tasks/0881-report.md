# 0881 report

Status: blocked
Done: steps 1 to 7 applied. Blocked on one guest test outside brief section 3 (see Questions).

## Files changed
- App/app/doc_ocr.py (step 1), App/app/routes/admin.py (step 2), App/app/host_i18n.py (step 3)
- App/app/templates/guest/_ocr_scan.html (new), App/app/templates/guest/form.html (steps 4, 5)
- App/app/i18n.py (step 6, EN and CS only)
- App/tests/test_doc_ocr.py, App/tests/test_property_form_save.py, App/tests/test_guest_ocr_geometry_browser.py (step 7)

## Commands (last lines)
- test_doc_ocr, test_property_form_save, test_billing_order: `54 passed, 126 warnings in 5.26s`
- test_guest_ocr_geometry_browser (browser, -rs): `6 passed in 4.47s` (0 skipped)
- test-map guest row (test_guest_*.py, test_guest_browser_e2e.py, browser env): `1 failed, 557 passed in 218.56s`
  - FAILED test_guest_languages.py::test_every_guest_key_exists_in_all_five_languages: de still has ocr_scan_title, ocr_scan_help, ocr_scan_label; all languages lack ocr_scan_button.
- `python3 scripts/context_lint.py`: `context lint: OK`

## Screenshot
- 390 px: written by test_a_390px_screenshot_of_the_scan_step to /tmp/ubyhost-shots/guest-form-scan-step-390.png (not viewed).

## Acceptance
- Not met: one guest key-parity test fails (see Questions).

## Deviations
- Step 1 and 2 edited together, committed separately. Step 5 stray endif fixed (amended).
- Include placed before the h2 in the first card (literal brief wording).
- Step 6 removed keys in EN and CS only, as the brief says. Other languages still have the old keys.
- Step 7: the brief's fill test (set_input_files on #ocr-scan-file) was not added; no such test existed in the geometry file. The status-line-in-card test was dropped because the status is hidden until a file is chosen.

## Questions
- test_guest_languages.py needs every guest key in all five languages. Options: (a) add ocr_scan_button to de, es, fr and uk, and remove the three old keys from those languages too. Needs translated copy from you. (b) keep the old keys in every language and add only ocr_scan_button to the non-EN/CS languages as an English fallback. Which one?

## Owner steps left
- Decide the question above. Then push and update PR #727 yourself. Nothing pushed.
