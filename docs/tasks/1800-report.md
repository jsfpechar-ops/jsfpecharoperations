# 1800 report: step C (lint, screenshots, checklist)

Status: review (partial: CSS defect open, see Deviations)

## Files changed
- App/tests/test_design_guardrails_browser.py: admin route map gets `admin-operations-alerts` and `admin-operations-alerts-kind` (kind=deadline_at_risk, level=critical). Admin pages are covered by this test, not by test_layout_lint_browser.py (no admin fixture there).

## Commands
- `cd App && UBYHOST_REQUIRE_BROWSER=1 .../venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_design_guardrails_browser.py -k 'layout_lint or every_host_page or admin_pages or known_regressions or guard' -q -rs --tb=short`
  Last lines: `1 failed, 14 passed in 318.28s (0:05:18)`; `E   AssertionError: 1 layout findings {'tap-target-small': 1}` / `guest-new 390 open: ['tap-target-small', 'a.ui-btn.ui-btn-quiet "Cancel"', 43, 44]`
  Admin guard test and layout-lint test passed. 0 skipped.
- Temporary screenshot test (deleted after run): 9 screenshots plus metrics.json. Overflow 0 px and 0 lint findings on all nine.
- Not run: Go tests, context_lint.

## Screenshots
/mnt/project-files/go-final/a4-shots/ops-alert-drilldown/ : summary-{390,768,1280}.png (the #ops-alerts section), all-{390,768,1280}.png, filtered-{390,768,1280}.png, metrics.json. Rendered from the Python app with fake data.

## Visual notes
- Drill-down 390: cards stack full width; labels present; no overflow. Stay shows name and dates; "stay removed" and "none" render.
- Drill-down 768: stacked cards fill only about half the container (left-aligned), the rest is empty. Defect, not caught by lint.
- Drill-down 1280: table, columns fit, no wrapping issues.
- Summary 390: stacked cards full width. Summary 768: cards narrow, same defect. Summary 1280: table, fine.

## Design-system checklist
Ticked: help "?" beside title; no truncated label; light mode; no action only on hover.
Not verified: host_page.html extension, header action row, 12 px spacing, ui-section-card/ui-kv use, no nested boxes.
Not ticked: CI (pending).

## Deviations
- Done: steps 1 to 3 (C1 test routes; C2 screenshots and review; C3 this report). Left: 768 CSS fix (shared `body.v2 .ui-table-stack` rules in App/app/static/app2.css around line 1856; the width needs a dedicated fix, not done).
- Date format on the stay column is ISO (2026-11-17), while the checklist asks for dd.mm.yyyy. Not changed; it matches the existing stay display.
- Screenshots came from the Python app, not the Go build.
- guest-new 390 "Cancel" tap target (43x44 px) fails the guard test. Not in this change's scope; not verified against base.
- Trailer: Haiku 5.5 used (the harness attribution) instead of the Sonnet 5.5 named in the brief.
