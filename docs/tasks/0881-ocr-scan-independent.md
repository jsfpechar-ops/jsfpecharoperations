# 0881 Passport OCR: scan independent of passport upload

Status: todo. Executor: Haiku 5.5. Same branch and PR #727. No new dependency.

## 1. Objective
Owner decision (Josef, 2026-11-02): the host toggle is independent of "Passport or ID photo from the guest". With the toggle on (Max only) a guest gets a minimal "Scan your passport" button at the top of the form. The photo is read once and not saved (unless the host separately requires the upload). Keep it minimal: one button, one status line, no fine print.

## 2. Context
Today the scan tickbox sits inside `#passport-photo-card` in `App/app/templates/guest/form.html` (~lines 269-280) and its JS (~lines 437-509, `scanToggle`, `runScan`, `fillFields`) reads the file from the upload input. The POST route `/l/<token>/<id>/scan` in `App/app/routes/guest.py` (~1953) already stores nothing and needs only `doc_ocr.available(apartment)`. `doc_ocr.available` currently also requires policy `required_foreign`; the editor save currently forces `ocr_scan` to 0 when policy is off. Both couplings go. Rule: no fine print; the guest form is wizard steps (`data-guest-step`), anything outside a step shows on every step, so the control goes INSIDE the first step card.

## 3. Files
`App/app/doc_ocr.py`, `App/app/routes/admin.py` (the `ocr_scan` payload line), `App/app/templates/guest/form.html`, `App/app/templates/guest/_ocr_scan.html` (new), `App/app/i18n.py` (guest keys ~367 and ~1058), `App/app/host_i18n.py` (the two `apartment.form.ocr_scan.*` keys EN and CS), `App/tests/test_doc_ocr.py`, `App/tests/test_guest_ocr_geometry_browser.py`, `App/tests/test_property_form_save.py`.

## 4. Steps
1. `doc_ocr.available`: remove the `passport_photo_policy` condition (keep `ocr_scan == 1`, Tesseract, test list, Max). Fix the docstring.
2. `admin.py`: `payload["ocr_scan"] = 1 if _form_str(form, "ocr_scan", "") == "1" else 0` (no policy check).
3. `host_i18n.py` EN label "Guests can scan their passport to fill in the form", EN hint "The photo is read once and not saved. Max plan only."; CS label "Hosté mohou naskenovat pas a vyplnit formulář", CS hint "Fotografie se jednou přečte a neukládá se. Jen v tarifu Max.". The toggle stays right under the passport policy select in `_property_editor.html` (no change there).
4. New `guest/_ocr_scan.html`, included at the top of the first step card (`data-step-title="{{ t('your_details') }}"`, ~line 77) only `{% if ocr_available %}`. Contents: `<div class="g-field" id="ocr-scan">`, a `<label class="g-btn secondary" for="ocr-scan-file">{{ t('ocr_scan_button') }}</label>` over a visually hidden `<input type="file" id="ocr-scan-file" accept="image/jpeg,image/png,image/webp">`, and `<p class="hint" id="ocr-scan-status" role="status" aria-live="polite" hidden></p>`. Use the existing button classes of the guest form; no new CSS unless a geometry test fails (then the smallest rule in the guest CSS file that holds `.checkline`). Inline script in the same partial: on `change` of the file input POST `FormData` (`passport_photo` = file, `_csrf` = form `_csrf` value) to `form.getAttribute('action').replace(/\/save\?/, '/scan?')`, show `ocr_scan_working`, on `{kind:'values'}` fill `surname, first_name, birth_date (DDMMYYYY to DD.MM.YYYY), nationality, doc_number` exactly like the old `fillFields`, dispatch `input` and `change` events on each filled element, show `ocr_scan_done`; on error show `data.message` or `ocr_unavailable`; clear the file input value afterwards so the photo is not kept in the page.
5. `form.html`: delete the `{% if ocr_available %} ... #ocr-scan ... {% endif %}` block inside the passport card and the old JS (`scanToggle`, `scanStatus`, `fillFields`, `runScan` and the two listeners). Nothing else in that script changes.
6. `i18n.py` EN and CS: add `ocr_scan_button` ("Scan your passport" / "Naskenovat pas"); delete `ocr_scan_help`, `ocr_scan_label`, `ocr_no_file`, and `ocr_scan_title` only if `grep -rn` shows no other use.
7. Tests: `test_doc_ocr.py` gate tests become: False when `ocr_scan` 0; True with `ocr_scan` 1 and Max even with policy `off`; others unchanged. `test_property_form_save.py` (d): saving `ocr_scan=1` with policy `off` now stores 1. `test_guest_ocr_geometry_browser.py`: scan control is in the first step now: no wizard walk needed; at 390 and 1280 px assert no sideways scroll, `#ocr-scan` inside its card, button and status at least 12 px apart, button height at least 44 px, and absent when the owner's `ocr_scan` is 0; keep the existing patched-`run_tesseract` fill test but drive it through `#ocr-scan-file` with `set_input_files` and assert the surname field is filled.

## 5. Do not touch
Everything else on the guest form, the `/scan` route, the scan engine, Stripe, other pages.

## 6. Commands
From `App/`, each ending `2>&1 | tail -30`: `.venv/bin/python -m pytest tests/test_doc_ocr.py tests/test_property_form_save.py tests/test_billing_order.py -q --tb=short -x`; then `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome UBYHOST_BROWSER_NO_SANDBOX=1 .venv/bin/python -m pytest tests/test_guest_ocr_geometry_browser.py -q -rs --tb=short` (0 skipped); also the other guest-form tests the test-map lists for `templates/guest/form.html`. Root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance
All pass, 0 skipped. Commit each step as `0881 step k`. Do not push.

## 8. Stop and ask
An anchor is missing, a guest-form test outside §3 breaks, or a step is unclear: STOP and ask.

## 9. Report
`docs/tasks/0881-report.md`, 200 words at most.
