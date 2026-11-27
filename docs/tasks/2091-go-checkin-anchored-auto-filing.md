# 2091: Go check-in-anchored automatic police filing

Status: todo
Depends on: none | Base commit: 52c418cf5 | Branch: task/2091-go-checkin-anchored-auto-filing
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Anchor automatic UbyPort filing (`scheduled` and `immediate`) to check-in time (`anchor` date at `apartment.checkin_hour`, defaulting to `15:00` Europe/Prague when `NULL`) so UbyHost never auto-files guests before they arrive, while preserving both the post-submit review delay and the statutory `ReportingDeadline - 6h` safety cap. Gate `SubmitCompletedStay` on the same rule so early guest submissions in `immediate` mode wait until check-in.

## 2. Context

- **Tier A (filing/UbyPort):** Go only — never touch `App/` (owner 2026-11-27).
- Plan: `docs/plans/checkin-anchored-auto-filing.md`.
- Statutory rules: `ReportingDeadline(anchor)` is `23:59:59` Prague time on the 3rd working day (decision D3); hard safety cap is `ReportingDeadline(anchor) - 6h` (decision 2026-11-09, brief 1070); incomplete stays (`completedAt == ""`) still file at `latest = ReportingDeadline(anchor) - 6h`.
- Formula for `ScheduledSendAt(mode string, submitAfterHours int, checkinHour *int64, completedAt string, anchor *time.Time) (time.Time, bool)`:
  - `mode == "manual"`: returns `(time.Time{}, false)`.
  - `latest` (when `anchor != nil`): `ReportingDeadline(*anchor).Add(-collectMarginHours * time.Hour)`.
  - `checkInMoment` (when `anchor != nil`): `anchor` date (Y/M/D) at `h:00:00` in `Europe/Prague`, where `h = 15` (`DefaultCheckinHour`) unless `checkinHour != nil && *checkinHour >= 0 && *checkinHour <= 23`.
  - If `completedAt == ""` or unparseable: returns `(latest, true)` when `anchor != nil`, else `(time.Time{}, false)`.
  - Otherwise:
    - `hours := submitAfterHours`; if `hours <= 0 { hours = DefaultSubmitAfterHours }` (`24`); if `mode == "immediate" { hours = 0 }`.
    - `sendAt := completed.Add(time.Duration(hours) * time.Hour)`.
    - If `anchor != nil`: `afterCheckIn := checkInMoment.Add(time.Duration(hours) * time.Hour)`; if `afterCheckIn.After(sendAt) { sendAt = afterCheckIn }`; if `latest.Before(sendAt) { sendAt = latest }`.
  - Returns `(sendAt, true)`.
- `DueForAutomaticSend` returns `ok && !now.Before(sendAt)`.

Verbatim excerpts to match before editing:

`go/internal/ubyport/collect.go`:
```go
type ApartmentRow struct {
	Apartment        Apartment
	Ref              ApartmentRef
	AutomationMode   string
	SubmitAfterHours int
	Fields           map[string]string
}
```
```go
		AutomationMode:   fields["automation_mode"],
		SubmitAfterHours: int(jsonInt(m, "submit_after_hours")),
		Fields:           fields,
```
```go
			if !DueForAutomaticSend(ap.AutomationMode, ap.SubmitAfterHours, st.completed, anchor, now) {
				continue
			}
```
```go
func DueForAutomaticSend(mode string, submitAfterHours int, completedAt string, anchor *time.Time, now time.Time) bool {
```

`go/internal/ubyport/completion_submit.go`:
```go
	var status, completedAt string
	var archived bool
	err = pool.QueryRow(ctx,
		`SELECT COALESCE(status, ''), archived_at IS NOT NULL, COALESCE(registration_completed_at, '')
		   FROM reservation WHERE id = $1 AND apartment_id = $2`,
		reservationID, apartmentID).Scan(&status, &archived, &completedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	if status != "active" || archived || completedAt == "" {
		return false, nil
	}
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/ubyport/collect.go` | edit | Add `CheckinHour *int64` to `ApartmentRow`, load `jsonIntPtr(m, "checkin_hour")`, add `DefaultCheckinHour = 15`, `DefaultSubmitAfterHours = 24`, `CheckInMoment`, `ScheduledSendAt`, update `DueForAutomaticSend` |
| `go/internal/ubyport/completion_submit.go` | edit | Select `COALESCE(date_from, '')`, compute `reservationDeadlineAnchor`, gate immediate send on `DueForAutomaticSend` |
| `go/internal/ubyport/collect_test.go` | edit | Update existing calls to pass `checkinHour` and add unit tests for early/on-time/late/cap/weekend/DST/nil-`checkinHour`/`immediate`/incomplete cases |
| `go/internal/ubyport/completion_submit_test.go` | edit | Add tests proving `SubmitCompletedStay` defers before check-in and sends at/after check-in (update existing fixtures where `now` is before `date_from`) |
| `go/internal/web/staydetail/post_test.go` | edit | Update `DueForAutomaticSend` call signature (pass `checkinHour`) |

No other file may change.

## 4. Steps

