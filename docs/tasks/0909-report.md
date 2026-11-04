# 0909 report (partial, Status: blocked)

## Done
- Go `go/internal/ubyport/sweep.go`: `RetryOutcomeUnknownBatches` now also calls `retryUnknownChains`. A chain = unknown batches of one apartment with the same `guest_ids` text. Gaps 30m/2h/6h/12h from the latest attempt's `finished_at`; after 4 resends (5 attempts) it stops. Latest attempt stale (crash path) or already retried is skipped. Resend uses `markBatchRetried` + `SubmitForApartment` with `autoResendMode`.
- `App/app/host_i18n.py` (en, cs) and `App/app/host_vi_i18n.py` (vi): `notification.submission_outcome_unknown.detail` now says the system retries by itself and the host acts only if the alert is still open after the last retry.
- `docs/context/decisions.md`: one `[filing] 2026-11-04` line.

## Tests run
- `go test ./internal/ubyport/...` (Postgres test DB): ok, 25.3 s, 0 failures. Existing crash-path tests pass.
- `go vet ./internal/ubyport/`: clean.

## Not done
- No new tests for the chain retry (gap timing, 5th attempt cap, duplicate/rejection stop, alert open). Go and Python.
- Python `App/app/reporting.py` `_retry_outcome_unknown_batches` not changed; it still only does the crash-path retry. Python parity is missing.
- Final-failure e-mail (host, cc `config.SUPPORT_EMAIL`, once per chain, Python and Go) and the push on exhaustion: not implemented. Go helpers to reuse: `QueueSubmissionProblemMail`, `QueueFilingProblemPush`, `EnqueueMail` in `go/internal/ubyport/notify.go`.
- Alert #87 root cause: not confirmed. Candidate: `apartment_in_doubt` / `ApartmentInDoubt` depends on `guest.submission_id` pointing at an `outcome_unknown` batch, and the retry path (`markBatchRetried`, Python `_retry_outcome_unknown_batches`) clears `submission_id` before the resend. During that window an ok batch for other guests of the apartment can resolve `submission_outcome_unknown:<apt>` (`go/internal/ubyport/submit.go` ~line 147, `App/app/reporting.py` ~line 1796). Needs a DB check on the production row history before a fix.
- Critical-alert push for `submission_outcome_unknown`: not checked.
- `scripts/context_lint.py` FAILS on `docs/tasks/0909-retry-unknown-outcome.md`: missing sections 7 (Acceptance), 8 (Stop and ask), 9 (Report). The brief is being edited by the reviewer; lint not fixed by executor.

Status: blocked
