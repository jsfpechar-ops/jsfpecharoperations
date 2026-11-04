# 0952 report

Status: blocked (one browser test fails, probably pre-existing; see Next step)

## Commits (par-0952, not pushed, no PR)
- 2b64ecc8 guard, #door-code/#smart-locks anchors, CSS order cleanup
- bc805d4f one `#sec-lock` outside the property form (form="property-settings-form" on door-code controls)
- e55ffb48 tests/test_0952_lock_section.py; test_0534 order assertions updated
- 3c604bb9, 71262dbb, 1d commit: switch status, discard, return-section tracking follow form-attribute controls
- this commit: tests/test_0952_lock_section_browser.py, screenshots, report

## Browser run (after the last JS fix, 0 skipped)
test_layout_lint_browser, 0541, unsaved-changes, 0199, host_geometry, static_versions, 0952 browser file: 35 passed, 1 failed.
- Failed: test_0251 test_overview_cards_and_tablet_menu_on_touch, locator `aside.preview a.r[href="#sec-lock"]` never appears. No `a.r` link to `#sec-lock` exists in base templates (base has only `a.sc` in the strip). Failed in the first run too. Probably a stale selector; not confirmed on the base commit.
- New tests: door edit outside the form sets data-dirty; `#door-code` and `#smart-locks` open `#sec-lock`; 0 skipped.

## Lint
F841 `spec` at test_0541_property_page_phone_browser.py:168 exists in base 871906ab too. Left unchanged.

## Screenshots (docs/tasks/screenshots-0952/, one per width, lock section open, `?view=settings&section=lock`)
- 390: Smart lock section scrolled into view; Door-code access times, check-in/out selects, Digital door lock switch, lock select visible; nothing clipped in the crop.
- 768: Smart lock between Automatic messages and Stay fee; single accordion; controls in one column; nothing clipped.
- 1280: same order; two-column door-code grid; "How it works" and connect block visible; nothing clipped.
- Only one Smart lock section in the page (test asserts one `id="sec-lock"`, no `sec-lock-account`, no duplicate ids).

## Design-system checklist
Not ticked: I did not run the checklist in docs/design/design-system.md in this session.

## Deviations
- Sub-block small headings not added; existing headings kept.
- app.js key is 20261104-0952m (0952j and 0952k were superseded by JS fixes).

## Decision line for orchestrator
[ui] 0952 lock section is one accordion outside the property form; door-code controls use form="property-settings-form"

## Next step
1. Confirm test_0251 aside locator against base 871906ab (run that one test on the base commit in a clean checkout), then fix the selector or the markup.
2. Tick design-system checklist; add the Smart lock desktop check to the report.

## Update (orchestrator follow-up)
- test_0251 desktop taps now use the strip cards `nav.prop-strip a.sc[data-strip="door"|"police"][href=...]`. Same intent, no skip. The door card renders only when `door_code` exists in this base (main has bcc6ef3d); the 0251 fixture must be checked after rebase.
- Same switch in test_onboarding_followup_browser.py (police) and test_property_navigation_browser.py (police).
- test_property_navigation three_views field check now also counts form-attribute controls: passes.
- Still failing, stale aside-card tests from 0948 (aside cards removed in base): test_onboarding_followup calendars row, test_property_navigation bookings/overview/tabs tests (aside #sec-basics, #sec-fee, aside .pv .r). Not fixed; calendars and fee rows have no strip card.
- Design-system checklist: not ticked (not reviewed in this run).

## Design-system checklist (docs/design/design-system.md)
- [x] 64: 390/768/1280 checked; no sideways scroll on the 0251 fit check; screenshots show no clipping.
- [x] 65: test_layout_lint_browser green, 0 skipped; 390/768/1280 screenshots opened and inspected (see per-width notes above).
- [x] 66: no new copy added (existing keys reused); no em dash added.
- [ ] 59, 60, 61, 62, 63, 67: not verified in this run (61: the door-code controls now submit with the main Save via form="property-settings-form"; not re-checked visually).

## Known, handled on main
Still failing from brief 0948 (aside cards removed in base), not fixed here:
- test_onboarding_followup_browser.py: calendars aside row (`aside.preview a.r[href='#sec-calendars']`).
- test_property_navigation_browser.py: test_bookings_view_with_no_one_and_many_feeds, test_overview_cards_point_at_the_canonical_editors, test_tabs_hashes_drafts_history_and_validation_in_browser (aside fee and overview cards).
- test_onboarding_wizard_browser.py:1155 calendars row (not run here).
