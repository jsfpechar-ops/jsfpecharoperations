# 0931 report: layout lint checks for the design system

Status: review

## Files changed
- `App/tests/layout_lint.js`: header-actions-misaligned (step 1, 64bb4be), multiple-save-in-form (step 2, af5595f), duplicate-heading (step 3, 1fec034).
- `App/tests/test_layout_lint_browser.py`: BAD_PAGE samples for multiple-save-in-form and duplicate-heading, a separate BAD_HEADER_PAGE at 1024 px for header-actions-misaligned, the expected set, and two `ALLOW` entries (d2827e6 and step 4b commit).
- Step 5 (decisions line): skipped, per coordinator. The orchestrator adds it.

## Commands
- `App/.venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short -rs` (with `UBYHOST_REQUIRE_BROWSER=1`, Chromium 1243): first run `1 failed, 1 passed`. The failure was 14 real multiple-save-in-form findings. Second run after the allow-list: `2 passed in 235.36s`, 0 skipped.
- `App/.venv/bin/python -m py_compile` and `node --check App/tests/layout_lint.js`: OK.
- Standalone Playwright check on the bad markup: multiple-save-in-form and duplicate-heading fire at 390 px, header-actions-misaligned fires at 1024 px.

## §7 checklist
- [x] Three new rules fire on the bad sample
- [x] `test_layout_lint_browser.py` passes with 0 skipped
- [x] Context lint green at HEAD (step 5 not applied, so no change to decisions.md)

## Real findings per rule (host pages, 7 widths, plus +open variants)
- header-actions-misaligned: 0 findings.
- duplicate-heading: 0 findings.
- multiple-save-in-form: 14 findings, on `fee-setup` (320, 390, 768 and wider) and `automation` (320, 390 and wider). Element: `button.btn "Save changes"`, two submits in one form. This is owner debt. It is allow-listed in `ALLOW` with the reason "owner debt, fix in UX threads". No page was changed.

## Deviations
- The brief names a `KNOWN_FINDINGS` dict. I used the existing `ALLOW` dict (route, rule) -> reason instead, so there is one allow-list mechanism, not two.
- The header rule runs only at 768 px and up, so its sample is a separate 1024 px page inside the same test, not part of BAD_PAGE (390 px).
- Screenshots: not taken. No template or CSS changed, and the only host-page result was a lint finding.

## Questions
- Should the two `fee-setup` and `automation` save buttons be merged into one? That is the UX-thread fix. The allow-list entry should be removed when it is done.

## Owner steps left
- None for the code. Add the step 5 decision line (the orchestrator does this). Open the PR if the coordinator wants one. No push was made.
