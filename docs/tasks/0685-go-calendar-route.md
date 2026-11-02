# 0685: Go dashboard calendar: progress, events query, route
Status: todo
Depends on: 0682 partial (commit 9485212) | Base commit: task/0682-go-calendar | Branch: task/0682-go-calendar (same worktree /tmp/wt0682)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 80k tokens
## 1. Objective
Finish brief 0682 step 1 (the DB tests are brief 0686, not this one). Build on the pure helpers already in `go/internal/calendar/calendar.go`. Read `docs/tasks/0682-go-dashboard-calendar.md` sections 2 and 5 for rules; this brief narrows scope and gives you the exact pieces.
## 2. Context
Rules as in 0682 section 2. Pieces below.
## 3. Files
Create `go/internal/calendar/progress.go`, `handler.go`, extend `calendar_test.go`. Edit `go/cmd/ubyhost-web/main.go` (one line), at most small exports in `go/internal/ubyport` (one-line doc comment each). Update `docs/tasks/0682-report.md` (append a 0685 section). Commit `0685: Go calendar progress, events query and route` with the trailers you were given.
## 4. Steps
What to write (all in `go/internal/calendar`, new file `progress.go` + `handler.go`)
1. `urgency(checkIn, nowLocal)`: port `App/app/deadlines.py` `urgency`/`hours_left` (lines 41-79) using exported `ubyport.ReportingDeadline` (23:59:59 of the third working day; check its signature). Local time = Europe/Prague naive (`time.LoadLocation("Europe/Prague")`, as `ubyport` does for `reportingToday`; reuse it).
2. `progress(stay, guests, today)`: port `reporting.reservation_progress` (App/app/reporting.py 395-468) returning only what the calendar needs: guest count, filled, expected (*int), status, reportable guests. Completeness: `validation.GuestIsComplete(row, stay.dateFrom, stay.dateTo, today)` (check it covers `_stay_dates` + signature, like `reporting.guest_issues` 319-331; if it does not, say so in the report). Filed by hand: `submit_state == "sent" && manual_filed_at != ""`. Verified: not reportable, or `identity_verified_at != ""`. Sent = `"sent"`; failed = `"error"` or `"blocked"` (check constants in reporting.py top). Expected: `expected_guests_override` if nonzero else `declared_guests` (nullable).
3. Deadline anchor: earliest parseable guest `stay_from`, else stay `date_from` (reporting.py 2306-2331), computed from the loaded guests, no extra query. Filed at: latest of reportable guests' `manual_filed_at` or `submitted_at` (parse as stored UTC with the parser `ubyport` uses, export it with a one-line doc comment if unexported), converted to Prague naive; by_hand from the latest one. Feed the existing `deadlineCell`.
4. Guest query: ONE query for all stays: `SELECT id, reservation_id, nationality, submit_state, manual_filed_at, submitted_at, identity_verified_at, stay_from, stay_to, and the encrypted/plain columns validation.GuestRow needs` `FROM guest WHERE reservation_id = ANY($1) AND archived_at IS NULL ORDER BY reservation_id, is_lead DESC, id`. Decrypt exactly the columns `ubyport.LoadGuests` decrypts, the same way (read `LoadGuests` 425-505 and copy its column list/decrypt calls; prefer exporting a small helper over copying more than ~20 lines). Decrypter: `secure.LoadDataKeys(getenv)` as `go/internal/pushweb/pushweb.go:116` does. If a guest will not decrypt: return 500 (Python's per-stay fallback then fails the request too).
5. Events query: copy the SQL from `dashboard_calendar.py` `events` (64-73) to `$n` placeholders, `a.owner_user_id IS NOT DISTINCT FROM $1`, ordering `r.date_from, r.date_to, r.id`. Select only the columns used. Tone = existing `tone(level, status, preview)` with level from `deadlineCell`. Preview = `source == "demo"` (check `DEMO_STAY_SOURCE` in App/app/demo.py).
6. Handler `Handler(pool, getenv, now)` with the signature style of `go/internal/palette` (`palette.Handler`): login guard as palette does; parse `from`/`to`/`property` (property: empty -> none; must be a positive int else 422); properties list = owner's non-archived apartments with `active` true, ordered by internal_name (palette `apartmentRows` pattern); property not in list -> 404. Response: ordered JSON struct `{"properties":[{"id","name"}],"events":[...]}` with event keys in this order: id, propertyId, property, label, start, end, displayStart, displayEnd, timingFallback, guests, complete, expected, status, tone, preview, source, url. `url` = `/reservations/<id>?return_to=/`. Compact JSON, `SetEscapeHTML(false)`, trim the newline, header `Content-Type: application/json`, `Cache-Control: no-store` on every response (also 401/422/404; check what palette's guard returns and do the same).
7. Register `GET /dashboard/calendar` in `go/cmd/ubyhost-web/main.go` like the palette line.
8. Unit tests (no DB) for `progress` statuses (failed, awaiting_guest, incomplete via missing, incomplete via unfinished guest, awaiting_verification, ready, reported, not_required), `urgency` buckets, anchor choice, JSON key order of one event struct.
## 5. Do not touch
Same as 0682 section 5. No DB tests here (0686).
## 6. Commands
From `/tmp/wt0682/go`: `test -z "$(gofmt -l .)" && go vet ./... && go build ./... && go test ./internal/calendar/ ./internal/ubyport/ ./cmd/... -count=1 2>&1 | tail -30`. Repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
Package builds, unit tests pass, route registered.
## 8. Stop and ask
Stop and report if a step needs a schema change or new dependency. If you reach 25 tool calls, commit what builds and report what is left.
## 9. Report
Append a 0685 section to `docs/tasks/0682-report.md`: command tails, `git diff --stat origin/main`, decisions, known differences.
