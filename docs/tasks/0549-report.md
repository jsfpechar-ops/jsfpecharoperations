# 0549 report

Status: blocked
Branch: claude/project-thread-c1h7ok (not pushed)

## Files changed
- App/app/templates/_cleaning_table.html: phone meta line and `.row small` print the check-in time only when set (lines 36, 46). Desktop untouched.
- App/app/static/app2.css: `body.v2 .cleaning-today{display:block;margin-top:8px}` in the 1023 px cleaning block. No colour fix (link colour does not show in the screenshot).
- App/app/templates/base.html: key `20261101-0547d` to `20261101-0549a`.
- App/tests/static_versions.json: `--write` (41 files).
- App/tests/test_cleaning_browser.py: fractional geometry parametrize drops the 1024 pairs (1280 pairs already existed); missing-hours test uses width=1280.
- docs/tasks/screenshots-0549/: cleaning-390.png, cleaning-1280.png, mockup-uklid-390.png.

Commits: a5634d5 (step 1), 9ac9cc5 (step 2), d676da3 (step 3), this report.

## Commands
- Step 1: `tests/test_static_versions.py --write` -> wrote 41 files.
- Step 2, set 1: `tests/test_cleaning_browser.py tests/test_0540_cleaning_tables.py tests/test_0541_cleaning_header.py tests/test_design_cleaning.py tests/test_cleaning.py tests/test_static_versions.py tests/test_host_language.py -q --tb=line -rf`
  tail: `81 passed in 49.34s` (no skips or failures).
- Step 2, set 2: `UBYHOST_REQUIRE_BROWSER=1 tests/test_0710_v2_mockup_match_browser.py -k cleaning -q --tb=short`
  tail: `FAILED ...[cleaning-320]`, `FAILED ...[cleaning-390]`, `FAILED ...[cleaning-768]`; `3 failed, 9 passed, 21 deselected in 47.92s`.
  - 390: `.tab.on` missing in app (shared); actbar padding and height (shared); `.card` height app 119 px vs mockup 121 px; `.list .row:has(.p-ok)` height 102 vs 103 px; `.row .t .pill.p-ok` width app 100.6 px vs mockup 114.6 px; `.actbar .btn` missing in mockup.
  - 768: header h1 size, `.head .btn`, `main .card` radius/padding/border colour (shared 768 item).
  - 320: security prompt (shared item, not inspected further).
- Step 3: `UBYHOST_SHOTS_V2=1 ... -k screenshots` -> `1 passed, 32 deselected in 19.15s`. `screenshots-0710` restored, cleaned.
- Mockup Uklid screen: `/tmp/uklid/uklid_shot.py` -> `ok`.
- `python3 scripts/design_lint.py` -> `design lint: OK`.

## Screenshot check
Looked at cleaning-390.png once: the today card is a proper box with its text inside. Rows read "next check-in 1 Nov" / "Tue 3 Nov · next check-in 3 Nov" with no "Time not set".

## §7 acceptance
- [x] Step 2 first set passes.
- [ ] Cleaning compare left with only the shared items. The 390 run still shows card height, row height and `.p-ok` pill width differences that are not on the shared list.
- [x] Lint OK.
- [x] Three screenshots (cleaning-390, cleaning-1280, mockup-uklid-390).

## Deviations
- Step 2: removed the 1024 parameter pairs instead of renaming them to 1280, to avoid duplicate cases. Coverage is the same.
- Did not push.

## Questions
- The 390 residual diffs (card height +2 px, row height +1 px, pill width 100 vs 115 px) may be a text or padding difference in the `.p-ok` pill. Fixing them means guessing at mockup CSS, so I stopped. Decide whether these are shared items or need a follow-up brief.

## Owner steps left
- Decide on the 390 residual diffs above.
- Push when ready: `git push origin claude/project-thread-c1h7ok` (not done by the executor).
