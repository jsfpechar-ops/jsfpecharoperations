# 0948 report: property page status strip

Status: review (polish step 8 applied: equal heights, centered status line, always six cards)

## Files changed
- App/app/templates/_property_editor.html, apartment_form.html, _property_create.html, partials/settings_back_header.html (strip, guest card removed, aside cleanup, copy button to header)
- App/app/host_i18n.py, host_vi_i18n.py (strip strings; unused preview.connections removed)
- App/app/static/app2.css (0948 block, dead guest-card rules removed), App/app/templates/base.html (app2.css key 20261104-0948c, workflow.css key 20261104-0949w), App/tests/static_versions.json
- Tests: test_0534, test_0286, test_0531, test_onboarding_wizard_browser, test_property_readiness, v2_mockup, test_0541 (geometry, police card, copy button)

## Tests (0 skipped)
- 0534/0286/0531/copy_property_settings/static_versions: 34 passed
- v2 mockup property + readiness: 27 passed
- onboarding guest/copy/property: 19 passed
- 0541: 5 passed
- test_layout_lint_browser.py: 4 passed (after one-column strip below 360 px)

## Screenshots (property page, EN, docs/tasks/screenshots-0948/)
- 390: strip 2 columns, dots visible, problem text red, Copy link button inside Guest link card. Calendars card shows a large empty gap between title and status line (see Deviations).
- 768: strip 3 columns, left edge matches form edge.
- 1280: strip 3 columns over the form and Preview; edges match. Copy-settings button not shown: hidden once setup is finished (by design of 0424).

## Deviations / open
- Step 8 (owner review of 1280 screenshot): `.sc` now uses `align-content:center`, so one-line cards center their title and status; `.prop-strip` uses `grid-auto-rows:1fr`, so all cards share one height. The Guest link card (Copy link button) sets the row height, so at 390 all rows are about 120 px tall.
- Door code card is always rendered (six cards): `data-state="off"` with the existing "Off" text when no door code or disabled; links to `#sec-lock`. Layout: 2 columns at 390, 3 columns at 768 and 1280, no odd empty slot.
- Strip below 360 px is one column (layout lint word-per-line failure at 320 px). Brief acceptance says 2 columns below 640; this is a narrow-phone exception.
- Screenshots were taken from the lint run (route property-detail, EN), not `?lang=cs`.
- Design-system checklist not ticked in step 8 (checklist file not opened in this step); owner-facing copy check not done.
- Manifest and workflow.css key were fixed in a9e8a861 (not this task's scope).

## Commits
ce75c46c, deb52441, 2fcf7614, 32382ebb, a9e8a861, 5850f710, 9bd7381d, 0e7d8493, dd301ed9, fcc8efde
