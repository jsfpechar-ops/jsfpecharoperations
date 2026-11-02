# 0541 report

Status: review

## Files changed (addendum, step 6)
- `App/tests/test_cleaning_browser.py` (only file changed in this addendum)

Diff stat since the 0540 report commit (`10f754a`), all of 0541: 9 files, 120 insertions, 35 deletions. Section 3 files only.

## Assertions changed (existing tests)
1. `test_calendar_popup_types_create_in_place_and_localize_validation`: the opening block now clicks `[data-cal-create-type="cleaning"]`, asserts the cleaning type is pressed, switches to stay and checks the date moves to `#cal-arrival`, shoots `cleaning-stay-popup-cs`, switches back and checks `#cal-clean-date`. The rest is unchanged.
2. `test_cleaning_calendar_can_create_stay_and_refresh_turnover_in_place`: it opens via the cleaning control and then switches to stay before the stay assertions. This was not in the brief's list; it clicked the removed header "add stay" button (section 8, host `/cleaning` header button).
3. `_open_create_dialog` helper (used by `test_add_stay_and_cleaning_dialogs_open_centred_in_both_tabs`): for `kind="stay"` it opens the cleaning dialog and clicks the stay type choice. Same reason as item 2.

No shared-view test or other existing assertion changed.

## Commands (last lines)
Browser set, `-rs`:
```
39 passed in 126.66s (0:02:06)
```
(no skipped lines)

Unit set:
```
64 passed in 12.65s
```

Lints:
```
design lint: OK
context lint: OK
```
(context lint printed pre-existing WARN lines about open briefs and 12 App commits after status.md update; orchestrator item, not blocking.)

## Screenshots (390 px, /cleaning host, generated with UBYHOST_SHOTS_DIR=/tmp/0541-shots)
- `/tmp/0541-shots/cleaning-add-cleaning-390.png` (viewed; cleaning dialog, type switch present, header has no stay button)
- `/tmp/0541-shots/cleaning-add-stay-390.png`
- Also at 1280: `/tmp/0541-shots/cleaning-cleaning-stay-popup-cs.png`

## Deviations
- Assertion changes 2 and 3 are beyond the three named in the addendum. They are host `/cleaning` header-button assertions, covered by section 8, and each was needed to get the browser set to 0 failures.

## Questions
- None.

## Owner steps left
- Merge via `scripts/merge-pr-on-green.sh` after CI. No deploy needed for this step.
