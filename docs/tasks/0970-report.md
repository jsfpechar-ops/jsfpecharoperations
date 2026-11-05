# 0970 report (executor run, B12)

Status: blocked (row A did not finish; see Left)

## Duplicate-label finding and fix
- Cause: `App/app/templates/housebook.html`, popover "Signed" line, used `t('housebook.signed_yes')` / `t('housebook.signed_no')` as the value. Those keys read "Signed"/"Not signed" (en) and "Podepsáno"/"Bez podpisu" (cs), so the page showed "Signed: Signed" and "Podepsáno: Podepsáno".
- Reproduced with a temporary pytest probe (deleted): `<span class="muted">Signed:</span> <span class="pill p-ok">Signed</span>`.
- Fix (commit d34d2f44): value is now `t('customers.yes')` / `t('customers.no')`, the existing yes/no keys. Probe after fix: EN "Signed: Yes"/"No"; CS "Podepsáno: Ano"/"Ne".
- Other popover fields (date of birth, citizenship, document, residence, purpose): label shown once.
- Residual: VI has no yes/no keys, so the VI popover shows "Đã ký: Yes"/"No" (English fallback). Needs a VI translation decision (new text), not done here.

## CSV baseline
- `/tmp/ubyhost-b12/export-before.csv`: 740 bytes, sha256 82d62f0c9c38a0455ad25147061621654d955e94c1d540f2299ab5bd51900551. Recorded at 21:31, before the code patch file was saved; not re-recorded on the base commit in this run.
- `-k csv_export`: 1 passed, 0 skipped. Byte match holds.

## Commands (fresh UBYHOST_DB per run, UBYHOST_REQUIRE_BROWSER=1, UBYHOST_SHOTS_DIR=/tmp/ubyhost-b12)
- New 0970 file: 11 passed, 0 skipped.
- B layout lint `-k every_host_page`: 1 passed, 3 deselected, 0 skipped.
- C: 38 passed, 0 skipped.
- D: 76 passed, 0 skipped.
- E test_endtoend: 28 passed, 0 skipped.
- F context_lint: OK (warnings only), rc 0.
- test_static_versions: 3 passed.
- A geometry (3 files): NOT FINISHED. Killed twice (exit 144) after 2 tests. A third run (`test_host_geometry.py` alone) is still hung on its second test. Not a pass.
- `git diff --check`: clean. No tracked PNG changed.

## Acceptance (brief §7)
- [x] 11 passed, 0 skipped
- [x] CSV bytes equal baseline
- [ ] Row A geometry not confirmed
- [x] Surname and status readable (screenshots)
- [x] Details keyboard and Esc (test passed)
- [x] EN page has no Czech text (test passed)
- [ ] Rows A-F green: A not green

## Screenshots (post-fix, inspected)
- 390 en: stacked cards, no table, name and status readable. Pass.
- 390 cs: same, Czech labels. Pass.
- 768 en: stacked cards, no table. Pass.
- 1280 en: five columns plus actions inside card, no sideways scroll. Pass.
- 1280 cs: same, Czech. Pass.
- 1280 en open: "Signed: Yes" once. Pass.
- 1280 cs open: "Podepsáno: Ano" once. Pass.

## Deviations
- Earlier run went 29 tool calls past the brief's 25-call stop point (recorded here). This run had no budget.
- Added row A and a temporary probe file (deleted).
- The fix uses existing `customers.*` keys, as instructed.

## Left
- Row A (geometry): rerun `tests/test_host_geometry.py`, `test_host_wide_geometry_browser.py`, `test_0890_speed_pages_browser.py` in a fresh session.
- VI yes/no translation (owner or translator decision).
- Brief status stays blocked until A is green.
