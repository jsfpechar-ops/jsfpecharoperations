# 0809 report (executor, partial)

Status: blocked

## Files changed
- App/app/templates/havel.html: subtitle "Support assistant" moved from a visible p.sub under the h1 into a help "?" beside the h1 (wrapper span.havel-name-tip).
- App/app/templates/apartment_form.html (/apartments/new): lede under the h1 moved into a help "?" (heading-with-tip prop-name-tip); head gets class prop-new so the tip body stays closed until opened.
- App/app/templates/_property_create.html: "What happens next" aside: each small body moved into a help "?" beside its title; the door-code body keeps its /guide#door-codes link as the help "More" link.
- App/app/static/app2.css: two rules in the 0803 havel block for tip button size (24px, 44px below 1024px) for .havel-name-tip and .prop-name-tip.

Copy, translation keys and tests were not changed. No legal text was removed.

## Commands (last lines)
- .venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py tests/test_onboarding_wizard_browser.py tests/test_onboarding.py tests/test_design_setup_wizard_browser.py -q --tb=line -p no:cacheprovider | tail -8
  214 passed in 302.59s (0:05:02)
- .venv/bin/python -m pytest tests/test_property_create_browser.py -q --tb=line -p no:cacheprovider | tail -3
=========================== short test summary info ============================
FAILED tests/test_property_create_browser.py::test_create_page_is_short_and_has_each_field_once
1 failed, 12 passed in 7.10s

