# 0802 report: guest guide (v2)

Status: blocked (30-call cap reached; one related test still fails)

## Files changed (not committed; orchestrator commits)
- App/app/templates/guest_guide.html (index)
- App/app/templates/guest_guide_card.html
- App/app/templates/guest_guide_quick.html
- App/app/templates/guest_guide_quick_done.html
- App/app/templates/guest_guide_qr.html
- App/app/static/app2.css (one block appended, comment `/* 0802 guest guide (v2) */`, plus 2 later Edits inside that block)
- docs/design/catalog.json (8 new class names added)
- Not changed: tests (test_0800 already had the guest-guide routes), public_guide.html, templates/guest/.

## Test results
- `tests/test_0800_v2_remaining_pages_browser.py -k "guest-guide or guest-guide-quick"`: 12 passed, 0 skipped (before the last CSS change, all widths 320-1440; the 390/1440 screenshot run also passed 10 of 10).
- `python3 scripts/design_lint.py`: OK.
- Related `test_guest_guide*.py`, `test_quick_answers.py`: 53 passed before the last CSS change.
- `tests/test_quick_answers_browser.py::test_the_chips_are_big_full_width_and_show_their_state`: FAILS (last tail: `assert (340 - 50) >= (316 - 2)`). The chips are 44 px tall now and in a 3-column grid, but the chip row is 26 px narrower than the form. Likely the fieldset or its grid container still has about 26 px of inset. Not fixed.

## Screenshots
docs/tasks/screenshots-0800/guest-guide-390.png, guest-guide-1440.png, guest-guide-quick-390.png, guest-guide-quick-1440.png, and the other widths in the same folder. NOT viewed by me (tool budget). Owner or orchestrator must look at the 390 PNG of each page before merge.

## Deviations
- Header: each page writes its own `.head` (h1 + sub) in the body, as cleaning.html does. Primary action is one coral `.btn`. Other header actions are plain links (index) or `.btn.line` (quick done).
- Phone: the QR link is `ph-hide` on the index. Quick and questions links stay.
- Phone item rows: CSS only (the table markup is kept; no `.list.plain .row` markup change).
- Quick chips: inline-styled via app2 (workflow.css is not loaded on v2).

## Questions
- The brief refers to sections "§6, §7, §8" that do not exist in the file. I followed the test commands and the Finish step.

## Owner steps left
- Fix the chip row width in the quick page (see the failing test above), re-run `tests/test_quick_answers_browser.py`, view the 390 PNGs, then commit.
