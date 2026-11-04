# 0909: Retry an unanswered police filing automatically

Status: todo. Owner OK: 2026-11-04 (Josef, "why not retry several times", "we dont care about duplicates right, if we get them we stop"). Executor: Haiku 5.5, one run. CRITICAL: filing correctness (rule 1).
Read first: AGENTS.md, docs/context/executor.md, docs/UBYPORT_CORE.md, docs/OPERATIONS.md#the-submit_state-state-machine.

## 1. Objective
When UbyPort does not answer after a request was sent (`UbyportOutcomeUnknownError`, batch state `outcome_unknown`, `error_text` not equal to `STALE_SUBMISSION_REASON`), the sweep resends the same guests by itself, with growing gaps, until UbyPort answers. This replaces owner decision OD-1 ("never automatically"). Reason: on 2026-11-01 submission #16 got "Remote end closed connection without response", nothing retried it, and the stay sat for 3 days until the host filed by hand. A duplicate answer (150, state `ok_duplicate`) is accepted as filed and stops the chain.

## 2. Rules
- Gaps measured from the latest unknown batch's `finished_at`: 30 min, 2 h, 6 h, 12 h. That is at most 4 automatic resends after the first attempt. After the 4th also fails, stop (alert stays, see 3).
- Chain = the unknown batches of one apartment with the same `guest_ids` text. Attempt count = number of those batches in state `outcome_unknown`. Resends use `mode=AUTO_RESEND_MODE` (Go `autoResendMode`), `only_guest_ids` = the batch's ids. No schema change, no migration.
- Any answer ends the chain: ok, ok_duplicate, rejection, partial, error. Only another unanswered attempt continues it.
- The existing crash path (`error_text == STALE_SUBMISSION_REASON`, one resend, `retried_at`) stays unchanged.
- Resend uses the same locking as today: stamp `retried_at` on the old batch and clear `guest.submission_id` for guests not yet `sent`, under `lock_key submit_apartment` (copy `_retry_outcome_unknown_batches`).
- `collect_sendable`: guests pointing at an unknown batch stay excluded from normal sweep sends. Only the retry path above frees them.
- Do not retry while `ubyport_auth_failed:<apt>` alert is open (existing check) or the apartment setup is invalid (existing check).

## 3. Alert must not hide a held stay
- `submission_outcome_unknown:<apt>` stays open while `apartment_in_doubt(apt)` is true. Check every place that resolves or auto-expires it (grep `submission_outcome_unknown` and `alerts.resolve`, also the alert auto-clear job) and make sure none closes it while guests still point at an unknown batch. On 2026-11-01 alert #87 was resolved 10 h after it was raised while the guests were still held; find out which code path did that and fix it.
- Confirm a critical `submission_outcome_unknown` alert also sends a push to the host (same path as other critical alerts). If it does not, add it using the existing push helper, no new dependency.
- When the last automatic resend (the 4th) also gets no answer, send ONE e-mail to the host (the operator of that property, same recipient as `mail_notify.submission_problem`) saying what happened: UbyPort did not answer after 5 tries over about 20 hours, the guests are not filed, what to do (file by hand in UbyPort or press the normal Send on the stay). Copy `config.SUPPORT_EMAIL` via `cc_email` (see `mail_notify.py` lines ~1519 and ~1608 for the pattern), and send the push with the critical alert. Dedupe so it is sent once per chain (idempotency key from the last batch id). Implement in Python and Go (`go/internal/ubyport/notify.go`, existing `EnqueueMail` and `QueuePush`; the Go mail outbox needs the cc column filled the same way). Do NOT add a new "Send again now" button: the existing standard Send button on the stay stays as it is.
- Update the English and Czech i18n text of `notification.submission_outcome_unknown.detail` (host_i18n.py) to say the system will retry by itself and the host only needs to act if the alert is still open after the last retry. Same for the Vietnamese file with a faithful translation.

## 4. Where
- Python: `App/app/reporting.py` `_retry_outcome_unknown_batches`, `AUTO_RESEND_MODE`, the comment block near `STALE_SUBMISSION_REASON`, and the `except UbyportOutcomeUnknownError` comment in `submit_batch`.
- Go (production files now; keep behaviour identical): `go/internal/ubyport/sweep.go` `RetryOutcomeUnknownBatches`; check `go/internal/ubyport/submit.go` and `recover.go` for the same alert resolve rule.
- Docs: replace OD-1 wording in `docs/UBYPORT_CORE.md` / `docs/OPERATIONS.md` if they state "never retried"; append one decision line to `docs/context/decisions.md` (`[filing] 2026-11-04: unanswered filings retry 30m/2h/6h/12h, duplicate answer stops, supersedes OD-1`). Update `docs/context/known-issues.md` only if an entry mentions the old rule.

## 5. Tests (rule: 0 skipped)
- The final-failure mail goes to the host with support in cc exactly once, in both languages of code (Python and Go).
- Python, in `App/tests/test_submission_*.py` style: an unknown batch is not resent at 29 min, is resent at 31 min; second unknown waits 2 h; the 5th attempt never happens; a duplicate answer stops the chain and marks guests sent; a rejection stops the chain; the crash path is unchanged; the alert stays open while a guest points at an unknown batch.
- Go: same cases in `go/internal/ubyport` tests against the test Postgres (`UBYHOST_TEST_DATABASE_URL`), with a fake clock.
- Check `test_submission_retry_cap` (it greps `submit_batch` and `plan_outcome` source for state literals) still passes.
- Run only the test-map row "Filing, UbyPort, worker, claim" plus `go test ./internal/ubyport/...`. From `App/`: `.venv/bin/python -m pytest <files> -q --tb=short -x 2>&1 | tail -30`. From the repo root: `python3 scripts/context_lint.py`.

## 6. Report
Write `docs/tasks/0909-report.md`: what changed, which code path closed alert #87 early, tests and results, any deviation. Do not open the PR; the orchestrator does.
