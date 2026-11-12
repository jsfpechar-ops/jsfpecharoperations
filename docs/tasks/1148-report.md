# 1148 report

Status: review

## Files changed (vs b49c0c17)

- App/app/icalsync.py: imports (json, timezone, alerts already imported), `_pointed_at_open_submission`, `_running_submission_covers_stay`, `_running_defers_cancel`, `_alert_if_filing_in_doubt`, `RUNNING_CANCEL_DEFER_SECONDS = 30 * 60`; event and sweep call sites.
- App/app/host_i18n.py: en and cs `cancelled_filing_unconfirmed` title and detail.
- App/app/host_vi_i18n.py: vi title and detail.
- App/tests/test_icalsync.py: imports, helpers, 6 new tests.
- App/tests/test_alert_language.py: one STORED_KINDS entry.
- docs/OPERATIONS.md: one alert kind row.
- docs/tasks/1148-ical-cancel-unclaimed-running.md: Status set to review.
- docs/tasks/1148-report.md: this file.

## Commands (last lines)

- Step 1, `python -c "import app.icalsync"`: no output.
- Step 2, same import: no output.
- Step 3, `pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py -q`: `67 passed in 9.40s`.
- Step 4, translate check: `['Stay from D was cancelled', 'Pobyt od D byl zrušen, al', 'Lượt lưu trú từ D bị hủy ']`.
- Step 5, `pytest tests/test_icalsync.py -k "unconfirmed or fresh_running or old_running"`: `6 passed, 58 deselected in 1.60s`.
- Step 7, `grep -c cancelled_filing_unconfirmed docs/OPERATIONS.md`: `1`.
- Step 8, area run (test_icalsync, test_ical_skip_unchanged, test_alert_language, test_host_i18n, test_no_em_dashes, test_go_host_i18n, test_stale_submission) with `-rs`: `140 passed, 1 warning`, no skips.
- Step 8, `python3 scripts/context_lint.py`: `context lint: OK` (warning: 7 commits touched App/ after the last status.md update; orchestrator to update status).

## Section 7 acceptance

- [x] Event and sweep cancel both go through `_running_defers_cancel` and `_alert_if_filing_in_doubt`.
- [x] 6 new tests pass; both revert bites fail then pass.
- [x] No sentinel `%(` left in the cards: the step 4 translate check returns substituted text (`Stay from D ...`) for en, cs and vi; keys exist.
- [x] Step 8 green, lint OK, only section 3 files changed.

## Revert bites

- (a) alert calls removed: FAIL, `3 failed, 1 passed`. Failing: `test_a_cancel_event_with_an_unconfirmed_filing_cancels_and_alerts`, `test_an_old_running_filing_does_not_hold_the_cancel_for_ever`, `test_a_vanished_stay_with_an_unconfirmed_filing_cancels_and_alerts`. Restored: PASS, `4 passed`.
- (b) defer disabled (`False or not`): FAIL, `2 failed`: `test_a_fresh_running_filing_defers_the_cancel_until_the_sweep_recovers_it`, `test_a_vanished_stay_with_a_fresh_running_filing_is_deferred`. Restored: PASS, `2 passed`.

## Deviations

- None in code. Brief's base commit 21c87fc6 is not HEAD; the branch HEAD was b49c0c17 (brief commit), used as the base.
- Step 1 `import json` was added; `alerts` was already imported in icalsync.py, so no import line for it.

## Questions

- None.

## Owner steps left

1. Push the branch `task/1148-ical-cancel-running`.
2. Open the PR as a draft and keep it until 1148b is ready (per brief §9).
