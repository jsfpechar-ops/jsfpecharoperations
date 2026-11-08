# 1010 report: required stars

Status: review
Branch: claude/required-stars (local only, not pushed)
Done: steps 1 to 6 (steps 5 and 6 partly: see Deviations).

## Commits
- 9a6dea7c step 1: editor police fields (IDUB, login, facility abbreviation, facility name; password only when none stored)
- e4487e0e step 2: calendar platform and URL, wizard ICO, wizard password, stay-fee fields (when fee_required), legend on wizard calendar step
- 6e5ead39 step 3: stars on permalink PIN (_property_editor.html) and reveal reason (guest_form_admin.html), keep HTML required; App/tests/test_required_stars.py (5 passed)
- c4047b77 earlier blocked report (superseded by this file)

## Tests (from App/, UBYHOST_REQUIRE_BROWSER=1 where marked)
- test_required_stars.py: 5 passed
- Non-browser set (wizard_old_look_0953, 0952_lock, property_address_required, calendar_platform_required, times_required_0210, stay_fee, onboarding*): 166 passed, 57 skipped. The skips are browser-only tests in test_onboarding_wizard_browser.py run without UBYHOST_REQUIRE_BROWSER.
- Browser set with UBYHOST_REQUIRE_BROWSER=1 -rs (property_navigation, 0833 editor, ttlock_0954, wizard_0884 geometry, design_setup_wizard, onboarding_wizard_browser, host_geometry, design_guardrails, onboarding_followup): 165 passed, 0 skipped.
- test_layout_lint_browser.py (UBYHOST_REQUIRE_BROWSER=1): 4 passed, 0 skipped.
- scripts/context_lint.py: OK (warnings are pre-existing).
- Test map row `test_wizard_old_look_0953_browser.py` does not exist; dropped from list.

## Screenshots (390 px, /mnt/project-files/ux-shots/stars/)
- wizard-police-390.png: red stars on IDUB, Web-service login, Web-service password (no password stored), Facility abbreviation, Facility name. Legend "Fields marked * are required." shown once. Labels do not wrap. Optional fields not starred.
- wizard-calendar-390.png: red stars on Platform and iCal export URL. "Your name for it (optional)" unstarred. Legend shown once. Labels do not wrap.
- property-editor-390.png: the full-page capture is downscaled to about 390x9400, so the stars in the police section are too small to verify by eye. The wizard police page shows the same star markup. Needs a crop check by the owner or a follow-up.

## Deviations
- Step 5 editor crop could not be verified at this scale (see above).
- Step 6 PR not opened: this run is local only, no push.

## Owner questions
1. Street stays unstarred (server and test 0953 treat it as optional). Make it required in a separate validation brief?
2. Door-code time stars show while door codes are off (kept, pinned by test_ttlock_setup_0954_browser.py). Hide them while off?
