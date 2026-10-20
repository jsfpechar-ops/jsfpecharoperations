# 0180: design lint T3 after 0177, and make the 0178 test assert something

Status: todo
Depends on: 0178 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

1. `python3 scripts/design_lint.py` fails: `App/app/templates/reservations.html: T3 class not in catalog: stay-col-property-name` (introduced by 0177, line 154). Remove the unlisted class: the line should read `<div class="ui-sub">...</div>` (the muted look comes from `ui-sub`). Do not add the class to the catalog.
2. `test_setup_checklist_is_a_padded_card` (added in 0178) returns early because the checklist (`[data-setup-status]`) does not render on `wide_host["apartments"][0]`: `_property_overview.html` line 47 shows it only when the property's readiness is set and the setup wizard is not active. Make the test assert for real.

## 2. Context

Fixtures in `App/tests/test_host_wide_geometry_browser.py` expose `wide_host["configured_apartment"]` and `wide_host["unconfigured_apartment"]` among others (read the fixture to see which property finished setup). The overview URL is `/apartments/{id}` with the Overview tab active by default. If neither fixture property shows `[data-setup-status]`, find the condition in `_property_overview.html` line ~47 and in `routes/` (grep `readiness`), then use the smallest seeding step in the test (for example calling the same db helper the page uses to mark the wizard done) instead of changing app code. Never change app code or the 0178 CSS here.

## 3. Files

`App/app/templates/reservations.html` (one class), `App/tests/test_design_guardrails_browser.py` (the 0178 test only), `docs/tasks/0180-*`.

## 4. Steps

1. Fix the class (section 1, item 1). From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -2`. Expected: OK.
2. Fix the test: open `/apartments/{id}?lang=en` for a property where `[data-setup-status]` exists (section 2), wait for it, remove the early `return`, and keep its three assertions (not tinted, solid border, heading at least 12 px inside). If after two attempts no fixture shows the element, stop and report which condition hides it.
3. From `App/` (foreground, timeout 600000, `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium`): `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py -q -rs 2>&1 | tail -6`. Then from the repo root `git checkout -- docs/tasks/0102-evidence && git clean -fdq docs/tasks/0102-evidence` (skip if refused). Expected: all passed, 0 skipped, and the checklist test really measured the element (add a `print` of the measured values or an `assert box` so an absent element fails).
4. Take a 1280 px screenshot of the checklist: short Playwright script outside the repo using the same fixture, element screenshot of `[data-setup-status]`, saved to `docs/tasks/0180-screenshots/checklist.png`. Report in one line how it looks (white card, border, padding).
5. Run the unit tests for stays pages: `.venv/bin/python -m pytest tests/test_overhaul.py -q --tb=short 2>&1 | tail -4` from `App/`.
6. Commit: `git add App docs/tasks/0180-* && git commit` with message "0180: lint class, checklist test measures the card" and the two trailers given by the orchestrator.

## 5. Do not touch

App CSS, other tests; hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] design lint OK; the checklist test fails if the element is absent and passes with it present; guards pass with 0 skipped.

## 8. Stop and ask

No fixture shows the checklist after two attempts.

## 9. Report

`docs/tasks/0180-report.md`, short; `Status: review`.
