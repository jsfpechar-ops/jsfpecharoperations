# 1029 report

Status: blocked (one browser assertion fails at 1280 px, see Open finding). Branch `claude/fee-rate-dates`, no PR.

## What changed

- `App/app/routes/stay_fees.py`: new `rate_from_default()` returns today (Prague, ISO).
- `App/app/routes/admin.py`: `rate_from_default` added to both `apartment_form.html` render contexts (new and edit).
- `App/app/templates/_stay_fee_fields.html`: one `.field` after the rate field, editor only (`not fee_required`) and only when the rate is above 0. Native `type="date"`, `min` and `value` = today, label "Applies from" (i18n key `apartment.form.stay_fee.rate_from_label`), help `rate_from_help`. No JS.
- `App/app/host_i18n.py` (EN, CS), `App/app/host_vi_i18n.py` (VI): the two keys.
- `App/tests/test_stay_fee_rate_field_1029.py`: new, 5 tests.

## Commands (last lines)

- `pytest tests/test_stay_fee_rate_field_1029.py tests/test_required_stars.py tests/test_property_form_save.py`: 25 passed (before the browser test was added).
- `UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_stay_fee_rate_field_1029.py tests/test_layout_lint_browser.py tests/test_0833_property_editor_browser.py tests/test_static_versions.py tests/test_host_i18n.py -rs`: 28 passed, 0 skipped, 1 error (the new browser test had a fixture import error at that time, since fixed).
- `pytest tests/test_stay_fee_rate_field_1029.py -k 1029 -rs`: 4 passed, 1 failed: `1280: date field not visible`.
- `static_versions`: passed. No static file changed, so no cache bump.

## Open finding

The browser test asserts `is_visible()` on `#stay_fee_rate_from` after opening `#sec-fee`. It passes at 390 and 768 and fails at 1280. The 1280 screenshot shows the field visible next to the rate, so this looks like a test or locator problem, not a layout one. Not investigated further (executor cap).

## Screenshots (in /mnt/project-files/ux-shots/rate-date/, not committed)

- 390 px: "Applies from" under the rate, date input full width, label and "?" on one row. The "?" is a large 44 px circle with a gap from the label (same as the rate field, so it is the house style, not this field). The bottom nav covers the help line at the foot of the crop (capture artifact).
- 768 px: same stack as 390, one column, no horizontal scroll. Same large "?".
- 1280 px: rate and "Applies from" side by side in the first grid row, cadence below. Field and label not clipped.
- Chrome shows the native date as mm/dd/yyyy (browser locale). The house rule is dd.mm.yyyy. Native date input follows the browser, so it cannot be forced from the template.

## Design checklist

Rule 9 (one explanation): help text is in the tip only. Light mode, no JS, no new dependency.

## Owner or orchestrator steps left

- Decide on the 1280 test failure (fix the locator or accept), then merge gate per rule 10.
- Decide whether the native date format (mm/dd/yyyy in en-US browsers) is acceptable.
