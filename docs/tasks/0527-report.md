# 0527 report: stays list v2, tests and screenshots

Status: blocked

Done: step 0 (bf1cef19); step 1 (420e13a2: one h1, Czech path, chevron 20, head actions hidden below 1024, key 20261101-0527c, manifest 41 files). Left: step 2 (old tests) and step 3 (screenshots). Steps 2 and 3 need a new session.

## Step 1 result
`pytest tests/test_0710_v2_mockup_match_browser.py -k stays -q --tb=no -rfs`: 3 failed, 9 passed, 0 skipped. Geometry passes at 320-1440 (1024 overlap gone with the upcoming range). Phone h1 is the single `.head h1` at every width.

## Remaining mismatches
- Waiting on shell (Overview thread): `.top .round` font-size, colour, padding (0718); `.chip.on` red background and border (app2.css global `!important`); `.head h1` 32 px and `.head .btn` styling at 768.
- Expected by decision 3 (not a bug): at 768 the table and head buttons are hidden, so `main table *`, `main td small` and `.head .btn` are missing in the app when compared with the desktop mockup. Table is not visible at 768.
- Row (`.list .row`): app uses `<a class="row">` (must link), mockup uses `<button>`. Border colour (text colour in app) and height 101 vs 103 px remain; `.row .t` 184 vs 180 px at 320 (4 px). Listed, not fixed with CSS on shared classes.
- Pill width `.row .pill.p-warn` 122 vs 161 px: label text differs from mockup copy. The shared test does not accept missing_ok for width mismatches, so this stays failing (not loosened).

## Step 2 (not done)
Old stays tests run once in this session: the run was cut at the 120 s tool limit and moved to the background (task bhvdhb4a0). Output shows many ERROR lines in unrelated browser tests (sidebar, a11y, design guardrails, host wide geometry) with no detail, plus FAILED entries in the list-page tests. Next session: run one file at a time with `--tb=short` to find whether the errors are a fixture problem.

## Commands
- `pytest tests/test_0710_v2_mockup_match_browser.py -k stays -q --tb=no -rfs`: `3 failed, 9 passed` (see above, 0 skipped).
- `pytest tests/test_static_versions.py -q --tb=line -rs`: `3 passed`.
- Design and context lint not run.

## Deviations
- Stays path is `/reservations?range=upcoming&lang=cs`, not `range=all`. The template has no "all" chip, so `range=all` shows no `.chip.on`; the mockup's selected chip is "upcoming". Czech labels now match (the test appends `?lang=en`, so `lang=cs` was not used alone).
- Phone h1 is `<h1 class="big">` on the `.head` h1 (no separate phone h1). Head is shown below 1024 as `display:block`, and the shell underline `.head h1:after` is hidden for `.stays-head` below 1024 (page-scoped; mockup phone h1 has no underline).
- `.chevron-right` icon size 16 changed to 20 (mockup `svg.chev`).
- Pagination and filter tap sizes from earlier step kept.

## Questions / owner
- Shell (Overview thread): approve `.top .round`, `.chip.on` !important, and `.head h1` / `.head .btn` below 1024.
- Copy: approve chip and pill label length (owner).
- Confirm `range=upcoming` as the stays test fixture.
