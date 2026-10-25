# 0328 report: Guide Dashboard, Settings and security, Archive, Data requests

Status: blocked
Done: steps 1 to 9. Left: step 10 (look once at the four new 390 px screenshots, commit them, then commit this report with the sentences per screenshot).

## Files changed
- App/app/guide_i18n.py: corrected guide.settings.body (en, cs); 41 new keys in en and cs.
- App/app/templates/guide.html: sections list; Dashboard steps and trouble list; Settings when, login, three steps blocks (#settings-passkey, #settings-twofa, #settings-email), trouble list; sections #archive and #privacy_requests.
- App/tests/test_guide.py, App/tests/test_guide_browser.py: section lists.
- docs/tasks/screenshots-guide/: four new PNGs (guide-overview, guide-settings, guide-archive, guide-privacy_requests at 390 px), not committed yet.

## Commands (last lines)
- Keys check (step 3): `41`
- test_guide.py -k same_keys: `1 passed, 2 deselected`
- test_guide.py: `3 passed`
- cmd1 (test_guide, test_host_i18n, test_no_em_dashes, test_copy_cleanup): `30 passed, 1 warning`
- cmd2 test_guide_browser.py -rs: `2 passed in 5.94s` (0 skipped)
- cmd3 design_guardrails and a11y browser tests: `14 passed in 107.63s` (0 skipped)
- context_lint: `context lint: OK`

## Section 7
- [x] Settings sentence no longer mentions a password, en and cs.
- [x] Dashboard and Settings have when, steps and trouble list; #settings-passkey, #settings-twofa, #settings-email present.
- [x] Archive and Data requests sections added after Settings and in the side navigation list.
- [ ] Four screenshots looked at (not yet; session stopped at the tool-call limit).
- [x] en and cs keys match; no dashes in the new copy; browser tests 0 skipped.

## Deviations
- Step 1: no checkout, the branch task/0328-guide-dashboard-settings-archive was already checked out in the worktree; the grep check printed 2 and 0.
- Step 3 expected count 40; the block as written defines 41 keys (all listed in the brief, each once). Used the block unchanged.
- Browser env: chromium-1243 path (from the executor instructions) instead of chromium-1194 in the brief.
- The browser test rewrote 7 tracked screenshots; restored them with git checkout, so they are not in this commit.
- Step 10 incomplete: the four new screenshots are untracked and unviewed.

## Questions
- Step 3 key count: 40 or 41? The block itself is correct per the brief's list; confirm.

## Owner steps left
1. Follow "Log in with a passkey" on staging and say if a label differs.
2. Read "Data requests" and say if you want more on how to answer one.
