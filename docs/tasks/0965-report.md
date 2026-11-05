# 0965 report (B07: G02, G03, G04)

Status: review

## 1. Diff and commits

`git diff --stat 89772982 HEAD`: 11 files, 1382 insertions, 19 deletions (brief and report included).
Commits: `144a1c49` (step 8, settle wait), `171cd6ee` (step 9 report), `fc85ed5b` (status), `b7954474` (step 10, spacing CSS, manifest), step 11 and `0965 status` (this report).

## 2. The two unidentified failures

`test_the_readable_link_takes_the_group_through_the_same_flow[320]` and `[390]`. Same spacing guards as the group-of-three test: acknowledgement text 15.1 px from the notice edge; review label 4.5 px from a Change button; Save and Back 6.0 px apart; "Person 2 of 3" 10.9 px from Save at 768 px and up.

## 3. Spacing fixes (step 10, guards unchanged)

Before: 9 failed, 583 passed. Fixes, all in `App/app/static/guest.css`:
- Acknowledgement `.checkline` padding 14 px to 14 px 15 px: text 16 px from the notice edge (min 16).
- `.g-review-row dt` margin-bottom 2 px to 12 px: long labels no longer sit 4 px above the Change button (min 12).
- `.g-wizard-nav` margin-top 6 px to 12 px: Back is 12 px below Save (min 12).
- `.g-save-note` margin-bottom 8 px to 12 px: person line clears Save (min 12).
- Cache key `guest.css` 20261105-0965a to 20261105-0965b in `App/app/templates/guest/base.html`; `App/tests/static_versions.json` regenerated.

Side effect: review rows are looser (label to value 12 px). Rows still align and nothing clips.

## 4. Commands (fresh DB per run, UBYHOST_REQUIRE_BROWSER=1)

- 0965 group `-k 0965 -x -rs`: `19 passed, 26 deselected in 118.18s`. Skipped: 0.
- Guest and host geometry, `tests/test_guest_*.py tests/test_host_geometry.py -rfs`: before fix `9 failed, 583 passed, 0 skipped` (EXIT=1). After fix: `592 passed, 9 warnings in 459.31s`, EXIT=0. Skipped: 0.
- `tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py`: `16 passed in 16.78s`. Skipped: 0.
- `python3 scripts/context_lint.py`: `context lint: OK` (WARN lines are repo-wide open-brief names).
- `git diff --check`: clean.

## 5. Screenshots (named set inspected)

- Review closed, en-390, cs-390, en-768, cs-1280: five rows, label above value, Change on one right edge, long name and address wrap in the row, one divider per row, no frame. cs-390 shows "1. ledna 1980".
- Review open, en-390: legal text inside the same card, no second border. The sticky Save covers legal text while scrolling (expected).
- Attempted invalid, en-390: red row with pink fill. The native "Please check this box" bubble covers part of the acknowledgement text. Native behaviour, not changed.
- Checked, en-390 focus-checked: green row, no red or pink, dark focus ring.
- Focus empty, en-390: dark 2 px ring, box neutral. The checkbox has a faint coral halo from the global input style.
- Bottom, cs-390 and en-390: Save above a quiet Back link, nothing covered at rest.
- Saved, en-390: next-person form with the saved strip, no error colour.

## 6. Section 7 and deviations

Section 7 ticks were already set in the brief and still hold; the spacing items are now covered by passing guards.

Deviations and questions:
1. The acknowledgement row is out of frame in cs-390 and en-390 checked-legal-open; green was confirmed in en-390 focus-checked only.
2. Not viewed: cs-390 and cs-768 attempted-invalid, cs-768 and en-1280 focus, en-1280 attempted-invalid.
3. Checkbox focus halo is coral (global input style). Accept, or change?

## 7. Done and left

Done: steps 1 to 8, 10 and the report. No push, PR or merge.
Left: owner steps none. Orchestrator review of the label spacing change and question 3.
