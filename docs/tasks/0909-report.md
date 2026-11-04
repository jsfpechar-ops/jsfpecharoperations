# 0909 report (Python half, Status: blocked)

Branch task/0909-py, worktree /tmp/wt0909py. Go half is in /tmp/wt0909go (not touched here).

## Done
- `App/app/reporting.py`: `apartment_in_doubt` ignores `sent` guests; the unknown-outcome branch of `submit_batch` no longer mails per attempt; crash-path docstring updated. New `_clock`, `_unknown_chains` (chain key = sorted guest ids), `_retry_unknown_chains` (gaps 30m/2h/6h/12h, 5 attempts, stops on live-chain guards, resolves the card when not in doubt) and `_resend_unknown_chain` (guarded `retried_at` claim, free guests with `submit_state != sent`, `submit_for_apartment(..., mode=auto_resend, ignore_schedule=True)`, restore unsent freed guests under lock).
- `App/app/routes/admin.py` `dismiss_alert`: refuses `submission_outcome_unknown` while in doubt (409 for fetch, else flash `flash.error.unknown_card_locked`).
- `App/app/host_i18n.py` (en, cs) and `App/app/host_vi_i18n.py` (vi): `flash.error.unknown_card_locked`. The en text is the brief's; cs and vi are my own translations, needing a native check.
- Tests rewritten to the new rule: `test_stale_submission.py::test_an_unclear_resend_is_retried_on_the_gap_schedule_then_stops` (replaces the WP31 test, same name pattern, fake clock via `reporting._clock`); docstrings of `test_sweep_does_not_retry_a_live_unknown_outcome`, `test_a_manual_send_with_an_unclear_outcome_is_not_auto_retried`, `test_an_unknown_outcome_is_recorded_and_not_refiled_by_the_sweep` updated (their assertions still hold at real time).
- Brief `docs/tasks/0909-retry-unknown-outcome.md` restructured to sections 1 Objective, 2 Context, 3 Files, 4 Steps, 5 Do not touch, 6 Commands, 7 Acceptance, 8 Stop and ask, 9 Report, with the Report line. Stale Go draft note removed. Cross-references updated.
- `docs/context/decisions.md`: one `[filing] 2026-11-04` line (replaces the earlier partial-run line).

## Tests
- `App/.venv/bin/python -m pytest tests/test_stale_submission.py tests/test_submission_retry_cap.py tests/test_submission_mail.py tests/test_admin_route_split.py tests/test_host_i18n.py -q`: 94 passed, 0 failed, 0 skipped.

## Lint
- `python3 scripts/context_lint.py`: no brief error. Remaining ERROR: `docs/context/decisions.md` ~2250 tokens over cap 2200 (the file was already at cap; needs one more older line compacted by the orchestrator).

## Not done (Left)
- Final notice: `mail_notify.submission_problem` cc and idempotency_key parameters, `unanswered` variant and its en/cs/vi texts, push `filing_problem` with key `unanswered:<L>`. The chain stops at count 5 with no mail yet.
- New Python cases from brief section 6 (only the gap-schedule test is new; the 10 cases are not written). Dismiss refusal has no test.
- Go half: not in this branch.
- Alert #87 root cause not confirmed. Owner check (brief section 4): `SELECT id, created_at, resolved_at, user_dismissed FROM alert WHERE id = 87;` and `SELECT id, mode, state, created_at, finished_at, guest_ids FROM submission WHERE apartment_id = 5 AND created_at >= '2026-11-01' ORDER BY id;`.
- `docs/UBYPORT_CORE.md` / `docs/OPERATIONS.md` OD-1 wording: not checked.

Status: blocked
Deviations: Done steps 1 to 4 of the Python half. Left: final notice mail and push, unanswered i18n texts, the new test cases, the decisions cap trim.
