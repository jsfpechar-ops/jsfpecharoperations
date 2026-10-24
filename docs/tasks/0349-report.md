# 0349 report: Review drafted cards (source line, discard)

Status: review

## Files changed

- App/app/guest_guide.py (discard_draft)
- App/app/routes/guest_guide.py (POST .../discard)
- App/app/templates/guest_guide_card.html (source line, discard form)
- App/app/host_i18n.py (_GUIDE_DRAFT_STRINGS, en and cs)
- App/tests/test_guide_drafts.py (new, 5 tests)
- docs/tasks/0349-report.md

## Commands

`cd App && .venv/bin/python -m pytest tests/test_guide_drafts.py tests/test_guest_guide*.py -q --tb=short`
    106 passed, 2 skipped (the 2 skips are pre-existing guest_guide tests, not browser tests)

`cd App && .venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_design_*.py -q --tb=short`
    3 failed, 149 passed, 31 skipped
    3 failures: tests/test_host_i18n.py (Vietnamese; "no such table: apartment"), known, predate this work.
    31 skips: Chromium is not installed in this container (`/opt/pw-browsers/chromium-1134` missing). Not run as browser tests here; the reviewer's CI should run them.

`python3 scripts/design_lint.py` -> design lint: OK
`python3 scripts/context_lint.py` -> context lint: OK (warnings only: catalog.json and RETENTION.md named by open briefs; 47 commits after last status update)

## Section 7 acceptance

- [x] Only the five files of section 3 change (plus the report).
- [x] test_guide_drafts.py: 5 passed.
- [x] Both lints OK.

## Deviations

- Commits: steps 1 and 2 are in one commit ("0349 step 1-2"), steps 3 and 4 in one commit ("0349 step 3-4"), step 5 and step 6 each have their own commit. Done in one session to save tool calls.
- Screenshot: taken at review by the orchestrator (390 px, a `check` card from Booking): source line in the banner, "Discard this draft" under More, scrollWidth 390.
- Browser tests: run at review with Chromium, test_design_*.py + test_guide_drafts.py 144 passed, 0 skipped.

## Questions

None.

## Owner steps left

1. Review and merge once CI is green.
