# 0353 report

Status: review
Branch: task/0353-guide-translation (not pushed, no PR)
Migration: 0018_guide_translation.sql (lint said next free 0018; now 0019)

## Files changed
- New: App/app/migrations/0018_guide_translation.sql, App/app/guide_translate.py, App/tests/test_guide_translate.py, App/tests/test_guide_translate_browser.py
- Edited: App/app/static/guest.css (appended), App/app/routes/guest_guide_view.py, App/app/templates/guest/guide.html, App/app/templates/guest/base.html (guest.css ?v=20261024-0303), App/app/config.py, App/app/routes/guest_guide.py, App/app/templates/guest_guide.html, App/app/i18n.py, App/app/guest_uk_i18n.py, App/app/host_i18n.py (by script), App/tests/static_versions.json
- Docs: docs/ENVIRONMENT.md, docs/context/test-map.md, docs/plans/guest-guide.md (0353 todo to review)

## Commands (last lines)
- `pytest tests/test_guide_translate.py`: `11 passed, 1 warning in 3.06s`
- `pytest` (8 files incl. test_host_i18n.py, test_static_versions.py, test_privacy_first.py): `145 passed, 2 warnings in 22.89s`. The 3 known Vietnamese failures did not occur.
- `pytest tests/test_ai.py`: `8 passed, 1 warning in 0.31s` (0310's day-count failure did not occur)
- Browser (guide_translate_browser, guest_guide_browser, guest_leon_browser), UBYHOST_REQUIRE_BROWSER=1: `8 passed, 1 warning in 18.17s`, 0 skipped
- Browser design guardrails `-k every_host_page`: `1 passed, 9 deselected, 1 warning in 53.11s`, 0 skipped
- `ruff check ... --select E9,F63,F7,F82,F401,F841`: `All checks passed!`
- `design_lint.py`: `design lint: OK`
- `context_lint.py`: `context lint: OK` (WARN: 85 commits touched App/ after status.md; orchestrator updates status at review)

## Section 7 acceptance
- [x] test_guide_translate.py (11) passes; test names/cases as the brief lists are in the copied file (not audited line by line)
- [x] test_guide_translate_browser.py (1) passes, 0 skipped
- [x] `grep` for log lines with title/steps/text in guide_translate.py: 0; no em dash in the new files

## Deviations
- Steps 4 and 5 are in one commit ("0353 step 4"): the template edits were applied in the same script run.
- Step 6 config edit: my first attempt used a regex that deleted about 79 lines. I reset that commit on the branch (local only, before any push), then re-applied the edit by line index. Final config.py diff: 9 insertions, 3 deletions. Committed as "0353 step 6".
- guest_uk_i18n.py anchor: the brief shows 8 spaces; the file has 4 (`    "leon_error_reload":`), one match. The copied script uses 4 spaces for uk, so the script result is correct; nothing hand-edited.
- Step 4 anchor `response.headers.update(HARDEN)` occurs twice in guest_guide_view.py; the block went after the one that follows `response = render_guest(request, "guest/guide.html", context)`.
- Tests were run with -x as the lead asked, with test_host_i18n.py in the same run.

## Questions
None.

## Owner steps left
1. Merge with scripts/merge-pr-on-green.sh once CI is green (PR not opened: no push requested).
2. On staging, add guide_translate to UBYHOST_AI_FEATURES (e.g. guide_import,leon,guide_translate), save, restart; then check a live guide with ?lang=de after a minute.
3. Orchestrator takes the screenshot App/.screenshots/0303-guide-translated-de-390.png (not taken by the executor).
