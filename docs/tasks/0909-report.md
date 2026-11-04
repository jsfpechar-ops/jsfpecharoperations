# 0909 report (Python half, Status: blocked)

Branch task/0909-py, worktree /tmp/wt0909py. Go half is in /tmp/wt0909go (not touched here). No push, no PR.

## Done
- Retry chain (`App/app/reporting.py`): `_unknown_chains` (chain key = sorted guest ids, start at newest original), `_retry_unknown_chains` (gaps 30m/2h/6h/12h, five batches, live-chain and auth/setup guards, card resolved when not in doubt), `_resend_unknown_chain` (guarded `retried_at` claim, free guests with `submit_state != sent`, `submit_for_apartment(..., mode=auto_resend, ignore_schedule=True)`, restore unsent freed guests under lock), `_clock` seam for tests.
- `apartment_in_doubt` ignores `sent` guests. The unknown-outcome branch no longer mails per attempt.
- Final notice (after the 5th batch, only while a guest is still held and within 24 h of the last attempt): `mail_notify.submission_problem(..., state="unanswered", cc_email=config.SUPPORT_EMAIL, idempotency_key="submission_unanswered:<id>")` and `push.filing_problem(..., key="unanswered:<id>")`. The `unanswered` variant and `subject/intro/preheader/next_unanswered` texts are in host_i18n.py (en, cs) and host_vi_i18n.py (vi). The brief gives only the content, so the wording is mine and needs a check. The push key override is a new optional `key` on `push.filing_problem`.
- Dismiss refused while in doubt (`App/app/routes/admin.py`), flash `flash.error.unknown_card_locked` (en from brief; cs and vi mine).
- Tests: `App/tests/test_stale_submission.py` (WP31 test rewritten to the gap schedule: resends at 2 h, 6 h, 12 h, then stops, no mail); `App/tests/test_submission_retry_chain.py` (new: guest-id order is one chain, a host send starts a fresh chain, two resends of one due chain send once, the fifth attempt mails and pushes once with keys and cc, nothing after five); `App/tests/test_push_events.py` (count of `push.filing_problem(` in reporting.py is now 2, for the final notice).
- Decisions: `docs/context/decisions.md` compacted to lint OK (wording only; the Postgres 2026-10-31 entries are merged into one line).

## Tests (App/.venv/bin/python -m pytest <filing row + test_admin_route_split.py test_host_i18n.py test_push*.py> -q)
- 468 passed, 0 failed.
- 1 skipped module: `tests/test_push_settings_browser.py` (11 browser tests). Playwright's Chromium download is blocked in this sandbox, so they did not run. The owner or CI must run them.
- Venv was missing `pypdf` and `pdfplumber` (installed in the venv only; not a repo change). No repo dependency change.

## Lint
- `python3 scripts/context_lint.py`: OK.

## Not done (Left)
- Dismiss refusal has no test. Gap-edge cases at 29 and 31 min, the "guest filed by hand during the gap" case, and "crash during a resend" are not new tests (the existing crash test and the gap-schedule test cover parts).
- Go half: not in this branch.
- Final notice texts are not checked by a native speaker in cs and vi.
- Alert #87 root cause unconfirmed. Owner check: `SELECT id, created_at, resolved_at, user_dismissed FROM alert WHERE id = 87;` and `SELECT id, mode, state, created_at, finished_at, guest_ids FROM submission WHERE apartment_id = 5 AND created_at >= '2026-11-01' ORDER BY id;`.
- `docs/UBYPORT_CORE.md` / `docs/OPERATIONS.md` OD-1 wording: not checked.

Status: blocked
Deviations: Done steps 1 to 5 of the Python half. Left: the test cases listed above, the browser run, the Go half.
