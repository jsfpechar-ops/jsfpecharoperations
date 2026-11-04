# 0909: Retry an unanswered police filing automatically

Status: todo (reviewed 2026-11-04: sections 2, 3 and 5 rewritten, numbers kept). Owner OK: 2026-11-04 (Josef, "why not retry several times", "we dont care about duplicates right, if we get them we stop"). Executor: Haiku 5.5, one run. CRITICAL: filing correctness (rule 1).
Read first: AGENTS.md, docs/context/executor.md, docs/UBYPORT_CORE.md, docs/OPERATIONS.md#the-submit_state-state-machine.

## 1. Objective
When UbyPort does not answer after a request was sent (`UbyportOutcomeUnknownError`, batch state `outcome_unknown`), the sweep resends the same guests by itself, with growing gaps, until UbyPort answers. This replaces owner decision OD-1 ("never automatically") and the WP31 rule "an `auto_resend` batch is never resent". Reason: on 2026-11-01 submission #16 got "Remote end closed connection without response", nothing retried it, and the stay sat for 3 days until the host filed by hand. A duplicate answer (150, state `ok_duplicate`) is accepted as filed and stops the chain.

## 2. Context
- **Chain key** = the sorted set of ids in `submission.guest_ids` (parse the JSON, sort, compare as a list; never compare the raw text). Only batches of the same apartment.
- **Chain** for a key = the newest batch with that key whose `mode != AUTO_RESEND_MODE` (the original send, by host or sweep), plus every later batch (higher id) with that key. If no such original exists (the set shrank, see below), the chain starts at the oldest batch with that key. A new host or sweep send with the same key therefore starts a fresh chain.
- **Attempt count** = number of batches in the chain. The chain is live only if every batch in it is `outcome_unknown`; any other state (ok, ok_duplicate, rejected, partial, error, transport_error, running) ends or pauses it: do nothing.
- **Due**: latest batch L of a live chain has `retried_at IS NULL` and `now >= L.finished_at + gap[count-1]`, gaps = 30 min, 2 h, 6 h, 12 h. Count 5 = 4 resends done: never resend, go to the final notice (section 4). `finished_at` is TEXT (`db.utcnow()`, e.g. `2026-11-01T10:00:00+00:00`): Python `datetime.fromisoformat`, Go scan into `string` then `time.Parse(time.RFC3339, s)` (pgx cannot scan TEXT into `time.Time`). Compare with the sweep's clock (Go `sweepNow(d)`), never `time.Now()` directly.
- **Crash path unchanged**: a stale original (`error_text == STALE_SUBMISSION_REASON` and `mode != AUTO_RESEND_MODE`, `retried_at IS NULL`) is still resent by the existing query in `_retry_outcome_unknown_batches` / `RetryOutcomeUnknownBatches`; the chain code skips a chain whose latest batch matches that query. A stale batch with mode `auto_resend` (crash during a resend) is an ordinary chain attempt. Keep the existing helper `markBatchRetried` and the crash query as they are.
- **Resend step** (new helper, one transaction under `lock_key submit_apartment`, Python and Go):
  1. `UPDATE submission SET retried_at = now WHERE id = L AND retried_at IS NULL AND state = 'outcome_unknown'`; if 0 rows changed, stop (another worker took it).
  2. For each chain guest: `UPDATE guest SET submission_id = NULL WHERE id = ? AND submission_id = L AND submit_state != 'sent'`; keep the ids where 1 row changed (`freed`). A guest filed by hand (`sent`) or moved to a newer batch by a host send is never freed and never resent. If `freed` is empty, stop.
  3. After commit: `submit_for_apartment(apt, only_guest_ids=freed, mode=AUTO_RESEND_MODE, ignore_schedule=True)` (Go `CollectOptions{OnlyGuestIDs: freed, IgnoreSchedule: &yes}` with `yes := true`). `ignore_automation` stays False, so the retry cap and every other collect guard still apply.
  4. Afterwards, under the same lock: `UPDATE guest SET submission_id = L WHERE id IN (freed) AND submission_id IS NULL AND submit_state != 'sent'`. A freed guest the resend did not take (incomplete now, cap, claim held elsewhere) goes back in doubt instead of silently leaving it; the chain then stops for it (L has `retried_at`) and the alert stays.
  A resend that sends fewer guests than the chain had creates a new key and starts a new chain at count 1. This is bounded (the set only shrinks) and accepted.
