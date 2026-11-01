# 0504 report

Status: review (not pushed; no PR opened, per owner instruction "do not push")

## Files changed
- App/app/static/app.js: initSubmitGuard, initDetailsLinks, initUnsavedForms follow the claimNode rule. initUnsavedForms beforeunload reads the guarded forms at event time and uses form._ubySubmitting.
- App/app/templates/base.html: app.js?v=20261101-0504
- App/tests/static_versions.json: via --write
- App/tests/test_0503_page_inits_once_browser.py: guard expectation is now ["invalid"] only
- App/tests/test_0504_mixed_inits_once_browser.py: new

## Commands and tails
- pytest (brief §6 set, from App/): `54 passed in 55.32s`, 0 skipped
  Files: 0504, 0503, 0502, 0501, 0284, 0399, static_versions, wp07_cache_heartbeats, plus grep matches test_host_unsaved_changes_browser.py and test_property_navigation_browser.py
- `node --check App/app/static/app.js`: rc 0
- `python3 scripts/context_lint.py`: `context lint: OK` (WARN lines are pre-existing)
- `git diff --stat origin/main`: 6 files (app.js, base.html, static_versions.json, 0503 test, 0504 test, brief 0504). The report is added on top.

## Page to selector table
| Page | Selector checked |
|---|---|
| /reservations?lang=cs | `.action-panel form` |
| /apartments/{id}?lang=cs | `form[data-unsaved-guard]` |
| /reservations/{id}?lang=cs | `[data-open-details]` |

## §7 ticked
- [x] All pass, 0 skipped
- [x] diff stat lists only section 3 files and the brief
- [ ] Screenshots: not taken (no template or CSS change)

## Deviations
1. `initPropertyViews` also re-binds a window `hashchange` (app.js ~2127), which the brief did not list. The new test allows exactly one `hashchange` on pages with `[data-property-views]`. Brief 0505 should make this zero.
2. The behaviour test dispatches an `input` event on the first guarded form instead of typing. On /apartments that form has no visible field. The same `mark` handler runs.
3. Done: steps 1 to 4. Nothing left for the executor.

## Questions
None.

## Owner steps left
1. Push: `git push -u origin task/0504-mixed-inits-a`
2. Open the PR, then merge with `scripts/merge-pr-on-green.sh` once CI is green.
