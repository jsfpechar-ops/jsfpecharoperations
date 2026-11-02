# 0505 report

Status: review
Brief: docs/tasks/0505-row-menus-help-tips-once.md (executor: Haiku 5.5)

## Files changed
- App/app/static/app.js: initRowMenus and initHelpTips bind once; shared state moved to rowMenuLastOpenAt and helpTipState.
- App/app/templates/base.html: app.js?v=20261101-0505.
- App/tests/static_versions.json: regenerated with --write.
- App/tests/test_0505_row_menus_help_tips_once_browser.py: new.

## Commands and tails
- node --check App/app/static/app.js (steps 1 and 2): no output, exit 0.
- Step 3 new test: `2 passed in 3.80s`.
- Brief §6 set (18 files from grep -rlE 'row-menu|help-tip' plus 0501 to 0505, static versions, wp07): `129 passed, 57 skipped in 504.55s`. All 57 skips were test_onboarding_wizard_browser.py ("browser not required"; UBYHOST_REQUIRE_BROWSER unset).
- Same file rerun with UBYHOST_REQUIRE_BROWSER=1: `85 passed in 140.87s`, 0 skipped.
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings are pre-existing open-brief notes).
- `git diff --stat origin/main`: 5 files, 222 insertions, 44 deletions (app.js, base.html, static_versions.json, new test, brief). Report added at the end.

## Page to selector table
| Page | Selector checked before second run |
|---|---|
| /reservations?lang=cs | .row-menu-trigger |
| /reservations/<stay>?lang=cs | [data-help-tip] (.help-tip-btn) |

## Deviations
1. Brief §4 step 3 asks for zero adds on document and window. Other inits (pointerdown, keydown, host:close-navigation, window resize) still add document/window listeners on a second run, which is out of scope. The test instead records the stack of each addEventListener call and asserts none comes from initRowMenus or initHelpTips. The stack check was not separately confirmed to fire on a known-bad case.
2. Running the browser tests rewrote 233 tracked PNG evidence files under docs/tasks/ (test screenshots). They were reverted with git checkout and not committed.
3. Onboarding wizard tests need UBYHOST_REQUIRE_BROWSER=1 for 0 skipped; the rerun above covers it.
4. No 390 px screenshot taken: no layout or template markup changed (version key only).
5. Not pushed, no PR opened (lead asked for no push).

## Questions
None.

## Owner steps left
- Review the branch task/0505-mixed-inits-b, then open the PR and merge via scripts/merge-pr-on-green.sh.
