# 0800 report: new property and onboarding on v2

Status: blocked (one test left failing; tool budget reached). Not committed (orchestrator commits).

## Files changed
- `App/app/templates/apartment_form.html`: `v2 = true`; create-page header (h1 + sub) moved into body; empty `page_title`/`meta` blocks.
- `App/app/templates/_property_create.html`: `prop-new` class on the outer lane.
- `App/app/templates/onboarding.html`: `v2 = true`; calls `onboarding_welcome(onboarding, v2=true)`.
- `App/app/templates/_components.html`: `onboarding_welcome` macro only (new `v2` param; v2 header, no now-block, step action button, no logo/kicker, `data-layout="v2"`).
- `App/app/static/app2.css`: block `/* 0800 new property + onboarding (v2) */` appended at the end.
- `docs/design/catalog.json`: `prop-new`, `prop-new-head`, `onboarding-step-action` added. `design_lint.py` OK.

## Test results
- `test_0800_v2_remaining_pages_browser.py -k "property-new or onboarding"`: 12 passed, 0 skipped.
- `test_property_create_browser.py`, `test_onboarding.py` (other than below), `test_property_address_required.py`, `test_new_property_defaults.py`, `test_property_operator_defaults.py`, `test_first_property_step.py`: pass.
- Still failing: `tests/test_onboarding.py::test_the_calendar_step_offers_adding_a_stay_by_hand` (line 409, expects "Add a stay by hand" on the page). Cause not found: the now-block that carried this label is hidden on v2, and the step button only shows when the step has a url (`step.url`, or `onboarding.current.url` for the current step). Fix to try: show the step action for every not-done step with a url, or check which step the calendar test sets up as current.
- `test_onboarding_wizard_browser.py`: about 50 failures seen in one run, on setup/automation and overview pages (e.g. `accentColor` 'auto' check at `/apartments/1/setup/automation`). Not run again after my last change; not verified whether they predate this branch. Not my pages.

## Screenshots (last run, before the final CSS tweak was reviewed)
- `docs/tasks/screenshots-0800/property-new-390.png`
- `docs/tasks/screenshots-0800/property-new-1440.png`
- `docs/tasks/screenshots-0800/onboarding-390.png`
- `docs/tasks/screenshots-0800/onboarding-1440.png`
Not yet looked at by the executor after the last edit.

## Deviations
- Step 4 duplicate: the "now" block repeated the current step with number `completed + 1`, which can differ from the list's `loop.index`. On v2 the now-block is not rendered; the list numbers by `loop.index` only.
- Step detail "Have ready" line kept (small grey text under the detail) so existing copy is not removed; test_onboarding.py:161 needs it.
- Layout marker is `data-layout="v2"` on the section, not a class, so the old `class="onboarding-welcome"` assertion still matches.
- Property form: follow-up aside sits beside the form only from 1280 px (test_property_create_browser needs the form at least 420 px wide at 1024 px).
- Phone tap targets: `.help-tip-btn`, copy button and "Manage business details" link made 44 px below 1024 px.
- Onboarding step action uses `step.url`, falling back to `onboarding.current.url` for the current step.

## Owner steps left
- None. Orchestrator: commit the changed files, fix the calendar-step test, then look at the four screenshots.
