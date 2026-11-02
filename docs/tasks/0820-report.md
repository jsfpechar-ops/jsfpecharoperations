# 0820 report

Status: review

## Files changed
- `App/app/static/app2.css`: appended block "0820 empty state v2" (`body.v2 .ui-empty` centred, `.ui-empty .ui-btn-group` flex centred). Cause: v2 pages load only tokens.css and app2.css, so host2.css 0176 never applied.
- `App/app/templates/base.html`: `app2.css?v=20261102-0820`.
- `App/tests/static_versions.json`: rewritten by `test_static_versions.py --write`.
- `App/tests/test_host_button_contrast_browser.py`: BUTTONS probe also matches `a.btn:not(.ghost)` (v2 stay-fees).
- `App/tests/test_host_list_cards_browser.py`: `fees` uses `.card.stays-desk` (>=1024 px) and `.stays-phone` (<1024 px); expectation for fees switches on viewport width, as properties does.

## Commands
1. `tests/test_design_guardrails_browser.py tests/test_host_button_contrast_browser.py tests/test_host_list_cards_browser.py`: 13 passed, 0 failed, 0 skipped (before: 3 failed, 10 passed).
2. `tests/test_0710_v2_mockup_match_browser.py -k "invoices or housebook or submissions or stay_fees"`: 45 passed, 0 skipped, plus `tests/test_static_versions.py` run on its own: 3 passed. The combined command in brief §6.2 gave 48 passed, but the `-k` filter also deselected the static-version tests, so they were run separately.

## Acceptance (§7)
- [x] 0 failed, 0 skipped.

## Deviations
- The brief's §2.1 cause was a v2 rule in app2.css. None existed. The real cause is that host2.css is not loaded on v2 pages. Fixed in app2.css as the brief allows.
- The list-cards test needed a logic line change (viewport split for fees), not only selectors.
- Not committed or pushed (user instruction). No PR opened.
- No screenshots taken: brief §7 does not require them.
- `docs/design/catalog.json` was already modified in the working tree before this task. Not touched by me.

## Questions
None.

## Owner steps left
- Review the diff, then commit and merge via `scripts/merge-pr-on-green.sh` (orchestrator commits).
