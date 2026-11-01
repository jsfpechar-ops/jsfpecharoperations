# 0527 report: stays list v2, tests and screenshots

Status: blocked

Done: step 0 (commit bf1cef19), step 1 partly (PAGES entry added, not passing).
Left: step 1 mismatches, step 2 old tests, step 3 screenshots.

## Commands
- Step 0: 0526 block in app2.css cut to page-only rules; 0718 duplicates removed; CSV row `csv.export_stays` added to `.stays-links`; key `20261101-0527a`; manifest written (41 files). Lint OK: `design_lint.py`, `context_lint.py`.
- Step 1: `pytest tests/test_0710_v2_mockup_match_browser.py -k stays`: 12 failed, 21 deselected (0 skipped). Tails:
  - `stays at 390 px: 18 style differences`
  - `stays at 1280 px: 4 style differences`
  - `stays at 1280 px: 20 findings`

## Mismatches found (not fixed)
- Phone `.top .round`: font-size 13.3 vs 15px, colour, padding 6px vs 0.
- Phone chips: `.chip` / `.chip.on` background and border are acc red, mockup is ink. Cause: `app2.css` line 56 has a global `.chip.on{background:var(--acc)!important}` (shared shell). Fixing it would change other pages, so it is not changed here.
- Phone `.row .pill` and desktop `main .pill`: colour follows the data tone (warn here), mockup shows the ok tone. Needs a data-dependent entry in `missing_ok` or a fixed fixture; not loosened.
- Phone `.list .row` border colour, height 101 vs 103 px; `.row .t` width 258 vs 250 px.
- Desktop: `main` has no `h1` at 1280 (`expected one h1, found 0`).
- Tap targets under 24/44 px on the desktop filter bar (selects, inputs, Apply/Create buttons, `stay-identity-link`, pagination Next/Previous). These are page controls, not the shell.
- Chip width 173 vs 123 px at 390.

## Deviations
- The step 1 PAGES entry is committed (not passing). It is the only failing change on this branch.
- Step 0 CSS: `--acc2` avoided; `.av` now uses the 0718 `--acc-text`.

## Questions / owner
- Decide whether the shared `.chip.on` !important rule (app2.css line 56) may change for all pages.
- Decide on the desktop filter-bar tap-target sizes (page change, not loosening).
- Decide how the data-dependent pill tone is covered in `missing_ok`.
- Steps 2 and 3 not started.
