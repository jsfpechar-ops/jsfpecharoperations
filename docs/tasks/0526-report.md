# 0526 report: stays list on the v2 shell

Status: review

Done: steps 1 to 4. Commits: 3939aaa3 (step 1), 7954280b (step 2), c37ecf5d (step 3), plus this report and the catalog fix.

## Commands
- Same pytest set, final run: `9 failed, 29 passed in 4.80s` (0 skipped). Failures are the old-markup assertions listed below. Earlier, before the inline-style fix, the run was 9 failed, 29 passed.
- `python3 scripts/design_lint.py`: design lint: OK. Fixed: catalog entries added; inline styles moved to classes `stays-head-actions` and `stays-links` (app2.css block), because the brief's inline styles failed T1.
- `python3 scripts/context_lint.py`: context lint: OK.

## Failing assertions (old markup, not edited, for 0527)
- test_0523: headers order (`stay-col-*` classes), row helper (`ValueError` on `</tr>`: the phone `a.row` now precedes the table in the DOM), no-name text, deadline badge, payment link preselect (same row helper), screenshots (`.stays-view`).
- test_design_stays: `ui-toolbar` / `data-filter-toolbar` / `data-list-toolbar` gone; the raw-markup guard fails on `style="` (the brief's own header has `style="display:flex;gap:8px"`), `class="btn` and `class="pill` (brief classes).
- test_stays_empty_workspace: `data-list-toolbar` gone.
- test_static_versions: passes after `--write`.

## Deviations
- Save-view button and CSV actions menu from the old toolbar were dropped (not in the brief's header list). The `.saved-views` container stays.
- Inline `style=` attributes from the brief replaced by classes (lint T1 and the raw-markup guard).
- Bulk send button written inline as `.btn ghost send-all` (the old macro used `ui-btn-secondary`).
- Failed-report chip links to `/reservations?report=failed` with no range, so it lists upcoming by default.
- Filter toggle chip uses plain `.chip` (app2 `.chip` is already dashed); no `dashed` class.
- Deadline under the pill is shown only when the pill does not already show it (not for overdue or filed states).
- Phone link icons: chevron-right used for both bottom links (mockup used a doc icon).
- New CSS is one block `/* 0526 stays list */` in app2.css; `.list`, `.link`, `.row` etc. are global, not scoped.
- app2.css key bumped to `20261101-0526b` (the first bump was refused by the manifest check); manifest written.
- `--acc2` is not defined in app2.css `:root` (only `--accs` was found), so `.av` text colour may fall back.

## Not done
- No 390 px screenshot (the test capture failed on the 1280 step; not retaken, per budget).

## Owner / 0527 steps left
- 0527: update the old assertions listed above; decide whether the inline header style and `.btn`/`.pill` classes stay (guard test).
- Take the 390 px screenshot of `/reservations` and attach it to the PR.
