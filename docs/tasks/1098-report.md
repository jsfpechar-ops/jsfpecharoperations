# 1098 report: guest page polish (design check 5 to 11)

Status: blocked

## Per item

- **5** `guest.css`: `.g-row { gap: 16px 14px }`, `.g-row > .g-field { margin-bottom: 0 }`, `.g-field .hint:empty { margin: 0 }` (Forms: 16 px between fields). Content-bottom gaps before: 390 `first_name>surname` 30, `birth_date>nationality` 35; 768 and 1280 row>row 32, DOB row>doc 37. After: all 16. `test_guest_browser_e2e.py` gaps loop now counts stacked row fields, tolerance 2 (passes, no follow-up).
- **6** `form.html` + `guest.css` `.g-dates-link`: coral 44 px link with the rail card (>=1020) and under `p.g-form-line` (below); `g-back` only for "Back".
- **7** `guest.css`: the three under-15 groups' checked row is `--g-line-2` / `--surface-3`; radio dot stays coral.
- **8** Not real: measured, passes. 390x844, sticky button 774-832 at every target position; `#u15-note` 0-23, `.g-review h2` 249-281, intro 293-361, legal tick 702-721 when the review is at top; all clear at start, focus and bottom positions, both paths. No CSS change.
- **9** `_fee_pay.html` dot span; `#fee-pay` is the one card, options are top-ruled sections, pay panel 1 px `--g-line` on `--g-surface-2`.
- **10** `all_done_body_fee` x6 shortened to the section 2 strings.
- **11** `stay.html` other-phone people are `div.g-card.g-summary.g-summary-row` "Person N · saved ✓"; `guest.css` `div.g-summary-row`.

## Commands (last lines)

1. 1098 + 1084 + 1090 + 1091 browser: `47 passed`, 0 skipped.
2. Guest suite: `2 failed, 838 passed`, 0 skipped. Failing: `test_guest_form_draft_1087_browser.py::test_1087_the_form_design_is_the_same_apart_from_the_one_line[390]` and `[768]`: `assert 14.5 <= 1` (removing `#draft-welcome` moves `#first_name` by 64.5 px, the line's height plus margins is 79). Cause: with "Not your dates?" no longer a `g-back` anchor at the top of `.g-checkin-main`, the welcome line is its first child and its top margin collapses through the column, so the test's margin sum overcounts. 1280 passes (no inline link there either; the rail carries it).
3. Layout lint + OCR + 0896: `27 passed`, 0 skipped.
4. i18n/copy/static versions: `96 passed, 1 warning`.
5. `context lint: OK`.

## Screenshots (`docs/tasks/screenshots-1098/`)

- form 390/768: even 16 px gaps; "Not your dates?" coral under the dates line. 1280: link under the rail dates card; grid fields even. Pre-existing: long empty band below the host card at 1280 (the rail spans 30 grid rows with a 44 px gap), not from 1098.
- u15-role 390 (844 viewport): legal tick and Save person both clear. 768/1280: chosen role row grey, dot coral; nothing sideways.
- stay-fee 390/768/1280: one card, sections ruled, "Please pay now" plain with coral dot; one sentence once; "Ada Guest · saved ✓" and "Person 2 · saved ✓" alike.

## Other coral selected states seen (not fixed)

None on the touched pages. The form's fee estimate (`_fee_estimate.html`) still nests a white panel in the grey box (out of scope).

## STOP (section 8)

A pin outside the two named ones fails because of item 6's markup change. Not fixed: options are (a) keep a zero-height element or `display: flow-root` on `.g-checkin-main` so the welcome margin does not collapse (a layout change outside the brief), or (b) let the 1087 test read the line's real push (a test change outside section 3). Orchestrator to choose.

## Deviations

Command 2 run without `-x` to see every failure at once.
