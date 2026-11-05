# 0960 report

Status: blocked

## Reason

Command 4 (`pytest tests/test_cleaning*.py -q -x`) fails after step 1. The test
`tests/test_cleaning_browser.py::test_add_stay_and_cleaning_dialogs_open_centred_in_both_tabs[1280-800]`
asserts that the Add stay and Add cleaning dialogs share the same top edge (within 8 px). Measured: stay top 75.5 px, cleaning top 151 px. Both are centred at cy=400, so the heights differ by about 151 px. The likely cause is the brief's first new rule, `#calendar .cal-create-popover > form { min-height:0; }`, which removes the fixed height that made both modes equal. This is an inference from the numbers, not confirmed by a separate run. The test was not changed. The brief says to stop at a failing command after one fix, and any fix needs a CSS choice the brief does not cover. The test ran only once (`-x` stopped it); I did not re-run it. Commands 5 and the rest of command 4 were not run because of the tool-call cap.

## Commands

| # | Command | Result |
|---|---|---|
| 1 | `test_dashboard_calendar_browser.py -k "0960 or 0958 or reclamps"` | 26 passed, 0 failed, 0 skipped |
| 2 | `test_dashboard_calendar.py test_calendar_*.py test_sample_calendar.py` | 64 passed, 0 skipped |
| 3 | `test_dashboard_calendar_browser.py` (full) | 63 passed, 0 skipped |
| 4 | `test_cleaning*.py -x` | 55 passed, 1 failed (the test above), stopped by `-x` |
| 5 | `test_static_versions.py test_wp07_cache_heartbeats.py` | not run |
| 6 | `python3 scripts/context_lint.py` | OK (existing WARN lines about open briefs only) |

## Commits (branch codex/0960-b02-calendar-create, not pushed)

- a79c4ff3 0960 step 1
- e2de183d 0960 step 2
- 264f1eff 0960 step 3
- this commit: report and status line (blocked)

## Screenshots (in /tmp/ubyhost-b02, from command 1)

- calendar-0960-dashboard-stay-en-390.png: Add stay sheet; Cancel is white with grey border on the left, Create stay coral on the right, one row; Label is light-bordered and matches Guests; the Guests field has a red outline.
- calendar-0960-dashboard-cleaning-en-390.png: Add cleaning; Cancel and Create cleaning on one row; no empty block under the form.
- calendar-0960-cleaning-stay-en-390.png: Cleaning page, Add stay; same row layout and no clipping.
- calendar-0960-cleaning-cleaning-cs-390.png: Add cleaning (CS); "Zrušit" and "Vytvořit úklid" fit on one row.
- calendar-0960-dashboard-stay-en-768.png: centred dialog; row layout correct.
- calendar-0960-cleaning-cleaning-cs-768.png: centred dialog; CS buttons fit.
- calendar-0960-dashboard-stay-en-1280.png: centred dialog; row layout correct.
- calendar-0960-cleaning-cleaning-cs-1280.png: centred dialog; CS buttons fit.
- calendar-0960-dashboard-stay-cs-1280.png: "Zrušit" and "Vytvořit pobyt" fit on one row.

Not inspected: the other 15 of 24 screenshots.

## Acceptance (section 7)

- [x] Step 1 applied with `git apply --check` clean; commits 0960 step 1..3.
- [ ] Commands 1 to 6 green: 1, 2, 3 green; 4 failed; 5 not run; 6 green.
- [ ] Section 6b: nine named images viewed; the bullets were not checked against the other 15.
- [ ] `git diff de537cb3 --stat`: not run.
- [x] Nothing printed from guest data.

## Questions

1. Should the centring test be updated, or should the dialog keep equal heights (a `min-height` on the form, as before)? Both are outside this brief.
