# 0350 report: Leon (AI) core

Status: review

## Files changed
- Created: App/app/migrations/0017_guest_chat.sql, App/app/leon.py, App/app/routes/guest_leon.py, App/tests/test_leon.py, App/tests/eval/leon_cases.json, App/scripts/leon_eval.py (copied from docs/plans/0350-files/, unchanged)
- Edited: App/app/main.py (import and register router), App/app/i18n.py and App/app/guest_uk_i18n.py (20 leon_* keys via add_leon_i18n.py), App/app/cookie_inventory.py (ubyhost_leon), App/app/retention.py (guest_chats step), App/tests/test_privacy_first.py (crawl plus cookie name), docs/privacy/RETENTION.md, docs/ENVIRONMENT.md, docs/context/test-map.md, docs/plans/guest-guide.md (0350 row: review)

## Migration
0017 (lint said next free 0017 at start; now 0018).

## Commands (last lines)
- `pytest tests/test_leon.py`: `40 passed, 1 warning in 8.83s`
- `pytest tests/test_privacy_first.py ... tests/test_*_i18n.py`: `190 passed, 2 warnings in 14.96s` (no failures; the three test_host_i18n Vietnamese failures did not occur)
- `pytest tests/test_ai.py`: `8 passed, 1 warning in 0.27s`
- `scripts/leon_eval.py --offline`: `offline: case file OK`
- `python3 scripts/context_lint.py`: `context lint: OK` (warns about 44 App/ commits since status.md; orchestrator to update)

## Acceptance (section 7)
- `grep -c 'def validate' App/app/leon.py` = 1; test_leon 40 passed.
- test_privacy_first and test_cookie_inventory pass with ubyhost_leon in the set.
- Log-text grep = 0.
- Em dash grep = 0 in all three files.
- Not run: screenshot (brief has no UI change; none taken).

## Deviations
- Step 8 was first applied with a wrong anchor, reverted with git checkout before any commit, then reapplied correctly. Final file matches the brief.
- Step 9: an extra blank line was removed so the new function has two blank lines before the next comment (PEP 8). No other text changed.
- Review fixes: lint (2 unused variables), history text cleaned so stored guest text cannot close its tag (test extended), busy guard released only by the request that took it.

## Questions
None.

## Owner steps left
From the brief's Owner steps: merge with scripts/merge-pr-on-green.sh once CI is green; on staging add `leon` to UBYHOST_AI_FEATURES and set UBYHOST_AI_KEY_DAILY_USD_LEON to 0.05; run leon_eval.py with a staging key and send the output to the orchestrator (ship only on PASS); production stays off until 0351 and 0352 are merged.
