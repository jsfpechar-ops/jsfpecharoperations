# 1006 report

Status: review

## Files changed (uncommitted, no commit, no push, no PR)
- App/app/static/app2.css: 1006 block appended (ui-page-narrow, ui-section-card, ui-section-head, ui-kv, ui-kv-row, ui-note-strip)
- App/app/templates/base.html: app2.css?v=20261107-1207 -> 20261108-1001
- App/app/templates/billing_plan.html: settings-lane also gets ui-page-narrow; status shown as ui_badge pill; tip= moved into the titles of Change, Cancel and Invoices
- docs/design/catalog.json: 6 class names added
- docs/design/design-system.md: section 5b with checklist added before section 6
- docs/tasks/1006-report.md: this file
- The temporary screenshot test was created and deleted again. Property editor template (step 7) was reverted, see below.

`git status --short`: M app2.css, base.html, billing_plan.html, catalog.json, design-system.md; ?? docs/tasks/1006-ux-wolt-style-cards.md

## Commands (last lines)
- `python3 scripts/design_lint.py`: "design lint: OK"
- `python3 scripts/context_lint.py`: "context lint: OK"
- billing/property/host pytest (App/): `342 passed` after reverting step 7
- Before revert, one failure: tests/test_property_navigation_browser.py:177 (`_open_ids`) pins the exact markup `<details class="prop-sec" id=...>`. Changing the class broke it. Fixing it needs a test file outside brief section 3, so step 7 was reverted.
- Layout lint (UBYHOST_REQUIRE_BROWSER=1, UBYHOST_SHOTS_DIR=/tmp/shots): `4 passed`, 0 skipped, no findings reported.

## What I saw
- Plan and billing 390: one white card per section, narrow, single column. Title with "?" beside it (Your plan, Change, Cancel). Facts stacked label above value. Status "Active" is a small grey pill. Cancel button right aligned in its card. The Change buttons are stacked and right aligned, which is legible but not compact. In the full-page capture the fixed bottom nav and help bubble overlap content; that is a screenshot artifact, not a layout fault.
- Plan and billing 1280: 720 px centred column, label/value rows with dividers, Change buttons stacked right, Cancel card. No stray "?". Invoices section not shown: the test account has no invoices.
- 768: layout lint shot taken; not opened by me.
- Property editor: step 7 reverted, so the editor is unchanged. The screenshots are from the layout-lint run (property-detail-configured+open). At 1280 they are about 6000 px tall and at 390 about 9400 px; the viewer downscaled them, so I could not verify details. Nothing obviously broken was seen at that scale.

## Screenshots
- /mnt/project-files/ux-shots/wolt/billing-390.png
- /mnt/project-files/ux-shots/wolt/billing-1280.png
- /mnt/project-files/ux-shots/wolt/property-390.png
- /mnt/project-files/ux-shots/wolt/property-1280.png

## Deviations
- Step 7 (property editor class change) reverted, because of the test pin above.
- Cache key used is 20261108-1001 (as instructed).
- Test-map run only; no full suite.

## Owner steps left
1. Open the four screenshots and approve or reject.
2. Decide whether to brief a test update (test_property_navigation_browser.py:124 regex) so the six `prop-sec` sections can get ui-section-card.
3. If approved: commit and open the PR yourself, or ask for a commit brief.

## Verification (second run, 2026-11-08)
- base.html app2.css key: 20261108-1003; `tests/test_static_versions.py --write` run (51 files).
- `.venv/bin/python -m pytest tests/test_layout_lint_browser.py`: 4 passed, 0 skipped.
- Billing/plan tests (test_0416_plan_page_browser.py, test_billing_enforcement.py, test_billing_order.py): 30 passed.
- `python3 scripts/design_lint.py`: OK. `python3 scripts/context_lint.py`: OK.
- Fresh billing shots (active Standard account, 390 and 1280): no horizontal overflow (scrollWidth equals viewport at both widths).
- 390 px: page title left edge matches the card edge. Change buttons wrap to two rows (flex wrap), no stray icons beyond the "?" tips. The fixed bottom nav covers part of the full-page capture; this is a screenshot artifact.
- 1280 px: title and cards share the 720 px column left edge. Change buttons sit in one row. Cancel button right aligned in its card.
- Screenshots copied to /mnt/project-files/ux-shots/wolt/billing-390.png and billing-1280.png.
- The temporary shoot test was created and deleted again.
