# 0151 report

Status: review

Branch: claude/project-thread-td6fpc (not pushed, no PR). Base 5b10d6a.

## Commits
- 6693758 0152 step 1: wait for the deferred skeleton hide (`skeleton.wait_for(state="hidden", timeout=2000)`) before `assert skeleton.is_hidden()`.
- 0151 report (this commit): K-T02 row in known-issues, this report.

## Commands (last lines)
- 0152 step 1: `pytest tests/test_onboarding_wizard_browser.py -k phone_guest_sharing_and_clear_setup_actions` gives `12 passed, 58 deselected`. Ruff `E9,F63,F7,F82,F401,F841`: `All checks passed!`.
- 0151 step 4, eight files: `102 passed, 1 warning in 474.05s (0:07:54)`, exit 0, no skipped, no failed.
- Capture 0079 `share_compact_row_menu`: `1 passed, 1 deselected`.
- Evidence folders restored with `git checkout -- docs/tasks/0102-evidence` and `docs/tasks/0079-evidence`. Nothing from them is committed.

## Acceptance (§7)
- [x] Step 2 passes with 0 skipped (102 passed).
- [x] Step 3 report written.

## By eye
- `wizard-calendar-390.png`: "Přidat kalendář" is whole and readable, nothing overlaps it, and the bottom tab bar sits below it.
- `stays-390.png`: one card per stay; stay names on one line; badges in a row under the dates; property left and guest count right; menu button top right; no horizontal scroll visible.

## Screenshots
- /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0151/wizard-calendar-390.png
- /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0151/stays-390.png

## Deviations
- The skeleton assertion did not fail on the eight-file run, so no rerun was needed.
- Step 5 known-issues row added as K-T02 (after K-T01).

## Questions
None.

## Owner steps left
- Review and open the PR for branch claude/project-thread-td6fpc (not pushed by the executor).
