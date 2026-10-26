# 0404 report: Leon setup wizard

Status: review

## Commits (branch claude/0403-leon-setup-wizard, not pushed)
- 0404 step 1: `leon.SETUP_STEPS`, `setup_step()` (3412c48)
- 0404 step 2: `routes/leon_setup.py` router, registered in `main.py` (c5ef36c)
- 0404 step 3: `guest_guide.py` leon redirects, `next=setup`, `from=leon` card flow (8dd9c3d)
- 0404 step 4: hidden `from` field in `guest_guide_card.html` (f157bab)
- 0404 step 5: overview card href (97cdb4a)
- 0404 steps 6 and 8: wizard layout and `static/leon-setup.js` in one commit (bbecfa5)
- 0404 step 7: step templates (4fe6f20)
- 0404 step 9: en/cs/vi copy (6b5746b)
- 0404 step 10: `tests/test_0404_leon_setup.py` (a95b863)
- 0404 step 11: browser test (c3f4dbd), 0396 browser test follows the redirect (c3d824f)

## Test results
- ruff (brief §6 line 1): All checks passed!
- Broad set (§6 line 2 plus test_0404 and test_0396 unit): 236 passed in 123.06s
- Browser (test_0404_leon_setup_browser, test_0396_leon_opt_in_browser, test_0404_leon_setup): 14 passed, 0 skipped
- `scripts/design_lint.py`: design lint: OK

## Screenshots (docs/tasks/screenshots-0404/)
switch-on-390.png, import-390.png, import-waiting-390.png, cards-390.png, try-390.png, done-390.png, import-1280.png
Looked at each once. Full-page captures show fixed-position overlays (the floating assistant button, the mobile tab bar, the "Add a second way in" sheet on switch-on, the import toast on the waiting page) and a fade mid-transition on cards. No overflow. 1280 footer Back and primary sit on one row.

## Deviations
- Step 8 is in the step 6 commit.
- The test fixture guide is live by default, so unit and browser tests patch `guest_guide.progress` to get the not-live and live states.
- Added `_leon_after_save()` in guest_guide.py and passed `from_leon` on the card-save validation error path, so a 422 from the wizard keeps its return link.
- Browser test uses `guest_guide.progress` patched live for the try and done steps (the brief said the fixture makes the guide live).
- Vietnamese copy is my own translation, not reviewed.
- 0396 browser test: one added `page.goto(.../leon)` before the banner assertion, since submit now lands on the wizard.
- Not run: `context_lint.py` (not in §6).

## Questions
- Commit trailer: the brief says `Co-Authored-By: Claude Opus 5.5`; the session attribution reminder says Haiku 5.5. I used the brief's trailer. Say which to keep.

## Owner steps left
None. Not pushed; PR and merge are the owner's.
