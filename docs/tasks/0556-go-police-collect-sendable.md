# 0556: Go police: collect_sendable, guest decrypt and the send schedule
Status: todo
Depends on: 0555 | Base commit: main | Branch: claude/project-thread-dwlrdj
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
Plan v4 step 17 (G5), rule 1. Go gets `CollectSendable`: the list of guests (with their stays) that Python's `collect_sendable` would offer right now, loaded and decrypted from Postgres, ready for `ClaimSendable` and `SubmitBatch`. Nothing calls the new code; nothing changes in production.
## 2. Context
- Python source of truth, `App/app/reporting.py`: `collect_sendable` (1354-1470; read it whole, it is the spec), `due_for_automatic_send` (1043-1086), `_as_utc` (897), `signature_dates_stale` (974), `blocked_as_duplicate` (1142), `auto_attempts` (1182), `guest_filed_by_hand` (2117), `reservation_deadline_anchor` (2267, the `guests=None` path). Constants: `AUTOMATIC_SEND_DEADLINE_MARGIN_HOURS = 6` (68), `SUBMISSION_MAX_AUTO_ATTEMPTS = 1` (96), state names near the top. `App/app/deadlines.py` 19-44 (`is_working_day`, `add_working_days`, `reporting_deadline`; holidays are working days). `App/app/config.py` 408 (`UBYHOST_RESTRICTED_BLOCKS_FILING`) and 438 (`TIMEZONE = "Europe/Prague"`). `App/app/db.py` `ENCRYPTED_GUEST_COLUMNS` (2327) and `decrypt_field` (2380-2400): no ciphertext gives the plain column verbatim, a token that will not decrypt is an error, never an empty value.
- Already in Go: `validation.GuestIsComplete`, `validation.GuestIsReportable`, `validation.ParseISODate` (0555, `go/internal/validation`); `IsDuplicate` (`ubyport/codes.go`); `ubyport.Guest`, `Reservation`, `Apartment` (request.go), `ApartmentRef` (notify.go), `OutcomeGuest` (outcome.go), `BatchPair` (submit.go), `ClaimPair` (claim.go), `UTCNow` (store.go); key loading `secure.LoadDataKeys` returning `*secure.MultiFernet` with `Decrypt(token, ttl, now)`.
- **Traps:**
  - Filter order and every `continue` follow Python line by line, including the one write: a non-reportable guest not in `not_required`/`sent` is set to `not_required` with `updated_at = UTCNow()`.
  - Python reads `r.archived_at IS NULL`, `status = 'active'` and `COALESCE(source,'') != 'demo'` for stays, and orders guests `r.date_from, g.id`. Same SQL, Postgres placeholders.
  - `registration_completed_at` is a text timestamp; `_as_utc` decides how it parses (naive means UTC). Copy its behaviour, including "unparseable means no send".
  - `submit_after_hours or 24`: 0 and NULL both mean 24.
  - The deadline is local Prague wall time 23:59:59 of the third working day, minus 6 hours, then converted to UTC with `time.LoadLocation("Europe/Prague")` (import `time/tzdata` if the container may lack zoneinfo; check `go/internal/ubyport/notify.go` for how 0553 did it and do the same).
  - `now` is a parameter (`func() time.Time`), so tests pin it.
  - The decrypt key: take a `FieldDecrypter func(token string) (string, error)` parameter, the mirror of `FieldEncrypter`; tests build it from `secure.LoadDataKeys` with a test secret like store_test.go does.
## 3. Files
New: `go/internal/ubyport/collect.go`, `go/internal/ubyport/collect_test.go`. Write `docs/tasks/0556-report.md`. Nothing else.
## 4. Steps
1. `collect.go`, top comment naming the Python lines:
   - `type ApartmentRow struct{ Apartment Apartment; Ref ApartmentRef; AutomationMode string; SubmitAfterHours int; Fields map[string]string }` (Fields is every text column, for `validation.ValidateApartment` in 0558) and `func LoadApartment(ctx, pool, id int64) (*ApartmentRow, error)` (nil, nil when missing).
   - `type CollectOptions struct{ OnlyGuestIDs []int64; IgnoreAutomation, AllowResend bool; IgnoreSchedule *bool; RestrictedBlocksFiling bool; Now func() time.Time; Decrypt FieldDecrypter }`.
   - `func CollectSendable(ctx, pool, aptID int64, o CollectOptions) ([]BatchPair, error)`; each pair fills `Guest`, `Reservation`, `Outcome` (id, reservation id, state, submitted_at, submission id, receipt submission id, attempts) and `Source`. Add the guest fields `SubmitBatch` or the claim step need only if they are missing from the existing types; prefer one small `GuestMeta` struct next to the pair over widening `ubyport.Guest`.
   - `func DueForAutomaticSend(mode string, submitAfterHours int, completedAt string, anchor *time.Time, now time.Time) bool` and `func ReportingDeadline(checkIn time.Time) time.Time` exported for the sweep and tests.
2. `collect_test.go` (database tests; run them, `UBYHOST_TEST_DATABASE_URL` is set): one test per `continue` branch (demo stay, restricted on/off, Czech guest set to not_required, hand-filed, blocked, blocked duplicate with allow_resend, attempts cap, in-doubt pointer, incomplete, stale signature dates, manual mode, no completion, delay not reached, deadline margin pulls the send earlier, immediate mode), an encrypted doc number read back plain, a bad token returning an error, `only_guest_ids`, order by stay start then id. Table tests for `ReportingDeadline`: Monday, Friday, Saturday, Sunday check-ins, and one across the October DST change.
3. Commit: `0556: Go collect_sendable with decrypt and send schedule`.
## 5. Do not touch
`App/` (all), every other file in `go/`, `go.mod`/`go.sum`, compose, CI, templates/CSS/JS.
## 6. Commands
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/ubyport/ -count=1 2>&1 | tail -30` with `UBYHOST_TEST_DATABASE_URL` set; report the skip count (must be 0).
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
`git diff --stat origin/main` lists only section 3 files and this brief. All ubyport tests pass with 0 skipped.
## 8. Stop and ask
Stop if the guest row needs a column the Go schema tests do not create, or if matching Python needs a new dependency.
## 9. Report
`docs/tasks/0556-report.md`: command tails, diff stat, anything you decided beyond section 2.
