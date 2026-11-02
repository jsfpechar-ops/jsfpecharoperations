# 0834 report

Status: review
Branch claude/project-thread-6ozz7x. Not pushed, no PR.

## Done
- Step 1 (54130d38) and 1b (93055c43): migration 0034_apartment_ocr_scan.sql only. The two db.py lines were dropped (duplicate column with the migration).
- Step 2 (6a775479): doc_ocr.available gates on ocr_scan and policy, plus module docstring line.
- Step 3 (3030e6f4): admin.py allowed field and payload rule.
- Step 4 (2e6ec36b): _property_editor.html switch row, help via help_tip.
- Step 5 (655017ed): EN and CS keys apartment.form.ocr_scan.label and .hint.
- Step 6 (04804e3f): gate tests (a, b, c) in test_doc_ocr.py; fixtures set ocr_scan 1; geometry world sets ocr_scan 1.
- Step 6b (see git log): tests (d) and (e) in App/tests/test_property_form_save.py (added to brief §3 by owner).

## Commands (last lines)
- `tests/test_doc_ocr.py tests/test_billing_order.py tests/test_property_form_save.py -x`: "54 passed, 126 warnings in 4.98s"
- `UBYHOST_BROWSER_EXECUTABLE=... tests/test_guest_ocr_geometry_browser.py -rs`: "8 passed in 26.94s" (0 skipped)
- `python3 scripts/context_lint.py`: "context lint: OK" (warnings only)

## Deviations
- Scan switch row uses help_tip directly instead of field_label, because field_label would add a second label.
- No 390 px screenshot: host editor change, not a guest template.
- Warnings: Pillow getdata DeprecationWarning (from 0833).

## Owner steps left
- Review and open the PR yourself (no push by executor).
