# 0402 report

Status: review

## Files changed
- App/app/templates/guest_guide.html: STATE tuple 'r' (line 26), topic badge td class="ui-cell-r" (line 32). Import section untouched.
- App/app/templates/guest_guide_quick_done.html: same two edits (lines 26, 32).
- App/tests/test_guest_guide_table_browser.py: new, extracted verbatim from the amended brief §4 step 2.
- docs/tasks/screenshots-0402/guide-table-1280.png and guide-table-390.png.
- docs/tasks/0402-report.md: this file.
No commit, no push (owner instruction). No CSS change.

## Commands (from App/ unless noted)
- `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_guest_guide_table_browser.py -q -rs --tb=short`
  ```
  ..                                                                       [100%]
  2 passed in 4.51s
  ```
- `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_guest_guide.py tests/test_guest_guide_pages.py tests/test_guest_guide_browser.py tests/test_design_guardrails_browser.py -q -rs --tb=short`
  ```
  ....................................                                     [100%]
  36 passed in 62.23s (0:01:02)
  ```
- `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841`
  ```
  All checks passed!
  ```
- From repo root: `python3 scripts/design_lint.py`
  ```
  design lint: OK
  ```
- From repo root: `python3 scripts/context_lint.py`
  ```
  WARN  docs/privacy/RETENTION.md is named by open briefs 0347-guide-import-fetch.md, 0350-leon-core.md; say which goes first
  next free: task 0403 | migration 0023
  context lint: OK
  ```
- Screenshot folders: no docs/tasks/screenshots-* other than 0402 changed; nothing to restore.

## §7 acceptance
- [x] 1280 px: all badges within 2 px, and all STATE headers within 2 px (separate groups; test passes).
- [x] 390 px: test passes; cards layout unchanged in the code (no CSS change). Badge position not re-inspected by eye.
- [x] guide-table-1280.png and guide-table-390.png produced.

## Deviations
Earlier run (before the brief amendment) compared headers and badges in one set and failed at 17 px spread because th and td have different side padding (20 px vs 16 px). The amended §4 step 2 checks the two groups separately; no other change.
The brief file docs/tasks/0402-guide-table-align.md shows as modified in the working tree; this is the owner's amendment, not executor work, and was not committed.

## Questions
None.

## Owner steps left
- Review, then commit and push the branch (executor did not commit or push).
