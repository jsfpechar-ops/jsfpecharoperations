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
