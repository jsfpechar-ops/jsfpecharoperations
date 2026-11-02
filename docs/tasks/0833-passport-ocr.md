# 0833 Passport OCR: read more passport photos (Tesseract only)

Status: todo. Executor: Haiku 5.5. One PR. No new dependency (Pillow and Tesseract already ship).

## 1. Goal
Phone photos of passports are often tilted, with the MRZ small in the frame. Today `doc_ocr.read_document` runs Tesseract once on the whole shrunken image. Make it try the MRZ band first, straightened and enlarged, then the whole image, and only ever return a read whose check digits validate (unchanged). Fix the stale "coming soon" checkout copy. Add a read-rate script that prints no personal data.

## 2. Files (open only these)
`App/app/doc_ocr.py`, `App/tests/test_doc_ocr.py`, `App/app/host_i18n.py` (grep `billing.order.plan_max`, EN and CS), `App/scripts/ocr_readrate.py` (new), `docs/context/decisions.md` (append), `docs/context/known-issues.md` (append).

## 3. Steps
1. In `doc_ocr.py` add after `_TD1_LEN`:
```python
_WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
BAND_FRACTION = 0.4  # the MRZ sits in the bottom 40% of the page
BAND_WIDTH = 1800  # px; Tesseract reads small MRZ text better enlarged
_TILT_ANGLES = (-8, -6, -4, -2, 0, 2, 4, 6, 8)
```
2. Add `mrz_band(jpeg: bytes) -> bytes`: open with Pillow (mode L), crop the bottom `BAND_FRACTION` of the height, resize so width is `BAND_WIDTH` (keep ratio, LANCZOS), pick the angle from `_TILT_ANGLES` whose rotated copy has the highest variance of per-row mean brightness (get row means by resizing the rotated image to `(1, height)` with `Image.BOX`, variance of `getdata()` values; rotate with `expand=True, fillcolor=255`; evaluate on a copy downscaled to 400 px wide for speed), rotate the full-size band by that angle, return a JPEG (quality 90). Pure Pillow, no numpy.
3. In `run_tesseract` change the argument list to add `"-c", f"tessedit_char_whitelist={_WHITELIST}"` and lower `timeout` to 15.
4. Replace `read_document` body: `attempts = (mrz_band(jpeg), jpeg)`; for each attempt call `run_tesseract`, `parse_mrz`; on `NothingRead` continue to the next attempt; `NoEngine` still propagates; if none read, raise `NothingRead`. Keep the nationality check against `validation.country_codes()`. A failing `mrz_band` (any `Exception`) must fall back to `jpeg` only. Add `mrz_band` to `__all__`.
5. `host_i18n.py`: in `billing.order.plan_max` replace the sentence "Document scanning (OCR): coming soon. Not available yet, including during the trial." with "Document scanning (OCR) of passports, not included in the trial." and the Czech key's matching sentence with the same meaning ("Skenování dokladů (OCR) pasů, není součástí zkušební doby."). Grep the CS value first with `grep -n 'billing.order.plan_max' App/app/host_i18n.py`; if other keys carry "coming soon" for OCR, STOP and ask.
6. Tests in `test_doc_ocr.py` (tests replace `run_tesseract`, no real Tesseract): (a) a synthetic Pillow image, tilted 4 degrees, makes `mrz_band` return a JPEG whose width is `BAND_WIDTH`; (b) `read_document` returns values from the band attempt when the first call returns a valid MRZ; (c) when the band attempt returns garbage and the whole-image attempt returns a valid MRZ, values come back; (d) both garbage raises `NothingRead`; (e) `mrz_band` raising falls back to the plain image; (f) `NoEngine` still propagates. Use the valid TD3 sample already in the file.
7. `App/scripts/ocr_readrate.py DIR`: for each jpg/png/jpeg in DIR call `doc_ocr.prepare_image` then `doc_ocr.read_document`; print only `file index, ok|nothing_read|bad_file` and a final `read N of M (P%)`. Never print any field value, filename or MRZ text. Exit 0. Module docstring: photos are the owner's own test passports and never go in the repo.
8. Append to `decisions.md` one line: `2026-11-02 | OCR accuracy: stay on Tesseract; MRZ band crop plus straighten plus character whitelist, pure Pillow; PaddleOCR (ONNX) only if ocr_readrate on about 30 real photos reads under 90%, then owner decision line needed | owner | test_doc_ocr`. Append to `known-issues.md`: OCR-B traineddata not used (needs a downloaded asset); read rate unmeasured until the owner runs `ocr_readrate.py` on real photos.

## 4. Tests (brief 6)
From `App/`: `.venv/bin/python -m pytest tests/test_doc_ocr.py tests/test_guest_ocr_geometry_browser.py tests/test_privacy_first.py -q --tb=short -x -rs 2>&1 | tail -30` and, for the copy change, `.venv/bin/python -m pytest tests/test_billing_order.py -q --tb=short -x 2>&1 | tail -30`. From repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. Browser tests: 0 skipped. No template change, so no screenshots.

## 5. Not in scope
No PaddleOCR, MinerU, new package or tessdata download. No guest-form change. No stored images (module stays stateless).

## 6. Report
`docs/tasks/0833-report.md` per executor.md, then open one draft PR from this branch.
