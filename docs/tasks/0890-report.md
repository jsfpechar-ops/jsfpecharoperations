# 0890 report

Status: blocked
Branch: claude/project-thread-2t66ph (nothing committed or pushed, per owner instruction; no PR)

## Files changed
- App/tests/test_0890_speed_pages_browser.py (new): fixture speed_host (module scope), base, 28 geometry cases, end-to-end test, screenshot test.
- App/app/static/app2.css: 0889 `.housebook-presets` gap var(--space-3) -> var(--space-4) (10.5 px -> 14 px; the 12 px floor failed at 390-1920).
- App/app/static/host2.css: 0849 `.invoice-quick-stays` gap -> 0, `li + li` margin-top var(--space-4). Did not fix the defect below.
- docs/tasks/screenshots-0890/: stay-fees-390.png, invoice-picker-390.png, invoice-form-390.png, housebook-390.png.

## Commands (last lines)
1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0890_speed_pages_browser.py -q --tb=line -rs`: `14 failed, 16 passed in 41.91s` (0 skipped).
2. Screenshots with UBYHOST_SHOTS_DIR: `1 passed, 29 deselected in 5.29s`; four PNGs written.
3. `python3 scripts/design_lint.py`: `design lint: OK`.

## Results
- Passing: stay-fees 7/7, housebook 7/7 (after the gap fix), end-to-end test.
- End-to-end taps: stay fee 5 (open, confirm all, confirm in dialog, ZIP download, use this setup; Fee C rate equals Fee A); invoice 2 (picker, quick link); housebook 2 (Last month, URL has from= and to=). No /submit request.
- Failing: invoice-picker and invoice-form, 7 widths each (14 cases).

## Defects
1. Fixed: housebook presets 10.5 px gap (0889).
2. Open, real (0849): `.invoice-quick-stays` at 1024, 1280, 1440, 1920 px: the two link boxes touch (0.0 px vertical gap). Passes at 320-768. The CSS margin fix did not change it, so the cause is not the li spacing. Not located; needs a fix brief.
3. Open, pre-existing shared chrome (not in the new controls; the 0849 commit did not add them): skip link (180x43), "How does this work?" summary (317x23), back link "Invoices" (75x24), help-tip "?" (24x24), header "VI" control, bottom nav labels at 11 px ("Dashboard", "Stays", "Properties", "Cleaning", "More"). These fail geometry_findings on the invoice pages only. Needs a separate chrome brief.

## Deviations
- No commit, push or PR (owner instruction overrode the brief's per-step commits).
- 0888 skipped: no `[data-use-price]` check, no invoice price tap, no 0888 screenshot.
- Own `_open` helper instead of `_open_app`: `_open_app` appends `?lang=en` even when the path has a query, which breaks `/stay-fees?month=...`.
- s2 is a second make_stay stay, not a reservation in s1's apartment.
- Cleanup also deletes `alert` and `onboarding_dismissed_<owner>` (FK failure otherwise).
- Invoice-form geometry runs the new-control checks and then geometry_findings; the chrome findings fail that last assert.

## Questions / owner steps
- Owner: decide whether the chrome findings get a fix brief or the invoice pages are exempted (the exemption is a decision, not an executor call).
- Next executor: locate why the picker quick list has 0 px gap at >=1024 px (check the wrapping element's computed display and any desktop media rule for `.invoice-quick-stays` / `.ui-section` children).
