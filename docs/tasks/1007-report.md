# 1007 report

Status: review

## Done

- Steps 1 to 7 committed locally (`1007 step 1` to `1007 step 7`, plus the step 1 fix commit).
- Step 8: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs`. Green, 0 skipped. Earlier stale run (pid 14460) killed first.
- Step 9: screenshots of /predplatne (active standard, monthly, lang=en) taken and viewed.
- Step 10: copied to `/mnt/project-files/ux-shots/wolt/billing-upgrade-390.png`, `billing-upgrade-768.png`, `billing-upgrade-1280.png`.
- Step 11: `python3 scripts/context_lint.py` returns `context lint: OK` (WARN lines are pre-existing notes).

## Commands (last lines)

- Step 8 layout lint: `....  [100%]`, `4 passed in 236.75s (0:03:56)`, `EXIT=0`.
- Step 8 full log: /tmp/claude-0/-home-user-jsfpecharoperations/19736c2f-d76f-5062-a390-a7e0df73a878/scratchpad/layout_1007.log
- Step 9 shots: temporary test file, deleted after use. Its teardown raised an FK error from the scratch fixture; the screenshots were already written.
- `python3 scripts/context_lint.py`: `context lint: OK`.

## Per page (what I saw)

- 390: Change card shows the Max upgrade tinted with a 1.5 px border and a full-width "Switch to Max" button. Yearly strip stacks, with "Pay yearly" full width below the text. TTLock add-on row is bordered with a full-width Add. Cancel card intact. No sideways scroll visible. The fixed bottom tab bar and help button sit over content only because a full-page capture places fixed elements mid-page.
- 768: Upgrade card and inline strip read cleanly. Add-on row and Cancel card intact. Same fixed-element capture effect at the bottom.
- 1280: Upgrade card, strip with inline button, add-on row and Cancel card all aligned in the content column. Nothing clipped.
- No CSS change made; nothing was clearly broken.

## Deviations

- Step 10 commit: no code changed in this run, so only the report is committed. The §3 files were already committed in steps 1 to 7; no 1006 files were uncommitted.
- Not pushed, no PR (brief §10).

## Owner steps left

- Review the three screenshots (UX gate, rule 10) before any merge.
- Push and open the PR yourself after review.
