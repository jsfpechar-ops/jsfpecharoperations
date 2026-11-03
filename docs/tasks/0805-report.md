# 0805 report: test fixes after 0800-0804

Status: blocked (checkpoint at the tool-call cap; Done: steps 1 to 3. Left: step 4, the setup-wizard failures)

## Files changed (not committed)
- App/app/templates/_components.html: in onboarding_welcome, v2 step list, added the "Add a stay by hand" link (onboarding.calendars.manual -> /reservations#add-stay-panel) for unfinished steps that have manual_url. Restyle only; the link is back on /onboarding.
- App/app/static/app2.css: `/* 0802 guest guide (v2) */` block, `.quick-choice-option` padding changed from `0 12px` to `0`, so the chip span fills the option width. Not yet verified by a passing run.
- App/tests/test_design_shell_browser.py: added "/apartments/new?lang=en" to the v2 branch list in test_more_preserves_each_page_kind_and_sheet_links_work (it now checks the v2 Menu tab instead of the More sheet, as for / and /reservations).

## Test results
- Run 1 (before the CSS and test edits were all in effect): `tests/test_onboarding.py tests/test_quick_answers_browser.py tests/test_design_shell_browser.py tests/test_onboarding_wizard_browser.py`: 49 failed, 68 passed. All 49 failures are in tests/test_onboarding_wizard_browser.py (test_phone_guest_sharing_and_clear_setup_actions, test_choice_card_selects_from_anywhere, and others in that file). The failures in the other three files were not listed in the tail that was read.
- Run 2 (with all edits): 46 failed, 71 passed in 280.81s. Output in the scratchpad at run2.txt. The remaining failures are in tests/test_onboarding_wizard_browser.py (example: line 1553, `assert 'auto' != 'auto'` on /apartments/115/setup/automation). Per-test list not yet triaged.
- Not run: tests/test_0800_v2_remaining_pages_browser.py (must stay 90 passed), scripts/design_lint.py.

## Failure fixes
- Failure 1 (Add a stay by hand): fixed as above, not yet confirmed by a passing run.
- Failure 2 (chips width): CSS padding change as above, not yet confirmed.
- Failure 3 (/apartments/new More sheet): test list change as above, not yet confirmed.
- Failure 4 (setup wizard, 49 failures): NOT FIXED. Not investigated, because the checkpoint was reached. Next step: run `tests/test_onboarding_wizard_browser.py -q -rs --tb=short` and decide per failure between a v2 restyle bug in the `/* 0801 setup wizard (v2) */` block and an old-shell colour assertion.

## Deviations
- Commit was not done, per the brief's instruction ("Do not commit").
- Tests ran in parallel for a short time (run 1 was still going when run 2 started). Results of run 1 may be mixed with edits.

## Owner or next executor steps
- Continue from step 4 with a new session; rerun the four-file command and the 0800 file (90 passed) and design_lint.
