# 0558: Go police: submit_for_apartment, the sweep and job kind `submit`
Status: todo
Depends on: 0557 | Base commit: main | Branch: claude/project-thread-dwlrdj
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
Plan v4 step 17 (G5), rule 1. Go gets the whole police sweep: `SubmitForApartment`, the one automatic retry of crash-interrupted batches, `Sweep` over all apartments, and the Go job kind `submit` that runs it. The kind is off in production until `submit` is in both `UBYHOST_GO_JOB_KINDS` and `UBYHOST_JOB_QUEUE_KINDS`; nothing changes in production.
## 2. Context
- Python source of truth, `App/app/reporting.py`: `submit_for_apartment` (1955-2027), `_retry_outcome_unknown_batches` (1913-1953), `sweep` (2029-2100), `client_for` (1088). `App/app/scheduler.py` `_job_submit` (154-167). `App/app/demo.py` `is_demo_apartment` (47-60). `App/app/codelists.py` `cached`, `error_codebook`, `error_severities` (89-105) and the `codebook_from_rows`/`severities_from_rows` helpers they call (grep for them). `App/app/config.py`: `UBYPORT_ENV` (296), `UBYPORT_DOMAIN` (308), `UBYPORT_MAX_BATCH` (311), `UBYPORT_TIMEOUT` (313), `endpoint_for` (638), and whatever `UbyportClient` reads for auth code and TLS verify. `App/app/db.py` `decrypt_secret` (2309): a token that will not decrypt is an empty string, not an error.
- Already in Go: `SubmitBatch` + `BatchDeps` (submit.go), `ClaimSendable`/`ReleaseSendableClaim` (claim.go), `CollectSendable`/`LoadApartment`/`FieldDecrypter` (collect.go, 0556), `RecoverStaleSubmissions`/`RefreshRegistrationCompletedAt` (recover.go, 0557), `validation.ValidateApartment`/`ErrorsOnly` (0555), `RaiseAlert`/`ResolveAlert` (effects.go), `NewClient` (client.go), `secure.LoadDataKeys`. Job wiring: `goIntervals` and `goHandlers` in `go/cmd/ubyhost-web/main.go` (214-250); Python's interval is `config.SUBMIT_SWEEP_MINUTES`.
- **Traps:**
  - Python `issues_to_text` (`validation.py` 1106) joins `"field: message"` with `"; "`; add it to `go/internal/validation` if 0555 did not.
  - The apartment dict given to `validate_apartment` carries the decrypted `uby_ws_password`; an undecryptable token becomes `""`, which then fails validation, as Python.
  - Sweep error handling: a guest decrypt error (the 0556 loader's error; make it a typed `ErrGuestUnreadable` checked with `errors.Is` if it is not one yet) raises `guest_record_unreadable`; any other error raises `sweep_failed`; both critical, texts and params byte-for-byte, and the loop continues. `sweep_failed:<id>` is resolved only after a clean apartment.
  - An apartment with an open `ubyport_auth_failed:<id>` alert is skipped and not counted; check how effects.go reads an open alert and reuse it.
  - `submit_for_apartment` releases the claim even when a batch errors (Go `defer`). Batches are `UBYHOST_MAX_BATCH` (default 32) guests each.
  - The retry runs `SubmitForApartment` with `only_guest_ids` and mode `auto_resend`; an empty guest list is marked retried but not sent.
  - The job handler returns the count the jobs package expects (look at the billing handlers) and logs the summary only when something was submitted or failed. No heartbeat ping in Go (stays with Python while the kind is off); write that in the report.
  - The Go job needs the data key (`secure.LoadDataKeys(os.Getenv)`) for guest fields and the request XML. If loading fails, the handler returns the error; it must not start sending.
## 3. Files
New: `go/internal/ubyport/sweep.go`, `go/internal/ubyport/sweep_test.go`. Edits: `go/cmd/ubyhost-web/main.go` (the `submit` kind, its interval and handler only), `go/internal/validation/validation.go` only for `IssuesToText` if missing. Write `docs/tasks/0558-report.md`. Nothing else.
## 4. Steps
1. `sweep.go`, top comment naming the Python lines: `func LoadCodebook(ctx, pool) (map[string]string, map[string]int, error)`; `func ClientFor(apt *ApartmentRow, decryptSecret func(string) string, getenv func(string) string) *Client`; `type SweepDeps struct{ Batch BatchDeps; Decrypt FieldDecrypter; DecryptSecret func(string) string; NewSender func(*ApartmentRow) Sender; MaxBatch int }`; `func SubmitForApartment(ctx, d SweepDeps, aptID int64, o CollectOptions, mode string) ([]BatchResult, error)` (demo apartment gives one `noop` result with Python's error text); `func RetryOutcomeUnknownBatches(ctx, d SweepDeps, aptID int64) (int, error)`; `type SweepSummary struct{ Apartments, Submitted, Failed int }`; `func Sweep(ctx, d SweepDeps, ownerUserID *int64) (SweepSummary, error)`.
2. `sweep_test.go` (database tests; run them) with a fake `Sender`: demo apartment noop; incomplete setup raises `apartment_setup` and sends nothing; setup fixed resolves it; 70 sendable guests go in three batches (32, 32, 6) and the claims are released; a sender error in batch 2 still releases the claims; retry of a stale batch resends only its guests in mode `auto_resend` and sets `retried_at`; sweep skips an apartment with an open auth alert; an unreadable guest raises `guest_record_unreadable` and the next apartment is still swept; summary counts.
3. `main.go`: `"submit"` in `goIntervals` with Python's default sweep minutes, and in `goHandlers` building `SweepDeps` from the environment.
4. Commit: `0558: Go police sweep and job kind submit`.
## 5. Do not touch
`App/` (all), every other file in `go/`, `go.mod`/`go.sum`, compose, CI, templates/CSS/JS.
## 6. Commands
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go build ./... && go test ./internal/ubyport/ ./cmd/... -count=1 2>&1 | tail -30` with `UBYHOST_TEST_DATABASE_URL` set; report the skip count (must be 0).
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
`git diff --stat origin/main` lists only section 3 files and this brief. All tests pass with 0 skipped. With `UBYHOST_GO_JOB_KINDS` unset the Go binary claims no `submit` job.
## 8. Stop and ask
Stop if the Go client cannot be built from the same settings Python's `client_for` reads, or if matching Python needs a new dependency.
## 9. Report
`docs/tasks/0558-report.md`: command tails, diff stat, the owner steps to switch the kind on (env lines only, not run), anything you decided beyond section 2.
