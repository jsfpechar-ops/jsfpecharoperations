# 1800 report: step C (lint, screenshots, checklist)

Status: review (768 CSS fixed in step C4; screenshots retaken; guest-new Cancel finding is pre-existing on base)

## Files changed
- App/tests/test_design_guardrails_browser.py: admin route map gets `admin-operations-alerts` and `admin-operations-alerts-kind` (kind=deadline_at_risk, level=critical). Admin pages are covered by this test, not by test_layout_lint_browser.py (no admin fixture there). (C1)
- App/app/static/app2.css: one rule in the `@media (max-width:1023px)` block, before the `thead` rule: `body.v2 .ui-table-stack,body.v2 .ui-table-stack tbody{display:block;width:100%}`. Stacked cards now fill the container at 768 px. (C4)

## Commands
- Browser runs need `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell` (the bundled Playwright expects build 1255, only 1243 is installed; no download done).
- `cd App && UBYHOST_BROWSER_EXECUTABLE=... UBYHOST_REQUIRE_BROWSER=1 /tmp/claude-0/venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_design_guardrails_browser.py -k 'layout_lint or every_host_page or admin_pages or known_regressions or guard' -q -rs --tb=short`
  Last lines: `E   AssertionError: 1 layout findings {'tap-target-small': 1}` / `E     guest-new 390 open: ['tap-target-small', 'a.ui-btn.ui-btn-quiet "Cancel"', 43, 44]` / `1 failed, 14 passed in 309.14s (0:05:09)`. 0 skipped. Only failure is the Cancel case; no new findings from the CSS change.
- Base check (git worktree of 26e20e4, removed afterwards): `pytest tests/test_design_guardrails_browser.py -k every_host_page` gives the same `guest-new 390 open: ['tap-target-small', 'a.ui-btn.ui-btn-quiet "Cancel"', 43, 44]`. `1 failed, 10 deselected`. Pre-existing, not caused by this change.
- Temporary screenshot tests (deleted after each run): see Screenshots.
- Not run: Go tests, context_lint.

## Screenshots (768, fake data, Python app; retaken in C4)
/mnt/project-files/go-final/a4-shots/ops-alert-drilldown/ : all-768.png, filtered-768.png, summary-768.png, other-stays-768.png, other-invoices-768.png, other-operators-768.png, other-settings-768.png. Earlier 390 and 1280 files unchanged.

## Visual notes (768)
- Drill-down all (`/admin/operations/alerts`): one critical `dates_changed_resign` card now spans the full content width. Defect fixed.
- Summary (`#ops-alerts` on `/admin/operations`): card spans full width. Defect fixed.
- Drill-down filtered (`kind=deadline_at_risk&level=critical`): shows "Nothing here." because this fixture has only a `dates_changed_resign` alert. It does NOT show the card layout; the filtered card width is unverified at 768. Needs a fixture with a deadline_at_risk alert.
- Stays (`/reservations`), invoices (`/invoices`): full-width cards. These pages use their own phone cards, not `ui-table-stack`, so they are a no-regression check only.
- Operators (`/entities`) and settings (`/settings`): render their own forms and list rows at this fixture state; no visible `ui-table-stack` table, so no regression check of the shared rule.
- Earlier 390 and 1280 observations unchanged.

## Design-system checklist
Ticked: help "?" beside title; no truncated label; light mode; no action only on hover.
Not verified: host_page.html extension, header action row, 12 px spacing, ui-section-card/ui-kv use, no nested boxes.
Not ticked: CI (pending).

## Deviations
- Done: steps 1 to 4 (C1 test routes; C2 screenshots and review; C3 report; C4 768 CSS fix, retaken screenshots, other-page shots, this report). Left: none of the brief's steps. Open: filtered-768 has no card to check (see Visual notes); guest-new 390 Cancel tap target (43x44 px) is pre-existing on base 26e20e4.
- Date format on the stay column is ISO (2026-11-17), while the checklist asks for dd.mm.yyyy. Not changed; it matches the existing stay display.
- Screenshots came from the Python app, not the Go build.
- Trailer: C4 commit uses the Sonnet 5.5 trailer named in the brief.

## Questions
- Should the fixture seed a deadline_at_risk alert so the filtered drill-down can be shot at 768?
