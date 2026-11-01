# 0554: Go G5d-3d: SubmitBatch, the whole send of one batch, matching Python
Status: review
Depends on: 0550, 0551, 0552, 0553 | Base commit: main | Branch: claude/project-thread-bhyvh5
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
Plan v4 step 17 (G5), rule 1. Go gets `SubmitBatch`: send one batch of guests to UbyPort and record everything Python's `submit_batch` records (submission row, guest writes, alerts, mail, push, audit), using the pieces 0550-0553 built. The caller passes in the loaded apartment, the guest/stay pairs, the sender and the codebook; loading them, the client and the sweep job are 0555. Nothing calls the new code; nothing changes in production.
## 2. Context
- Python source of truth: `App/app/reporting.py` `submit_batch` (1541-1817). Read it whole; it is the spec. Helpers it calls are already ported: `header_from_apartment`/`guest_payload` = `ubyport.Header`/`GuestFields` (request.go), `plan_outcome` = `PlanOutcome` (outcome.go), `uby_errors.describe`/`split_codes` = `Describe`/`SplitCodes` (codes.go), DB writes in store.go (`InsertSubmission`, `RecordOutcomeUnknown`, `RecordTransportError`, `RecordOutcome`, `ReceiptLookup`), alerts/audit/in-doubt/stuck in effects.go, mail and push in notify.go (0553). `demo.is_demo_stay` (demo.py 81): `reservation.source == "demo"`.
- **Traps:**
  - Order of side effects must follow Python line by line: insert `running` row, send, then on outcome-unknown / transport / auth error the exact alert kinds, messages, dedupe keys and params of 1585-1660; on an answer resolve `submission_transport:<id>` first, then plan, write, stuck alerts per reservation, `clear_stuck_alert_if_recovered` per reservation, ok/rejected branch, receipt branch, audit. Alert message strings and params are byte-for-byte copies (use `fmt.Sprintf` with the same text).
  - Error kinds: `errors.Is(err, ErrOutcomeUnknown)` is the in-doubt branch; any other `*ubyport.Error` (including `ErrAuth`, which also raises `ubyport_auth_failed`) is the transport branch. The in-doubt branch stores the request XML Python gets from `exc.request_xml`: if `*Error` does not carry it, add a `RequestXML string` field to `Error` in client.go and set it in `Submit` where the envelope is known (the only allowed change outside the new files).
  - Mail and push are best-effort: an error from them is logged (no address, no reason text) and the batch result is unchanged. Alert or DB errors are returned.
  - `str(exc)` in Python is `err.Error()` in Go. Python `f"{name}"` of a None internal name prints `None`; keep `InternalName` a string and note it.
  - Stuck-alert names: `"<surname> <first_name>"` stripped, else `#<id>`, joined by `", "`, grouped by reservation in first-seen order.
  - Rejected `count` param is `failed + blocked` as an int; `header` is the described header codes joined by `", "` (empty string when none).
  - Clock: one `UTCNow()` for `now` after the answer, as Python; separate calls where Python calls `db.utcnow()` again.
## 3. Files
New: `go/internal/ubyport/submit.go`, `go/internal/ubyport/submit_test.go`. Allowed edit: `go/internal/ubyport/client.go` only for `Error.RequestXML` (see trap). Write `docs/tasks/0554-report.md`. Nothing else.
## 4. Steps
1. `submit.go`, top comment naming the Python lines:
   - `type Sender interface{ Submit(ctx context.Context, header map[string]*string, guests []map[string]any) (SubmitResult, error) }` (`*Client` satisfies it).
   - `type BatchPair struct{ Guest Guest; Reservation Reservation; Outcome OutcomeGuest; Source string }` or the smallest equivalent that carries what `GuestFields`, `PlanOutcome` and the demo check need; reuse existing types, do not duplicate fields.
   - `type BatchDeps struct{ Pool *pgxpool.Pool; Enc FieldEncrypter; Getenv func(string) string; AppBaseURL, PublicBaseURL, Endpoint string; Codebook map[string]string; Severities map[string]int; Now func() time.Time }`.
   - `type BatchResult struct{ Submitted, Failed, Blocked int; SubmissionID int64; State, Error, Stamp string }`.
   - `func SubmitBatch(ctx context.Context, d BatchDeps, s Sender, apt Apartment, ref ApartmentRef, pairs []BatchPair, mode string) (BatchResult, error)`; demo pairs dropped with a log line; none left gives state `noop` and touches nothing.
2. `submit_test.go` (database tests; run them, `UBYHOST_TEST_DATABASE_URL` is set for you) with a fake `Sender`: all accepted (state `ok`, alerts `submission_rejected`/`submission_transport` resolved, audit row text, no mail); rejected (alert params bytes, one `email_outbox` row, push rows for a subscribed device); outcome unknown (submission `outcome_unknown`, request XML stored encrypted, guests point at it, critical alert, mail); auth error (two alerts); transport error (guests unchanged); accepted with no receipt and no stamp (`receipt_missing` warning); all-demo pairs (`noop`, no rows).
3. Commit: `0554: Go G5d-3d SubmitBatch matching submit_batch`.
## 5. Do not touch
`App/` (all), other files in `go/internal/` except the one client.go field, `go/cmd/`, `go.mod`/`go.sum`, compose, CI, templates/CSS/JS.
## 6. Commands
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/ubyport/ -count=1 2>&1 | tail -30` with `UBYHOST_TEST_DATABASE_URL` set; report the skip count (must be 0).
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
`git diff --stat` against the base lists only section 3 files and this brief. All ubyport tests pass with 0 skipped.
## 8. Stop and ask
Stop if `PlanOutcome`'s inputs cannot be built from what a caller loads (for example it needs a field no table has), or if matching Python needs a new dependency.
## 9. Report
`docs/tasks/0554-report.md`: command tails, diff stat, anything you decided beyond section 2.
