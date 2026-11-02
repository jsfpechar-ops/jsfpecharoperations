# 0809 report B: host guest guide, cleaning pages, property-create test

Status: blocked

## Files changed (not committed)
- App/tests/test_property_create_browser.py: the slice anchor is now `<div class="head prop-new-head prop-new"` (the v2 page header in apartment_form.html). The test passes.
- App/app/templates/cleaning_shares.html: intro sub line, share-ready text, and the caution paragraph moved into `help_tip` (heading-with-tip for the h1; next to the create button for the caution). Added `{% from "_components.html" import help_tip with context %}`.
- App/app/templates/cleaning_edit.html: property-times hint, notes hint (still `aria-describedby="clean-notes-hint"`, now the help body id), and auto-help moved into help_tip. Same import added.
- App/app/templates/guest_guide.html: import-off and import-help text, and Leon help moved into help_tip. Same import added.
- App/app/templates/guest_guide_card.html: prompt sub line moved into a help_tip beside the h1. Same import added.
- App/app/templates/guest_guide_qr.html: meta sub line moved to help beside h1; print and rotate help moved to help_tip. Same import added.
- App/app/templates/guest_guide_quick_done.html: missing_lede moved to help_tip. Same import added.

Not changed: app2.css (no CSS edits yet), cleaning_settings.html (/cleaning/properties/{id} is outside the named scope), guest_guide_quick.html, public guide templates.

## Test results
- `tests/test_guest_guide_view.py tests/test_guest_guide_pages.py`: 31 passed.
- `-k "guest_guide or cleaning"` (full run, before the last fixes): 50 failed earlier from a missing import, now fixed. Last run: 12 failed, 217 passed. All 12 are browser geometry in tests/test_0800_v2_remaining_pages_browser.py for cleaning-shares (all widths) and cleaning-new 1440.
- `tests/test_property_create_browser.py tests/test_0800_v2_remaining_pages_browser.py`: 24 failed, 95 passed. The failures are the same cleaning cases plus the guest-guide ones listed below.

## Why the browser tests fail
At 390 px the `.help-tip-btn` in the cleaning-shares heading is 23x21 px (minimum 44 px), and its "?" overlaps the heading text "Choose properties for a read-o...". The fix needs CSS inside the 0804 (cleaning) and 0802 (guest guide) blocks of App/app/static/app2.css, for example a 44 px tap size on `.heading-with-tip .help-tip-btn` at max-width 1023px and room for the button beside the h1. I did not make this edit: the tool budget ran out first.

## Deviations
- Done: steps 1 to 3 (test anchor, cleaning and guest-guide templates, help imports). Left: CSS for help-tip placement in the 0802 and 0804 blocks, then rerun the browser tests, then 390 px screenshot per changed page.
- Guest-guide photo helper (`ui_field ... help=t('guest_guide.photos.help')`) and the "photos full" line were not moved; they are field and state text, not yet decided.
- The import-help tip sits in the section body, not beside the section heading.

## Owner steps left
None. Commit is the orchestrator's job.
