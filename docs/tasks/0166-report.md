# 0166 report

Status: review

## Files changed

- `App/tests/a11y_guard.js` (copied unchanged from the design-reset tools folder)
- `App/tests/test_a11y_guard_browser.py` (new: four tests, reuses imports and ROUTES from `test_design_guardrails_browser.py`)
- `.github/workflows/ci.yml` (one entry added to the browser test list)
- `docs/design/MASTER.md` (section 11.1 Accessibility added after 11.0)
- `docs/tasks/0166-a11y-guard.md` (status set to review), `docs/tasks/0166-report.md`

## Command

`cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_a11y_guard_browser.py -q -rs -p no:cacheprovider 2>&1 | tail -60`

Last lines: `2 failed, 2 passed, 1 warning in 65.90s`. 0 skipped, no Python errors.

## Findings (tests)

- test_every_page_passes_the_page_checks: FAILED, 617 findings. contrast 220, target-size-24 304, generic-link-text 41, nav-no-current 24, no-accessible-name 24, aria-target-missing 4.
  - dashboard en 390: generic-link-text, a "More"
  - dashboard en 390: contrast, a "View all stays", 4.17
  - fee-setup en 390: no-accessible-name, input#overview-guest-url
  - guest-new en 390: aria-target-missing, canvas#sig-canvas, aria-describedby sig-help
- test_keyboard_focus_is_visible_and_not_covered: FAILED, 15 findings. focus-not-visible 8, focus-obscured 7.
  - operators 1280: focus-not-visible, input#new_contact_phone_country_code
  - operators 1280: focus-obscured, input#new_signature_file
  - stay-detail 1280: focus-obscured, input#stay-link
- test_pages_reflow_at_320_and_200_percent: PASSED, 0 findings.
- test_pages_survive_wide_text_spacing: PASSED, 0 findings.

JSON output: `/tmp/ubyhost-a11y-page.json`, `/tmp/ubyhost-a11y-focus.json`, `/tmp/ubyhost-a11y-reflow.json`, `/tmp/ubyhost-a11y-spacing.json`.

## Deviations

- The CI entry sits inline in the existing one-line list, next to `tests/test_design_guardrails_browser.py`, because the list is a single shell command.
- The output files are named by short names (page, focus, reflow, spacing), since the brief gave no names.
- Step 9 copy to `/mnt/project-files/design-reset/a11y/` is not done here (not part of step 6).
- The 0102-evidence cleanup ran without a permission refusal.
- An untracked `docs/tasks/0167-field-button-rows.md` was already present; it is not mine and is not committed.

## Questions

- MASTER now has two sections numbered 11.1 (the new Accessibility section and the existing Lint section). Renumber, or keep?

## Owner steps left

- Decide the 11.1 numbering. Fixes for the findings are separate briefs; the new test is expected to fail until then.
