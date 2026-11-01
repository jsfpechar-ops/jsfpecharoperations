# 0557: Go police: stale batch recovery and stay completion refresh
Status: todo
Depends on: 0556 | Base commit: main | Branch: claude/project-thread-dwlrdj
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
Plan v4 step 17 (G5), rule 1. Go gets the two steps the sweep runs before it collects guests: `RecoverStaleSubmissions` (a batch left `running` after a crash becomes `outcome_unknown`) and `RefreshRegistrationCompletedAt` (a stay whose forms are done gets its completion stamp, which starts the send clock). Nothing calls the new code; nothing changes in production.
## 2. Context
- Python source of truth, `App/app/reporting.py`: `recover_stale_submissions` (1851-1912), `refresh_registration_completed_at` (923-972), `_forms_quiet_for` (908), `_as_utc` (897), `reservation_progress` (395-460, only the keys the refresh reads: `guests`, `expected`, `filled`, `incomplete`), `expected_guest_count` (350), `guest_filed_by_hand` (2117). Constants: `SUBMISSION_CLAIM_TTL_SECONDS` (59), `STALE_SUBMISSION_REASON` (64), `HEADCOUNT_QUIET_HOURS` (110), `SENT` near the top.
- Already in Go: `validation.GuestIsComplete` (0555); `LoadApartment`, the guest loader and `FieldDecrypter` in `ubyport/collect.go` (0556); `RaiseAlert` (effects.go); `UTCNow` (store.go); the advisory lock call in claim.go line 62 shows how `db.lock_key` maps to Postgres (`pg_advisory_xact_lock(hashtext(name), id)`); use the same for `"submit_apartment"`.
- **Traps:**
  - `db.immediate()` is one transaction; the candidate scan is one transaction and each stale batch is its own transaction, both holding the `submit_apartment` lock, as Python.
  - `submission_claim.claimed_at` is epoch seconds (float); `live_after` is now minus 300 s, compared with `>=`.
  - `guest_ids` is a JSON text array; empty or NULL means `[]`, and an empty batch is always stale.
  - The guest pointer update keeps `submit_state != 'sent'` and `submission_id IS NULL OR submission_id < ?` exactly.
  - Alert text, kind, dedupe key and params byte-for-byte (`params={"property", "error"}`), raised once per call, only when something was stale.
  - The refresh reads guests with decrypted fields, because completeness needs them; reuse the 0556 loader, do not write a second one. `_forms_quiet_for` reads the newest guest `updated_at`; copy its parsing via `_as_utc`.
  - The clear branch only runs when `existing` is set and a form is actually incomplete; both writes set `updated_at = UTCNow()`.
  - `now` is a parameter so tests pin it.
## 3. Files
New: `go/internal/ubyport/recover.go`, `go/internal/ubyport/recover_test.go`. Allowed edits in `go/internal/ubyport/collect.go`: export the guest loader if 0556 left it unexported, and make the `today` passed to `validation.GuestIsComplete` the UTC date of `now()` (Python's `date.today()` runs in a UTC container), with one test. Write `docs/tasks/0557-report.md`. Nothing else.
## 4. Steps
1. `recover.go`, top comment naming the Python lines: `func RecoverStaleSubmissions(ctx, pool, aptID int64, now func() time.Time) (int, error)` and `func RefreshRegistrationCompletedAt(ctx, pool, reservationID int64, decrypt FieldDecrypter, now func() time.Time) (*string, error)` (returns the stamp, nil for none).
2. `recover_test.go` (database tests; run them): running batch with a live claim is left alone; one with an old claim, and one with no guests, become `outcome_unknown` with the reason, guests pointed at them except sent ones and ones already on a newer batch, one critical alert with the exact params; nothing stale raises nothing. Refresh: declared count reached, quiet forms after 12 h, not yet quiet, incomplete guest clears an existing stamp, existing stamp kept when all are complete, hand-filed guest counts as complete.
3. Commit: `0557: Go stale batch recovery and completion refresh`.
## 5. Do not touch
`App/` (all), every other file in `go/`, `go.mod`/`go.sum`, compose, CI, templates/CSS/JS.
## 6. Commands
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/ubyport/ -count=1 2>&1 | tail -30` with `UBYHOST_TEST_DATABASE_URL` set; report the skip count (must be 0).
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
`git diff --stat origin/main` lists only section 3 files and this brief. All ubyport tests pass with 0 skipped.
## 8. Stop and ask
Stop if matching Python needs a new dependency or a column the test schema lacks.
## 9. Report
`docs/tasks/0557-report.md`: command tails, diff stat, anything you decided beyond section 2.
