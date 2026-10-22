# 0235 report: Round 1 verification

Status: review

## Files changed
- docs/tasks/0235-round1-verification.md (Status line only)
- docs/tasks/0235-report.md (this report)
No app code changed. Scratch and screenshots: /mnt/project-files/foolproof-round1/{en,cs,vi}/ and /tmp/claude-0/0235-run2.txt.

## Step 1: old app worktree
Created /tmp/claude-0/oldapp at origin/main (fea8bee). Removed in step 7.

## Step 2: browser and geometry tests
Run with UBYHOST_REQUIRE_BROWSER=1 (see Deviations). Last lines:
```
FAILED tests/test_onboarding_wizard_browser.py::test_wizard_journey_and_geometry[390-en] (and 390-cs, 1280-en, 1280-cs)
FAILED tests/test_onboarding_wizard_browser.py::test_full_wizard_clickthrough_keeps_police_and_guest_settings
FAILED tests/test_onboarding_wizard_browser.py::test_phone_guest_sharing_and_clear_setup_actions (all 12 params: False and True x 360, 390, 1280 x en and cs)
FAILED tests/test_host_list_layouts_browser.py::test_stays_pills_and_deadlines_stay_on_one_line
18 failed, 106 passed, 0 skipped, 735.54s
```
Without the env var the same set gave `1 failed, 81 passed, 42 skipped` (skips are "browser not required").

Failure notes (first lines only):
- test_stays_pills_and_deadlines_stay_on_one_line: `('en', 1280, {'pill': True, 'deadline': True, 'height': 122, ...})`, `assert 122 <= 100`. A stays row is 122 px tall, so the one-line rule fails at 1280.
- test_phone_guest_sharing_and_clear_setup_actions: `.setup-wizard-foot button[value=skip]` count is 0 on `/apartments/N/setup/door_lock`, expected 1.

## Step 3: non-browser tests
`80 passed, 2 warnings in 9.82s`

## Step 4: screenshots
- en: `45 shots, 0 with problems`, EXIT 0
- cs: `45 shots, 0 with problems`, EXIT 0
- vi: `45 shots, 0 with problems`, EXIT 0 (no refusal of `--lang vi`)
The tool wrote 45 shots per language (not the 54 a full grid would give). I did not check which combinations are missing.

## Step 5: geometry report
report.json for en, cs and vi: 45 entries each, no entry with problems. Result: none.

## Step 6: EN key shots
- reservations-1-390.png: the bottom tab bar appears in the middle of the page, under "Back to stays". This is probably a fixed nav in a full-page capture, not confirmed. Otherwise the stay, guest form tracker, guest list, police reporting and stay settings render without cut text.
- reservations-1-1280.png: clean. Sidebar, step tracker, guests, police reporting and stay settings all visible, no overlap.
- apartments-1-setup-door-lock-390.png: the heading "Set up Vivus Apartment with" is cut off under the bottom tab bar, which looks like the same fixed-nav capture effect. Needs an owner look in a real phone view.

## Step 7: cleanup
`git worktree remove --force /tmp/claude-0/oldapp` ran.

## Acceptance (section 7)
- [ ] Step 2: 18 failures, quoted above. Not all passed.
- [x] Step 3: 80 passed.
- [x] Screenshots saved for en, cs, vi.
- [x] Geometry problems listed: none in report.json.

## Deviations
- Step 2: the brief command omitted `UBYHOST_REQUIRE_BROWSER=1`, which CI sets. Without it 42 tests skipped. I reran the same command with the variable set so skips became real results (0 skipped).
- Done: steps 1 to 7. Left: none.

## Questions
- Are the 18 failures (onboarding wizard and the stays row height) expected at this commit? I did not fix app code, per the brief.
- Is the mid-page tab bar in the 390 shots a capture artifact or a real layout bug?

## Owner steps left
- Decide on the 18 failing browser tests before round 1 is considered verified.
- Check the 390 px door-lock shot on a real phone (heading under the tab bar).
