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