- `collect_sendable` / Go collect: unchanged. Guests pointing at an unknown batch stay excluded from normal sweep sends.
- Do not retry while `ubyport_auth_failed:<apt>` is open or the apartment setup is invalid (existing checks at the top of the function). Apartments with `automation_mode = 'manual'` are not swept today and stay not swept (say so in the report).
- Per-attempt mail: the `outcome_unknown` branch (`submit_batch` Python, `batchOutcomeUnknown` Go) no longer calls `submission_problem` / `batchMail`. The alert is still raised there. The only mail is the final notice. (Its current text "Nothing from this attempt reached the register" is wrong for this state anyway.)

## 3. Files
- Python: `App/app/reporting.py` `_retry_outcome_unknown_batches` (call the new chain function at its end, as Go does), `apartment_in_doubt`, `AUTO_RESEND_MODE` comment (~98), the comment near `STALE_SUBMISSION_REASON` (~60), the `except UbyportOutcomeUnknownError` branch of `submit_batch` (~1626); `App/app/mail_notify.py` `submission_problem`, `build_submission_problem`; `App/app/push.py`; `App/app/routes/admin.py` `dismiss_alert`; host_i18n.py, host_vi_i18n.py.
- Go (the GO executor's worktree, not this branch; see section 5): `go/internal/ubyport/sweep.go` (`RetryOutcomeUnknownBatches`, `retryUnknownChains`, rewritten to section 2: it keys on raw text, counts all unknown batches ever, skips every stale latest and scans TEXT into `time.Time`), `submit.go` `batchOutcomeUnknown`, `effects.go` `ApartmentInDoubt`, `notify.go`, `go/internal/mail/submission_problem.go`.
- Docs: replace OD-1 wording in `docs/UBYPORT_CORE.md` / `docs/OPERATIONS.md` if they state "never retried"; append one decision line to `docs/context/decisions.md` (`[filing] 2026-11-04: unanswered filings retry 30m/2h/6h/12h, duplicate answer stops, supersedes OD-1 and WP31 single resend`). Update `docs/context/known-issues.md` only if an entry mentions the old rule.

## 4. Steps
### Alert must not hide a held stay
- `apartment_in_doubt` (Python) and `ApartmentInDoubt` (Go, `go/internal/ubyport/effects.go`): add `AND g.submit_state != 'sent'`, so a guest filed by hand no longer holds the card open forever.
- Writers that close `submission_outcome_unknown:<apt>` (complete list, verified 2026-11-04): Python `submit_batch` ok/ok_duplicate branch (`reporting.py` ~1796), Go `submit.go` ~147 (both guarded by in-doubt), and the host's Dismiss (`routes/admin.py` `dismiss_alert`, sets `user_dismissed = 1`). No retention or auto-expire job touches open alerts. Changes:
  - `dismiss_alert`: refuse kind `submission_outcome_unknown` while `apartment_in_doubt(row["apartment_id"])`, the same way as `dates_changed_resign` (409 for fetch, else flash). New key `flash.error.unknown_card_locked` in en, cs (host_i18n.py) and vi (host_vi_i18n.py): "This card clears by itself when UbyPort answers or when you file the guests by hand."
  - The chain function (both languages) resolves `submission_outcome_unknown:<apt>` when the alert is open and `apartment_in_doubt` is false (e.g. after the host filed by hand).
- Alert #87: the executor has no production database. In the report, name the two candidate paths above and give the owner this check to run: `SELECT id, created_at, resolved_at, user_dismissed FROM alert WHERE id = 87;` and `SELECT id, mode, state, created_at, finished_at, guest_ids FROM submission WHERE apartment_id = 5 AND created_at >= '2026-11-01' ORDER BY id;`. `user_dismissed = 1` means the Dismiss button; otherwise an ok batch ran while in-doubt was false.
- **Final notice** (count 5 and L still `outcome_unknown`, at least one chain guest has `submission_id = L` and is not `sent`, and `now - L.finished_at < 24 h` so a pruned outbox row is never re-sent): checked by the chain function on every sweep; dedupe through the outbox keys below.
  - Mail: `mail_notify.submission_problem(apartment, L, state="unanswered", reason=L.error_text, transport=False, cc_email=config.SUPPORT_EMAIL, idempotency_key=f"submission_unanswered:{L}")`: add the two optional parameters (default: current behaviour). Recipient is unchanged (`_entity_contact_email` of the legal entity). Add the `unanswered` variant to `build_submission_problem`: keys `mail.submission_problem.subject_unanswered`, `intro_unanswered`, `preheader_unanswered`, `next_unanswered` (en, cs, vi). Content: UbyPort did not answer after 5 tries over about 20 hours; the guests are not confirmed as filed; check UbyPort and file by hand there if they are missing, or press the normal Send on the stay. No new button.
  - Go: same in `go/internal/mail/submission_problem.go` (English constants equal to the Python en strings) and `notify.go`: add `CC string` to `OutboxMail` (empty means NULL, replace the literal `NULL` in `EnqueueMail`), and let `QueueSubmissionProblemMail` take cc and key. Support address: `"support@ubyhost.com"` as in `pushsend.go`.
  - Push: `push.notify(owner, "filing_problem", key=f"unanswered:{L}", url=..., params={"property": ...})` built like `push.filing_problem` but with this key, so a same-day rejection push cannot swallow it. Go: `QueuePush` with kind `filing_problem`, key `unanswered:<L>`.
- i18n: `notification.submission_outcome_unknown.detail` in en and cs (host_i18n.py) and vi (host_vi_i18n.py): "Their answer never arrived (%(error)s). UbyHost sends it again by itself several times over the next 20 hours. You only need to act if this card is still here after that." Keep `%(error)s`.

## 5. Do not touch
- `go/` (the Go half belongs to the GO executor in its own worktree; this branch never edits anything under `go/`).
- `App/app/migrations/` (no schema change in this brief), templates and CSS (no template or CSS change; no new button).
- No new dependency (section 7).

## 6. Commands (tests; rule: 0 skipped)
- Tests that pin the old rule and must be rewritten to the new one (not deleted): `test_stale_submission.py` `test_sweep_does_not_retry_a_live_unknown_outcome` and `test_a_manual_send_with_an_unclear_outcome_is_not_auto_retried`; `test_submission_retry_cap.py` `test_an_unknown_outcome_is_recorded_and_not_refiled_by_the_sweep`; Go `sweep_test.go` `TestRetrySkipsAndGuards` case "auto_resend mode is not retried again" (still true for a stale auto_resend batch on the crash query; the chain must pick it up instead). `test_icalsync.py` ~442 only fixes the docstring if it still says "will not retry".
- New, Python (`App/tests/test_submission_*.py` style) and the same cases in Go (`go/internal/ubyport`, test Postgres `UBYHOST_TEST_DATABASE_URL`, fake clock via `SweepDeps`):
  1. not resent at 29 min, resent at 31 min with mode `auto_resend`; 2nd unknown waits 2 h (not at 1 h 59); 3rd 6 h; 4th 12 h; a 6th batch is never created.
  2. after the 5th unknown: one mail to the entity address with `cc_email = support@ubyhost.com`, one push per device; two more sweeps add no row; no mail at all from attempts 1 to 4.
  3. duplicate answer (150) on a resend: guests `sent`, no further resend, alert resolved. Rejection on a resend: no further resend.
  4. guest_ids `[3, 1]` and `[1, 3]` are one chain.
  5. one guest of a two-guest batch filed by hand during the gap: only the other guest is resent; when both are filed by hand nothing is sent and the alert resolves on the next sweep.
  6. host sends the stay during the gap and gets `outcome_unknown`: a fresh chain (next resend at 30 min, not 2 h).
  7. two sweeps racing on the same due chain (call the chain function twice in a row with the first resend stubbed to stay `running`): exactly one resend.
  8. a freed guest the resend does not take (make it incomplete): points at L again, alert open.
  9. crash path unchanged (existing tests pass); a crash during a resend continues the chain.
  10. Dismiss of the unknown card is refused while in doubt and allowed after.
- `test_submission_retry_cap` greps `submit_batch` and `plan_outcome` source for state literals: it must still pass.
- Run only the test-map row "Filing, UbyPort, worker, claim" plus `test_submission_mail.py`, the admin alert tests (`grep -l dismiss App/tests/test_admin*.py`) and `go test ./internal/ubyport/... ./internal/mail/...`. From `App/`: `.venv/bin/python -m pytest <files> -q --tb=short -x 2>&1 | tail -30`. From the repo root: `python3 scripts/context_lint.py`.

## 7. Acceptance
- No code path can create a 6th batch in a chain, resend a guest whose `submit_state` is `sent`, or resend a guest whose `submission_id` is not L.
- Python and Go give the same result for every case in section 6.
- No new dependency, no migration, no new button.

## 8. Stop and ask
Stop and write the report instead of guessing if: the rules need a schema change; a test in section 6 can only pass by deleting an existing test; the `sent` filter in `apartment_in_doubt` breaks a test that expects a `sent` guest to hold the card; the Go mail cannot carry cc without changing the mail sender.

## 9. Report
Write `docs/tasks/0909-report.md`: what changed, the alert #87 candidates and the owner SQL from section 4, tests and results, any deviation. Do not open the PR; the orchestrator does.
Report: docs/tasks/0909-report.md
