# 1052 report: Stay fee card rows and a centred property editor

Status: review.

## Changed
- `App/app/templates/_property_editor.html`: stay-fee include wrapped in `.fee-grid`; copy-row "?" uses the SVG icon.
- `App/app/templates/_stay_fee_fields.html`: step 1 order rate, period, Applies from; every "?" `svg=true`; More details summary has an SVG chevron.
- `App/app/templates/_components.html`: `help_tip`/`field_label` take `svg=false` (default unchanged elsewhere).
- `App/app/templates/_entity_business_fields.html`: signature legend "?" is the SVG icon when `prefix == 'fee_'`.
- `App/app/static/app2.css`: two `1052` blocks at the end (card grid, subgrid step 1, help-mark rule, chevron; centred editor column from 1024 px).
- Cache key `app2.css?v=20261109-1052b` (`base.html`, `tests/static_versions.json`).
- New test `App/tests/test_stay_fee_card_rows_1052_browser.py`.

## Tests (local, Chromium)
- 83 passed, 0 skipped: layout lint, a11y guard, 1052, 1032 wide, guest pay, 0833 editor, property controls, navigation, repetition audit, 1029 rate field, wide geometry, 0505 help tips, 0884 wizard geometry, static versions.
- 1046 passed: `test_stay_fee*.py`, `test_property_*.py` (non-browser), entity editor navigation, cache tests. `design_lint.py` OK.

## Screenshots (`/mnt/project-files/ux-shots/stayfee-card/`)
- 1280: steps 1-3 stacked left, step 4 right, no void; rate and period inputs on one line, labels end on one line; "?" icons 8 px after labels; signature full width on the field edges.
- 1280 all-open: More details open (chevron up) and three payment methods open; left and right columns stack independently, signature below the taller one.
- 768: step 1 two columns (rate | period, Applies from below), other steps single column, even gaps.
- 390: single column, icons at the label end, label lines not stretched by the 44 px tap box.
- 1440 / 1800 page: header, pills, notice and card form one centred column (max `--lane`); help bubble clear.
