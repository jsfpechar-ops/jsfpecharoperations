# 0715 report

Status: review

## Done
- Step 1 (commit 4c3353c): header links in one flex row without "·" separators; every Stav state is a pill; month line items wrap as whole units.
- Step 2 (commit 237fb74): calendar fallback label from i18n (`calendar.kind_stay`); `.todo` one column below 1024 px, check 8 updated; reduced_motion in test_0710.
- Step 3 (this commit):
  - `not_registered` (guests missing) renders `pill p-warn` (decision 2).
  - Mockup selector `main .pill` replaced by `main .pill.p-ok` and `main .pill.p-warn`; `main .pill.p-ok` added to `missing_ok` with reason "tone depends on data: the demo overview has no reported stay" (decision 1).
  - 320 px overflow: `@media (max-width:359px){body.v2 main table{table-layout:fixed}}` in app2.css. A padding-only rule at <400 px was tried and reverted: it broke the 390 and 320 style checks (mockup padding is 14 px).
  - test_0520: calendar marker is now `class="card cal ov-section"` (decision 4); order check kept.
  - app2.css key `20261101-0715` in base.html; `static_versions.json` regenerated (41 files).
  - Screenshots regenerated; committed only overview-390, overview-768, overview-1280 and mockup-today-1280. Other regenerated PNGs reverted.

## Test tails
- Section 6 command (7 files): `50 passed in 179.82s (0:02:59)`. 0 skipped (`-rs` printed no skip lines).
- `python3 scripts/design_lint.py | tail -1`: `design lint: OK`
- `python3 scripts/context_lint.py | tail -1`: `context lint: OK`

## Screenshots (what was seen)
- overview-390: header links on one row, "Clear demo data" on its own row, no orphan separator. Stav pill "Waiting for guest" yellow. Calendar bars in English ("Stay"). Remaining: the month line ends row 1 with a dangling "·" ("This month 1 guest · 12 nights ·" then "0 reported to the police"). Items stay whole, but the separator is orphaned.
- overview-768: "What needs you" is one column; sidebar present; no overflow.
- overview-1280: two-column "What needs you"; English labels; calendar bars "Stay"; Dnes/Today row has yellow "Waiting for guest" pill.
- mockup-today-1280 (Czech, different demo data): shows green "Hotovo, nahlášeno policii" and amber "Čeká na 2 ze 3 hostů" rows. The app demo has no reported stay, so the green pill is not in the app (covered by missing_ok).

## Deviations
- The 390 px dangling "·" in the month line is not fixed (not named in the brief's items).
- Padding-only 320 px fix was replaced by table-layout:fixed (see above).

## Owner steps left
- Decide whether the 390 px month-line separator needs a fix (small CSS/markup follow-up).
