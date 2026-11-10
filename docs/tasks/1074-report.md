# 1074 report: guest scan feedback, smaller photo, nationality prompt, date example

Status: review

## Files changed (`git diff --stat origin/main`)

`_ocr_scan.html` (+107), `guest.css` (+25), `guest/base.html`, `i18n.py`, `guest_uk_i18n.py`, `validation_i18n.py`, `static_versions.json` (regenerated, guest.css only), `test_doc_ocr.py`, `test_guest_dob_separator.py`, new `test_guest_scan_feedback_browser.py`, `docs/tasks/screenshots-1074/` (9 PNGs), this brief and report. `routes/`, `doc_ocr.py`, `validation.py`: 0 diff lines.

## Commands (last lines)

- Step 1 before shots: `3 passed`. Step 2 baseline: `44 passed`.
- Step 3: `27 passed`. Step 4: `ok`, six chip lines. Step 5: `ok`, `20 passed`.
- Step 7: `36 passed`. Step 8 (new file): `23 passed`, 0 skipped.
- Step 9: `wrote ... static_versions.json (51 files)`, 2 lines changed, `3 passed`.
- Step 11.1 guest test-map row, `UBYHOST_REQUIRE_BROWSER=1 -rs`: `661 passed in 505.60s`, no SKIPPED.
- Step 11.2 privacy/cookies/static: `13 passed`. Step 11.3 context lint: `context lint: OK` (only pre-existing warnings).

## Section 7

- [x] No `g-btn secondary` in `_ocr_scan.html`.
- [x] New file and guest row pass, 0 skipped.
- [x] Diff only in section 3 files (plus the brief, screenshots, report).
- [x] routes/doc_ocr/validation diff: 0.
- [x] Before/after form shots at 390/768/1280 and scanned shots at 390/768/1280, checked by eye.
- [x] No sideways scroll (asserted). [x] Texts in six languages (asserted). [x] Lint clean.

## Visual check (for the PR)

Guest form step 1, at rest (pixel diff before vs after: the changed box is only the scan button at every width):
- 390: same card, fields, spacing and Continue button; scan button now brand red with white text, same size.
- 768: same; only the scan button fill changed.
- 1280: same two-column layout and sidebar; only the scan button fill changed.

Scanned state (stubbed values):
- 390: grey "Please check" chips under each filled field, inside the card; read-back line under the date stays above its chip; visa field hides for an EU nationality (existing behaviour).
- 768: chips under each field in both columns, inside the card; row heights grow by the chip only.
- 1280: same as 768; no overlap, no sideways scroll.

## Review fixes

The nationality sentence now shows once, under the picker (`#nationality_error`). The status line shows only `ocr_scan_done`; it falls back to both sentences only when the picker has no error slot. Tests assert the status line does not repeat it. After the fix, the new test file passed 25 and the guest test-map row passed 663, with 0 skipped. The new viewport screenshots are `after-busy-{390,768,1280}.png` and `after-natmissing-{390,768,1280}.png`.

- Busy: 390: grey spinner ring plus "Reading your document. This takes about 10 seconds." under the scan hint; it wraps to two lines and stays inside the card; fields are empty and nothing else moves; 768: same on one line; 1280: same on one line, sidebar unchanged.
- Nationality missing: 390: the page scrolls to the picker, whose search box has a red focus border; the sentence sits under it as a grey hint over two lines (the text is grey, not red); the country list opens below it and covers the child box; other fields show chips; 768: same in the right column, list over the lower fields; 1280: same, no overlap with the left column or sidebar.

## Deviations

- Step 0 applied the six review corrections to the brief (chip text "Please check" translated; smoothing quality; three-width scanned test; nationality prompt on stale value, also in `#nationality_error`, focus only when empty, cleared on a later scan that reads it; new stale-value test; line refs).
- The step 8 test code used bare-expression `wait_for_function` strings, which the guest page CSP blocks (`unsafe-eval`). Changed them to `() => ...` arrow strings in the test and in the brief (step 8 commit). No assertion changed.

## Questions

None.

## Unconfirmed

(a) Whether the browser's resampling (canvas, `imageSmoothingQuality = 'high'`) and the one extra JPEG pass at quality 0.9 change the OCR hit rate on real phone photos; only stub and synthetic images were tested, and the guest checks every field. (b) iOS Safari/WebKit not run (`createImageBitmap` options need Safari 15+; older versions send the original). (c) Real scan duration ("about 10 seconds" is the plan's wording; worst case about 45 s).

## Owner steps left

See the brief's "Owner steps": open the PR, check on a real phone, merge with `scripts/merge-pr-on-green.sh`, deploy by hand.