1. In `go/internal/ubyport/collect.go`:
   - Add constants `DefaultCheckinHour = 15` and `DefaultSubmitAfterHours = 24`.
   - Add `CheckinHour *int64` to `ApartmentRow` and populate `CheckinHour: jsonIntPtr(m, "checkin_hour")` in `LoadApartment`.
   - Add exported helpers:
     - `CheckInMoment(anchor time.Time, checkinHour *int64) time.Time` returning `time.Date(y, m, d, hour, 0, 0, 0, pragueLoc)` (fallback `DefaultCheckinHour` when `checkinHour == nil || *checkinHour < 0 || *checkinHour > 23`).
     - `ScheduledSendAt(mode string, submitAfterHours int, checkinHour *int64, completedAt string, anchor *time.Time) (time.Time, bool)` implementing the §2 formula.
   - Update `DueForAutomaticSend(mode string, submitAfterHours int, checkinHour *int64, completedAt string, anchor *time.Time, now time.Time) bool` to delegate to `ScheduledSendAt`.
   - Pass `ap.CheckinHour` from `CollectSendable`.
2. In `go/internal/ubyport/completion_submit.go`:
   - Extend the reservation query to also select `COALESCE(date_from, '')` into `dateFrom`.
   - Compute `anchor, err := reservationDeadlineAnchor(ctx, pool, reservationID, dateFrom)`.
   - Compute `current := time.Now(); if now != nil { current = now() }`.
   - If `!DueForAutomaticSend(apt.AutomationMode, apt.SubmitAfterHours, apt.CheckinHour, completedAt, anchor, current) { return false, nil }`.
   - Keep `IgnoreSchedule: &yes` inside `runImmediateStaySubmit` once the gate passes.
3. Update `go/internal/web/staydetail/post_test.go` for the new `DueForAutomaticSend` parameter.
4. Update `go/internal/ubyport/collect_test.go`:
   - Update existing calls to pass `nil` or explicit `checkinHour`.
   - Add `TestScheduledSendAtCheckInAnchored` covering:
     - `scheduled` (24h, `checkin_hour=15`, Mon `2026-11-09` arrival): completed Fri `2026-11-06` → due Tue `2026-11-10 15:00` Prague; completed Mon `14:00` → Tue `15:00`; completed Mon `20:00` → Tue `20:00`; completed Tue `10:00` → Wed `10:00`; completed Wed `14:00` → clamped Wed `17:59:59`.
     - `scheduled` with `checkin_hour=nil` falls back to `15:00` Prague.
     - `scheduled` with custom `checkin_hour=12` uses `12:00` Prague.
     - `immediate`: completed Fri before Mon `15:00` → NOT due before Mon `15:00`, due at Mon `15:00`; completed Mon `18:00` → due immediately.
     - Weekend arrival (Sat `2026-11-07 15:00`): `scheduled` 24h → Sun `15:00`, deadline Wed `23:59:59`.
     - DST spring-forward / fall-back arrival date uses `Europe/Prague` wall clock for `checkInMoment` + elapsed hours.
     - Incomplete stay (`completedAt == ""`) still due at `ReportingDeadline - 6h` for both `scheduled` and `immediate`, never for `manual`.
     - `submitAfterHours <= 0` treated as `24`.
5. Update `go/internal/ubyport/completion_submit_test.go`:
   - For existing tests expecting immediate filing, set `date_from` on or before `now` (e.g. `2026-11-01`).
   - Add subtests:
     - `"defers before check-in hour"` (`date_from: 2026-12-01`, `checkin_hour: 15`, `now: 2026-12-01 13:59 UTC` = `14:59` Prague → returns `(false, nil)`, `sender.calls == 0`, guest stays `pending`).
     - `"sends at check-in hour"` (`now: 2026-12-01 14:00 UTC` = `15:00` Prague → returns `(true, nil)`, `sender.calls == 1`, guest becomes `sent`).
     - `"null checkin_hour falls back to 15:00 Prague"`.
6. Run §6 commands.

## 5. Do not touch

- Anything under `App/` (Python is retired; owner 2026-11-27).
- `go/internal/deadlines/deadlines.go` (statutory D3 deadline unchanged).
- `go/internal/calendar/filing_stalled.go` and `filing_watchdog.go` (alarms unchanged).
- `go/internal/ubyport/soap.go`, `client.go`, `claim.go`, `outcome.go`, `response.go`.
- Hard rules: UbyPort filing correctness beats everything; no DB migration; no new dependency.

## 6. Commands

Run from `go/`:
```bash
go test ./internal/ubyport/... ./internal/web/staydetail/... ./internal/calendar/... 2>&1 | tail -30
```
Expected: `ok` for all tested packages (if `UBYHOST_TEST_DATABASE_URL` is set, DB tests pass; note in report if DB tests were skipped due to env).

Run from repo root:
```bash
python3 scripts/context_lint.py 2>&1 | tail -30
```
Expected: `context lint: OK`.

## 7. Acceptance

- [ ] `ScheduledSendAt` and `DueForAutomaticSend` anchor both `scheduled` and `immediate` on `CheckInMoment` (`checkin_hour`, fallback `15:00` Prague) and `completedAt`, clamped at `ReportingDeadline - 6h`.
- [ ] `SubmitCompletedStay` never files before `CheckInMoment` and files immediately at/after `CheckInMoment`.
- [ ] Incomplete stays still file complete guests at `ReportingDeadline - 6h`; `manual` never auto-files; `IgnoreSchedule: true` manual sends still work anytime.
- [ ] Zero files under `App/` changed.
- [ ] All §6 commands pass.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/2091-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/ubyport/collect.go` (full diff — Tier A filing scheduler)
- `go/internal/ubyport/completion_submit.go` (full diff — Tier A immediate completion gate)

## Owner steps

1. After CI is green on PR, merge with `scripts/merge-pr-on-green.sh <PR>`.
2. After deploy, run one Gate 2 spot-check in `UBYHOST_UBYPORT_ENV=test` verifying a future-dated stay does not send early and an arrived stay files with Doručenka PDF.
