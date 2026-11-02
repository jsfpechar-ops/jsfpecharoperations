# 0546 report: cleaning phone layout from the mockup

Status: blocked (acceptance not met: browser differences remain, 13 regression failures not itemised)

## Done
- Step 1 (`0546 step 1`): `_cleaning_table.html` wraps desktop sections in `.cleaning-desk` and adds `.cleaning-phone` (grp, card for today, list rows for week/later). Copy key `next_arrival_short` added to `cleaning_i18n.py` and `host_vi_i18n.py`.
- Step 2 (`0546 step 2`): `cleaning.html` h1 `.big`, `.top` back button (`/menu`), `.actbar` with the share button.
- Step 3 (`0546 step 3`): cleaning CSS appended to `app2.css`; key `20261101-0546n`; `tests/static_versions.json` rewritten.
- Step 4 (`0546 step 4`): PAGES entry with `phone_view: uklid`, `phone_selectors`, and `missing_ok` for `main table th/td`.
- Step 5: regression run ran, 13 failed, 73 passed, 0 skipped reported. Failure names were not captured (no `-rf`); rerun needed.
- Step 6 (`0546 step 6`): `docs/tasks/screenshots-0546/` holds cleaning-320, 390, 768, 1024, 1280, 1440 PNGs. No uklid mockup shot was copied (glob matched nothing).
- Design lint: OK.

## Cleaning test (test_0710 `-k cleaning`): 3 failed, 9 passed
- 390 px, 13 differences:
  - `.tab.on` missing in app. Shell tab bar (`_shell_v2.html`), shared, not fixed.
  - `.big` height 47.8 vs 36.8 px. Shared `.big`/`.head h1` rule, not fixed.
  - `.sub` height 42 vs 21 px. Copy: the app subtitle is longer than the mockup's "Vzniká sám z odjezdů.".
  - `.card` height 57 vs 121 px, margin-top 0 vs 8. Fixture has no today item (empty card matched).
  - `.list .row` height 102 vs 103.2 px. Fixture row is amber, mockup green.
  - `.row .t .pill` colours and width. Fixture data state (warn vs ok).
  - `.actbar` padding-bottom 12 vs 30 px, height 75 vs 93 px. Shared `.actbar` rule: STOP per brief, not fixed.
  - `.actbar .btn` missing in mockup. Mockup uses `.bar .btn`; selector mapping, not fixed.
- 768 px, 8 differences: desktop view. `.head h1` 32 vs 24 px, `.head .btn` missing (hidden below 1024 by design), `main .card` radius and padding. Not fixed; these come from the desktop mockup view at 768, which the phone layout intentionally replaces.
- 320 and 1024/1280/1440: pass.

## Test entry notes
- The cleaning browser click tests report "`.actbar .btn` / tab intercepts pointer events" at some width. The shown failure log is truncated; the source test is unknown.

## Deviations
- No push, no PR (caller said do not push).
- No uklid mockup screenshot copied.
- Owner steps left: rerun step 5 with `-rf` to list the 13 failures; decide on shared `.actbar` padding and `.tab.on`.