## Not done (left for the next session)
- Onboarding (/onboarding: step card descriptions, "Have ready" lines).
- Setup wizard: setup-wizard-lede / setup-wizard-instruction paragraphs in App/app/templates/setup_wizard/*.html (police legal text must go into a help tip).
- Host guest guide (guest_guide*.html), cleaning new/shares/properties (cleaning_*.html).
- Screenshots (brief 4d) not regenerated.
- Tests asserting moved text (test_property_create_browser.py) still pass because help text stays in the HTML.

## Deviations
Done: step a for havel and new property. Left: onboarding, wizard, guest guide, cleaning, screenshots. Stopped at the tool-call cap.

## Questions
- test_property_create_browser.py::test_create_page_is_short_and_has_each_field_once raises ValueError (header class ui-ph not found). Not obviously caused by these edits; check whether it failed before this change.

## Owner steps left
- None until the executor finishes the list above.

## Onboarding + wizard

Status: blocked (executor stopped at the tool-call cap; left items below).

Files changed (not committed):
- App/app/templates/_components.html: onboarding step card detail and "Have ready" line moved into the existing Learn disclosure; demo body and hint moved to a help tip; skip hint moved to a help tip.
- App/app/templates/setup_wizard/_layout.html: new block `wizard_help` beside the step question.
- App/app/templates/setup_wizard/{automation,calendar,door_lock,guest_link,police,property,stay_fee,try_it}.html: lede and "why" instruction paragraphs moved into `wizard_help` as help tips (ids `wiz-why-<step>`); door_lock keeps `wizard-lock-help`, try_it keeps `setup-try-help`.
- App/app/static/app2.css: 0800 block only, one rule for `.onboarding-welcome .help-tip-btn` size (24 px desktop). The 44 px mobile rule is still needed by the test; the mobile bottom clearance is unresolved.
- App/tests/test_onboarding_wizard_browser.py: two lede typography assertions changed to check the help tip ids `#wiz-why-stay_fee` and `#wiz-why-try`.

Left (not done):
- Onboarding mobile: test_v2_remaining_page[onboarding-390] and [onboarding-768] fail with "main content ends under the tab bar" after the help tip grew to 44 px. Fix needs a look at which element is lowest at scroll bottom.
- Onboarding 1440: tap target 23x21 on help tip; fixed by the 24 px desktop rule (passes).
- Left visible on purpose: onboarding finish line, the non-v2 onboarding now block, wizard done.html finish note, the police wait notes (wizard_notes), the guest_link link-window note, the door_lock "all taken"/"unavailable"/other-brands lines, try_it instructions and waiting line.
- Screenshots not regenerated (UBYHOST_SHOTS_0800 not run).
- Guest guide and cleaning failures (guest-guide-*, cleaning-new-*, cleaning-shares-*) belong to the other executor's pages; not touched.

Final test tails (last full run, from this executor, before the last CSS edits):
- `tests/test_0800_v2_remaining_pages_browser.py tests/test_onboarding_wizard_browser.py tests/test_onboarding.py tests/test_design_setup_wizard_browser.py`: `15 failed, 199 passed in 312.04s`; the failing tests are cleaning-shares-* and guest-guide-* (other executor's pages).
- `tests/test_0800_v2_remaining_pages_browser.py` alone: `24 failed, 82 passed in 145.51s`; onboarding-1440 was listed then, and the 0800 onboarding subset was `3 failed, 5 passed` after the last CSS change (onboarding-390, onboarding-768, onboarding-1440 fails on mobile clearance).

## Guest guide + cleaning

Status: blocked

### Files changed (not committed)
- App/tests/test_property_create_browser.py: the slice anchor is now `<div class="head prop-new-head prop-new"` (the v2 page header in apartment_form.html). The test passes.
- App/app/templates/cleaning_shares.html: intro sub line, share-ready text, and the caution paragraph moved into `help_tip` (heading-with-tip for the h1; next to the create button for the caution). Added `{% from "_components.html" import help_tip with context %}`.
- App/app/templates/cleaning_edit.html: property-times hint, notes hint (still `aria-describedby="clean-notes-hint"`, now the help body id), and auto-help moved into help_tip. Same import added.
- App/app/templates/guest_guide.html: import-off and import-help text, and Leon help moved into help_tip. Same import added.
- App/app/templates/guest_guide_card.html: prompt sub line moved into a help_tip beside the h1. Same import added.
- App/app/templates/guest_guide_qr.html: meta sub line moved to help beside h1; print and rotate help moved to help_tip. Same import added.
- App/app/templates/guest_guide_quick_done.html: missing_lede moved to help_tip. Same import added.

Not changed: app2.css (no CSS edits yet), cleaning_settings.html (/cleaning/properties/{id} is outside the named scope), guest_guide_quick.html, public guide templates.

### Test results
- `tests/test_guest_guide_view.py tests/test_guest_guide_pages.py`: 31 passed.
- `-k "guest_guide or cleaning"` (full run, before the last fixes): 50 failed earlier from a missing import, now fixed. Last run: 12 failed, 217 passed. All 12 are browser geometry in tests/test_0800_v2_remaining_pages_browser.py for cleaning-shares (all widths) and cleaning-new 1440.
- `tests/test_property_create_browser.py tests/test_0800_v2_remaining_pages_browser.py`: 24 failed, 95 passed. The failures are the same cleaning cases plus the guest-guide ones listed below.

### Why the browser tests fail
At 390 px the `.help-tip-btn` in the cleaning-shares heading is 23x21 px (minimum 44 px), and its "?" overlaps the heading text "Choose properties for a read-o...". The fix needs CSS inside the 0804 (cleaning) and 0802 (guest guide) blocks of App/app/static/app2.css, for example a 44 px tap size on `.heading-with-tip .help-tip-btn` at max-width 1023px and room for the button beside the h1. I did not make this edit: the tool budget ran out first.

### Deviations
- Done: steps 1 to 3 (test anchor, cleaning and guest-guide templates, help imports). Left: CSS for help-tip placement in the 0802 and 0804 blocks, then rerun the browser tests, then 390 px screenshot per changed page.
- Guest-guide photo helper (`ui_field ... help=t('guest_guide.photos.help')`) and the "photos full" line were not moved; they are field and state text, not yet decided.
- The import-help tip sits in the section body, not beside the section heading.

### Owner steps left
None. Commit is the orchestrator's job.

## 0812

Brief: docs/tasks/0812-v2-help-tip-shared.md. Only `App/app/static/app2.css` changed. Not committed (owner asked for no commit from this run).

Rules added (end of app2.css, block `/* 0812 help tip (v2) */`): `body.v2 .help-tip` (inline-flex, relative, margin-left 6px); `body.v2 .help-tip-btn` (24 px, 44 px below 1024 px); `body.v2 .heading-with-tip, body.v2 .havel-name-tip` (flex, gap 6px); `body.v2 .help-tip-body` hidden; popover shown on `.is-open` or `:not([data-js]):focus-within`.

Rules removed: prop-name-tip and havel-name-tip help-tip-btn sizes (692-695); wiz-page help-tip-btn (1189, 1236); prop-new help-tip-btn selectors in the 1270-1271 blocks (fragment only, the rest of those lines kept); onboarding-welcome help-tip-btn (1292-1293); the `:is(.prop-new,.wiz-page)` help-tip, help-tip-btn, help-tip-body and popover rules (1299-1302). Kept: stay-detail (602/606), details (385, 943-945).

Deviation: the brief's -10px negative margin on the 44 px mobile target made the "?" overlap the h1 on havel (test "overlapping text in head"). Removed the negative margin; the 44 px target now takes its full box. Havel's `.havel-name-tip` also made flex, same reason.

Final tails:
- `pytest tests/test_0800_v2_remaining_pages_browser.py tests/test_onboarding_wizard_browser.py tests/test_property_create_browser.py -q --tb=line -p no:cacheprovider -rs` → `3 failed, 201 passed in 289.99s`
- Failing: `test_v2_remaining_page[onboarding-320|390|768]`: "main content ends at 1149 under the tab bar (top 916)".
- Same three onboarding cases also fail on HEAD (copy from `git archive HEAD`): "main content ends at 1111 ... (top 916)" at 768. Pre-existing, not caused by this brief; not fixed (out of brief scope).
- `UBYHOST_SHOTS_0800=1 pytest tests/test_0800_v2_remaining_pages_browser.py -q` → `3 failed, 103 passed in 153.56s` (same onboarding cases). Screenshots regenerated.
- `python3 scripts/design_lint.py` → `design lint: FAIL`, 5 T3 findings, all in templates, none in app2.css: apartment_form.html (prop-name-tip), cleaning_shares.html, guest_guide_card.html, guest_guide_qr.html (heading-with-tip), havel.html (havel-name-tip). Catalog (docs/design/catalog.json) lacks these classes. Needs a catalog decision or a template change (not in this brief).

Left for the owner / next brief: onboarding geometry (above); design lint catalog entries; the stale comment at app2.css line ~1285 ("0809: the onboarding help tips ...") still describes the deleted rule.
