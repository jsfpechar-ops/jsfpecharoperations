# 0834 Passport OCR: per-property host toggle (default off)

Status: todo. Executor: Haiku 5.5. Goes into PR #727 (same branch).

## 1. Objective
Scanning is on today for every Max property with passport upload on. Make it a per-property host toggle, default off. The toggle only has effect while "Passport or ID photo from the guest" is on: the scan tickbox lives inside that card. Without upload, saving forces the toggle off, and the guest form never shows the tickbox.

## 2. Context
`doc_ocr.available(apartment)` in `App/app/doc_ocr.py` gates the guest tickbox (Max plan, test list, Tesseract). The editor field `passport_photo_policy` is saved in `App/app/routes/admin.py` (~line 1530) and rendered in `App/app/templates/_property_editor.html` (~line 183). Switch markup to copy: the `feature-switch-row` / `switch feature-switch` block of `door_codes` in the same template. Schema rule: new file in `App/app/migrations/`, mirror the newest `ALTER TABLE` migration.

## 3. Files
`App/app/migrations/0035_apartment_ocr_scan.sql` (new), `App/app/db.py` (only where `passport_photo_policy` is declared at ~165 and ~969: add the matching `ocr_scan INTEGER NOT NULL DEFAULT 0`), `App/app/doc_ocr.py`, `App/app/routes/admin.py`, `App/app/templates/_property_editor.html`, `App/app/host_i18n.py`, `App/tests/test_doc_ocr.py`, `App/tests/test_guest_ocr_geometry_browser.py`, the test file the test-map names for the property editor save.

## 4. Steps
1. Migration plus the two `db.py` lines: column `ocr_scan INTEGER NOT NULL DEFAULT 0` on `apartment`.
2. `doc_ocr.available`: return False unless `int(apartment["ocr_scan"] or 0) == 1` and `(apartment["passport_photo_policy"] or "off").strip().lower() == "required_foreign"`; keep every existing gate after those. Update the module docstring gate list in one line.
3. `admin.py`: add `"ocr_scan"` to the allowed-fields set next to `"passport_photo_policy"` and, after the policy lines, `payload["ocr_scan"] = 1 if (_form_str(form, "ocr_scan", "") == "1" and payload["passport_photo_policy"] == "required_foreign") else 0`.
4. `_property_editor.html`: after the passport policy select, a switch row (copy the `door_codes` markup, no JS needed) with `name="ocr_scan" value="1"`, checked when `apartment.ocr_scan`, label `t('apartment.form.ocr_scan.label')`, help `t('apartment.form.ocr_scan.hint')` via the same `field_label` help mechanism as the policy field. No visible description text.
5. `host_i18n.py` EN and CS keys `apartment.form.ocr_scan.label` ("Fill the form from the document photo" / "Vyplnit formulář z fotky dokladu") and `apartment.form.ocr_scan.hint` (EN "Needs the passport or ID photo above to be on. Max plan only. The photo is read on our server and not kept for this." CS equivalent). Hint text must say it needs the upload setting.
6. Tests: (a) `available` False when `ocr_scan` is 0 even on Max with upload on; (b) False when `ocr_scan` is 1 but policy is `off`; (c) True when both on and Max; (d) saving the editor with `ocr_scan=1` and policy `off` stores `ocr_scan` 0; (e) saving with both on stores 1. In `test_guest_ocr_geometry_browser.py` set `ocr_scan` 1 on the world's apartment next to the existing `passport_photo_policy` update so the 8 geometry tests keep passing; its test at ~line 266 (no toggle when unavailable) must still hold.

## 5. Do not touch
No new dependency, no guest template change, no other settings, no `main`.

## 6. Commands
From `App/`, each ending `2>&1 | tail -30`: `.venv/bin/python -m pytest tests/test_doc_ocr.py tests/test_billing_order.py <editor test file from the test-map> -q --tb=short -x`; then `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome UBYHOST_BROWSER_NO_SANDBOX=1 .venv/bin/python -m pytest tests/test_guest_ocr_geometry_browser.py -q -rs --tb=short` (0 skipped). Root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance
All commands pass, 0 skipped. Commit each step as `0834 step k`. Do not push.

## 8. Stop and ask
An anchor is missing, the test-map names no editor test file, or a step is unclear: STOP and ask.

## 9. Report
`docs/tasks/0834-report.md`, 300 words at most.
