# 0953 report: wizard old look, red stars, seat vs accommodation, plain e-mail
Status: review (branch par-0953, not pushed, no PR opened: the owner or orchestrator pushes)

## Commits
step 1 old onboarding card look; step 2 banner (primary + quiet underlined skip); step 3 progress strip and icon tiles; step 4 red stars; step 4b seat and e-mail stars; step 5 seat and accommodation headings; step 6 plain e-mail, hint removed; step 7 server tests; step 8 browser geometry test. Step 9 is this commit.

## Tests
- test_wizard_old_look_0953.py: 4 pass.
- test_wizard_old_look_0953_browser.py: 3 pass (390, 768, 1280), 0 skipped.
- test_0884_wizard_geometry_browser.py + test_layout_lint_browser.py + test_operator_naming.py + test_static_versions.py: 51 pass after the fixes below.
- Test-map run: 348 pass, 27 fail in test_property_navigation_browser.py and test_onboarding_wizard_browser.py on stale selectors (#property-guest-link-title, #sec-calendars, #sec-basics). Known, handled by orchestrator; not touched.
- Known: test_host_i18n 'no such table: apartment' not run here.

## Screenshots (docs/tasks/screenshots-0953/)
- 390, viewed: checklist card has kicker, logo, 0%, bar, underlined skip; property step shows 4-segment strip and red stars; police shows stars on IDUB, login, abbreviation, facility name; operator form shows "Operator: registered seat" heading with stars on seat and e-mail; Stays shows primary "Continue setup" and underlined skip.
- 768, viewed: operator form (entities). Not viewed: checklist, property, police, apartments.
- 1280, viewed: checklist (card, primary, skip, step cards); property (strip, stars, two headings distinct). Not viewed: police, entities, apartments.
- Finding: the "?" help tip on the checklist sits below the skip link (not fixed).

## Required stars applied
Property: internal_name, legal_entity_id, addr_house_no, addr_zip, addr_obec, checkin_hour, checkout_hour. Police: uby_idub, uby_mark, uby_name, uby_ws_user. Operator: name, ico (business), seat, contact_email. Server does not require seat or e-mail; starred because the form is HTML-required (owner-approved by orchestrator).

## Deviations
- app2 cache key: 0953b to 0953f (test_static_versions refuses changed content under one key).
- Seat heading is a p, not h3: the entities page renders the business form twice (edit and new), so layout-lint flagged duplicate headings.
- ui-btn-quiet untouched; skip links use onboarding-skip-link.

## Design-system checklist
Not ticked: docs/design/design-system.md was not reread in this run.

## Decision line for orchestrator
- [wizard] 2026-11-04: old look restored on the current 4-step flow; red star marks mandatory fields; operator e-mail has no purpose text. Source: brief 0953.

## Owner questions
Do you want the 8 steps back as well, or only the old look? Is the older look (before 2b4a9199) meant?
