# 0150 report: stays and dashboard rows, part 2

Status: review

## Files changed
- App/app/templates/_components.html (onboarding_banner: Continue is ui-btn-secondary compact, Skip is ui-btn-quiet compact)
- App/tests/test_onboarding_wizard_browser.py (line 1424 assert now checks ui-btn-secondary)
- App/app/static/host2.css (appended 0150 setup-strip and phone chip-scroll rules)

## Commands (last lines)
- `.venv/bin/python -m pytest tests/test_setup_banner.py tests/test_design_stays.py -q --tb=short -x`: 7 passed, 1 warning
- `python3 scripts/design_lint.py`: design lint: OK
- Browser run (4 files listed in brief section 4 step 3): 2 failed, 19 passed. Failure 1 is the known local failure test_host_list_page_layout_browser properties [40,42]. Failure 2 is in test_onboarding_wizard_browser.py:1518 (see Deviations). Rerun of the onboarding test alone: 12 passed, 0 skipped.
- `UBYHOST_CAPTURE_0079=1 ... -k share_compact_row_menu`: 1 passed, 1 deselected
- ruff `--select E9,F63,F7,F82,F401,F841`: see tail output in the session (no findings reported)

## Brief section 7
- [x] Step 1 tests pass; design_lint OK after step 2
- [x] Step 3 listed tests: all pass except the known [40,42] failure; 0 skipped; docs/tasks/0079-evidence restored clean
- [x] Step 4 confirmed (below)

## By eye (screenshots)
- stays 1280 (/tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0150/stays-1280-cs.png): the only coral button is "Přidat pobyt". The setup strip is one white line with a bordered "Pokračovat v nastavení" and a plain "Přeskočit průvodce nastavením" at the right.
- stays 390 (.../shots/0150/stays-390-cs.png): chips are one row, cut at the right edge (scrollable). "Filtry" sits below. No chip on a second line. The setup strip wraps to two lines at 390 (button, then skip text), which the flex-wrap rule allows.
- 28-continue-setup (.../shots/0150/28-continue-setup-cs-1280-js.png): Continue is white with a border, one line, about 32 px tall.
- dashboard 390 (.../shots/0150/dashboard-390-cs.png): no coral setup button; the setup block is a warning card with a bordered "Dokončit nastavení" button.

## Deviations
- Test flake: test_onboarding_wizard_browser.py:1518 failed once with `assert False where False = is_hidden()` on `[data-page-skeleton]` after `window.ubyhostSkeleton.hide()`. It passed on rerun (12 passed). Not caused by this change; the assertion is about the page skeleton, not the strip.
- 28-continue-setup-cs-390.png does not exist. Copied 28-continue-setup-cs-1280-js.png (the first match for "28-continue").
- Commit trailer uses Co-Authored-By: Claude Haiku 5.5 per the session attribution reminder, not the Opus line in the orchestrator note.
- No PR opened and no push, per the orchestrator note.

## Questions
- None.

## Owner steps left
- None for this brief. Review and merge the branch via scripts/merge-pr-on-green.sh when ready.
