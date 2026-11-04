# 0897 report: stay-fee guest pay, phase 0 (design fix-up)

Status: review

Done: design fix-up of block 4 "Guest pays the stay fee". Nothing committed, no branch changes.

## Files changed (this fix-up)
- App/app/templates/_stay_fee_fields.html: hint moved into the "?" of the collect label; inline styles removed; rails are plain rows (fieldset class `stay-fee-rails`); Revolut and cash fields carry classes for the CSS show/hide.
- App/app/static/app2.css (shared host sheet, scoped to `.stay-fee-guest-fields`): plain fieldset, checkline rows, hairline dividers, 44 px rows, 18 px "?" with 44 px hit area, `:has()` show/hide for Revolut and cash.
- App/app/templates/base.html and App/tests/static_versions.json: app2.css cache key 0903b to 0897c.
- docs/tasks/screenshots-0897/: six PNGs replaced (EN 390/768/1280, unticked 390, CS 390, flag off 390).

## Commands (from App/)
- `pytest tests/test_stay_fee_guest_pay_0897.py tests/test_stay_fee*.py tests/test_property_*.py tests/test_host_i18n.py`: 342 passed, 0 failed, 0 skipped.
- `UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_layout_lint_browser.py tests/test_host_geometry.py -rs`: 4 passed, 0 skipped.
- `python3 scripts/design_lint.py`: OK. `python3 scripts/context_lint.py`: OK (next free 0932, migration 0037).

## Screenshots
- Element crop at 390 (scratch): block is 4 plain rows, no fieldset border, "?" 18 px inline after label, Revolut and cash hidden when unticked. Viewed.
- Full-page 390, 768, 1280, CS, flag off: captured, no sideways overflow (measured). Not all opened by eye; see checklist.

## Design-system §5 checklist
- [x] Page extends `host_page.html`; no own shell; no `<style>` or `style=""` in the block.
- [x] Header action row: property page header not changed by this brief.
- [x] One Save per form: unchanged.
- [x] No fine print: hint moved under "?"; the off-state line stays as state.
- [ ] 12 px between neighbours: rows 44 px, fields 16 px. Labels sit 8 px above inputs (`--space-2`); 6 px is not a token. Owner or orchestrator to decide.
- [x] No truncated label.
- [ ] 390/768/1280 no sideways scroll: measured yes; 768, 1280, CS and flag-off PNGs not opened by eye.
- [x] `test_layout_lint_browser.py` green, 0 skipped.
- [x] CS and EN keys present together; no em dash in the guest_pay keys.
- [ ] CI watched: not pushed.

## Deviations
- Checked checkboxes are coral: the shared `.checkline input` uses `accent-color: var(--brand)` (#c85a52) in app.css and app2.css. Left as is (shared component, rule 9). Flag for the owner.
- Label-to-input gap is 8 px, not 6 px (no 6 px token).
- If the Revolut link has an error while Revolut is unticked, the field stays visible so the error is seen.

## Owner steps left
1. Decide on the coral checkbox accent (shared component) and the 6 px vs 8 px label gap.
2. Open the 768, 1280 and CS PNGs and confirm.
