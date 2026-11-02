# 0813 report: neighbour gap on the 0800-0804 pages

Status: blocked

## Files changed
- App/tests/test_0800_v2_remaining_pages_browser.py: added _NEIGHBOUR_JS and neighbour_findings(); the per-page test adds its findings (all 15 routes x 6 widths). Pairs inside main, excluding .side, .tabs, header, .env-banner and .help-tip, must keep 12 px.
- App/app/static/app2.css (blocks 0800-0804, 0808): gap 8px to 12px on body.v2 .havel-v2 .havel-topics .havel-chips; gap 10px to 12px on body.v2 .prop-new .property-create-actions; gap 8px to 12px on body.v2 .guide-page .ui-form-actions.

## Findings (step b, before fixes)
- havel, all 6 widths: a.ui-chip.havel-chip vs a.ui-chip.havel-chip, gap 8. Fixed.
- property-new, 390 px: a.ui-btn-secondary vs button.ui-btn-primary, gap 10. Fixed.
- property-new, 1024/1280/1440 px: a.ui-btn-secondary (cancel) vs section.panel.property-create-card, gap 8. NOT fixed.
- property-new, all widths: button.ui-btn-primary vs button.ui-btn-quiet, gap 8 (first run). Not reproduced after the fixes.
- guest-guide-quick, 390 and 1280 px: button.ui-btn-primary vs button.ui-btn-quiet, gap 8. Fixed by the gap 12 px rule on .guide-page .ui-form-actions.

## Commands (last lines)
- pytest 0800 + onboarding, UBYHOST_SHOTS_0800=1 (run 2, after fixes): 9 failed, 182 passed in 319.25s. Failing: property-new 1024/1280/1440 (cancel gap 8), guide 320-1440 (section.workflow-block vs details.guide-section.card, overlaps of -30 to -114 px, plus the pre-existing "main content ends under the tab bar" geometry finding).
- design_lint: FAIL, "T3 class not in catalog: guide-topic" in App/app/templates/guide.html.

## Findings outside this brief's files
- App/app/templates/guide.html has an uncommitted diff of 75 insertions and 76 deletions. I did not write it. The guide failures and the design-lint failure both appear only after that change, and run 1 (before it) showed no guide failures. I did not touch it.
- Trial: with the guide-page gap at 8 px, the guide-390 and guide-1280 cases passed. Restored to 12 px, as the brief asks, pending review of guide.html.

## Rules changed
- None outside the two files above. No commit, push or reset.

## Deviations
- Done: steps a, b, c (partly). Left: property-new desktop cancel link gap (step c); guide page regression (needs guide.html owner decision); step d run is green only after those are fixed.
- Stray empty file /tmp/x was created by a mistaken command and removed.

## Owner / orchestrator steps left
- Decide what to do with the uncommitted guide.html change, then rerun: App/.venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py tests/test_onboarding_wizard_browser.py -q --tb=line -p no:cacheprovider (from App/, with the env from the brief).
- Fix the property-new cancel-link gap at desktop widths (cause not found in the actions row margin; check the card-to-actions structure in the page).
