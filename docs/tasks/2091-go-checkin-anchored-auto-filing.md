# 2091: Go check-in-anchored per-guest automatic police filing

Status: todo
Depends on: none | Base commit: 52c418cf5 | Branch: task/2091-go-checkin-anchored-auto-filing
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Anchor automatic UbyPort filing (`scheduled` and `immediate`) to check-in time (`guestAnchor` date at `apartment.checkin_hour`, defaulting to `15:00` Europe/Prague when `NULL`) on a **per-guest** basis so UbyHost never auto-files guests before they arrive, completed guests on a partial stay (e.g. `2/3`) file on schedule without waiting for missing co-guests, and every filing stays clamped to `ReportingDeadline - 6h`. Gate `SubmitCompletedStay` on the same rule so early guest submissions in `immediate` mode wait until check-in.

## 2. Context

- **Tier A (filing/UbyPort):** Go only — never touch `App/` (owner 2026-11-27).
- Plan: `docs/plans/checkin-anchored-auto-filing.md`.
- Statutory rules: `ReportingDeadline(anchor)` is `23:59:59` Prague time on the 3rd working day (decision D3); hard safety cap is `ReportingDeadline(anchor) - 6h` (decision 2026-11-09, brief 1070).
- **Per-guest formula (owner confirmed 2026-11-27)** for `ScheduledSendAt(mode string, submitAfterHours int, checkinHour *int64, submittedAt string, anchor *time.Time) (time.Time, bool)`:
  - `mode == "manual"`: returns `(time.Time{}, false)`.
  - `latest` (when `anchor != nil`): `ReportingDeadline(*anchor).Add(-collectMarginHours * time.Hour)`.
  - `checkInMoment` (when `anchor != nil`): `anchor` date (Y/M/D) at `h:00:00` in `Europe/Prague`, where `h = 15` (`DefaultCheckinHour`) unless `checkinHour != nil && *checkinHour >= 0 && *checkinHour <= 23`.
  - If `submittedAt == ""` or unparseable: returns `(latest, true)` when `anchor != nil`, else `(time.Time{}, false)`.
  - Otherwise:
    - `hours := submitAfterHours`; if `hours <= 0 { hours = DefaultSubmitAfterHours }` (`24`); if `mode == "immediate" { hours = 0 }`.
    - `sendAt := submitted.Add(time.Duration(hours) * time.Hour)`.
    - If `anchor != nil`: `afterCheckIn := checkInMoment.Add(time.Duration(hours) * time.Hour)`; if `afterCheckIn.After(sendAt) { sendAt = afterCheckIn }`; if `latest.Before(sendAt) { sendAt = latest }`.
  - Returns `(sendAt, true)`.
- **Per-guest inputs in `CollectSendable`:**
  - `guestAnchor`: parsed `c.stayFrom` when valid ISO date, else parsed `st.dateFrom` (fallback `reservationDeadlineAnchor` if blank).
  - `guestSubmittedAt`: `COALESCE(NULLIF(g.filled_at,''), NULLIF(g.updated_at,''), NULLIF(g.created_at,''), '')` (if empty, falls back to `st.completed`).
  - Result: on a `2/3` stay, completed guests 1 & 2 file at `min(max(checkIn + 24h, guestSubmittedAt + 24h), deadline - 6h)` in Batch 1, and guest 3 files separately in Batch 2 when they finish.
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
	completed, err := RefreshRegistrationCompletedAt(ctx, pool, reservationID, dec, now)
	if err != nil {
		return false, err
	}
	if completed == nil || apt.AutomationMode != "immediate" {
		return false, nil
	}
```
```go
	var status, completedAt string
	var archived bool
	err = pool.QueryRow(ctx,
		`SELECT COALESCE(status, ''), archived_at IS NOT NULL, COALESCE(registration_completed_at, '')
		   FROM reservation WHERE id = $1 AND apartment_id = $2`,
		reservationID, apartmentID).Scan(&status, &archived, &completedAt)
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/ubyport/collect.go` | edit | Add `CheckinHour *int64` to `ApartmentRow`, load `jsonIntPtr(m, "checkin_hour")`, load `filledAt` (`COALESCE(NULLIF(g.filled_at,''), NULLIF(g.updated_at,''), NULLIF(g.created_at,''), '')`) in `LoadGuests`, add `DefaultCheckinHour = 15`, `DefaultSubmitAfterHours = 24`, `CheckInMoment`, `ScheduledSendAt`, update `DueForAutomaticSend`, evaluate per-guest `guestAnchor` + `filledAt` in `CollectSendable` |
| `go/internal/ubyport/completion_submit.go` | edit | Keep `RefreshRegistrationCompletedAt`, allow `immediate` per-guest send even on partial (`2/3`) stays once `now >= checkInMoment` by passing `IgnoreSchedule: &no` (or gating on `DueForAutomaticSend`), never sending before check-in |
| `go/internal/ubyport/collect_test.go` | edit | Update existing calls to pass `checkinHour` and add unit tests for early/on-time/late/cap/weekend/DST/nil-`checkinHour`/`immediate`/partial-`2/3`-stay cases |
| `go/internal/ubyport/completion_submit_test.go` | edit | Add tests proving `SubmitCompletedStay` defers before check-in, sends at/after check-in, and files complete guests on a partial `2/3` stay in `immediate` mode once check-in has started |
| `go/internal/web/staydetail/post_test.go` | edit | Update `DueForAutomaticSend` call signature (pass `checkinHour`) |

No other file may change.

## 4. Steps

1. In `go/internal/ubyport/collect.go`:
   - Add constants `DefaultCheckinHour = 15` and `DefaultSubmitAfterHours = 24`.
   - Add `CheckinHour *int64` to `ApartmentRow` and populate `CheckinHour: jsonIntPtr(m, "checkin_hour")` in `LoadApartment`.
   - Add `filledAt string` to `collectGuest` and select `COALESCE(NULLIF(g.filled_at,''), NULLIF(g.updated_at,''), NULLIF(g.created_at,''), '')` in `LoadGuests`.
   - Add exported helpers:
     - `CheckInMoment(anchor time.Time, checkinHour *int64) time.Time` returning `time.Date(y, m, d, hour, 0, 0, 0, pragueLoc)` (fallback `DefaultCheckinHour` when `checkinHour == nil || *checkinHour < 0 || *checkinHour > 23`).
     - `ScheduledSendAt(mode string, submitAfterHours int, checkinHour *int64, submittedAt string, anchor *time.Time) (time.Time, bool)` implementing the §2 formula.
   - Update `DueForAutomaticSend(mode string, submitAfterHours int, checkinHour *int64, submittedAt string, anchor *time.Time, now time.Time) bool` to delegate to `ScheduledSendAt`.
   - In `CollectSendable` (when `!ignoreSchedule`), compute per-guest anchor (`c.stayFrom` if valid ISO date, else `st.dateFrom`, else `reservationDeadlineAnchor`) and per-guest submit stamp (`c.filledAt`, fallback `st.completed`), and call `DueForAutomaticSend(ap.AutomationMode, ap.SubmitAfterHours, ap.CheckinHour, stamp, guestAnchor, now)`.
2. In `go/internal/ubyport/completion_submit.go`:
   - Always call `RefreshRegistrationCompletedAt` so `registration_completed_at` stays accurate.
   - Return `(false, nil)` when `apt.AutomationMode != "immediate"`.
   - Remove the early return on `completed == nil` (partial `2/3` stays may have complete guests ready to file once check-in starts!).
   - In `runImmediateStaySubmit`, set `IgnoreSchedule: &no` (i.e. `false`) so `CollectSendable` enforces the exact `DueForAutomaticSend` check-in gate per guest — pre-check-in saves become a no-op (no UbyPort call, no submission row), and at/after-check-in saves file every complete unfiled guest on that reservation immediately.
   - Return `true, nil` only when at least one batch was submitted (or keep existing return contract consistent with tests: check `len(results) > 0` before returning `true`).
3. Update `go/internal/web/staydetail/post_test.go` for the new `DueForAutomaticSend` parameter.
4. Update `go/internal/ubyport/collect_test.go`:
   - Update existing calls to pass `nil` or explicit `checkinHour`.
   - Add `TestScheduledSendAtCheckInAnchored` covering:
     - `scheduled` (24h, `checkin_hour=15`, Mon `2026-11-09` arrival): submitted Fri `2026-11-06` → due Tue `2026-11-10 15:00` Prague; submitted Mon `14:00` → Tue `15:00`; submitted Mon `20:00` → Tue `20:00`; submitted Tue `10:00` → Wed `10:00`; submitted Wed `14:00` → clamped Wed `17:59:59`.
     - Partial `2/3` stay (`registration_completed_at = NULL`): guests 1 & 2 submitted Friday → due Tue `15:00` (do NOT wait until Wed `17:59`!).
     - `scheduled` with `checkin_hour=nil` falls back to `15:00` Prague; custom `checkin_hour=12` uses `12:00` Prague.
     - `immediate`: submitted Fri before Mon `15:00` → NOT due before Mon `15:00`, due at Mon `15:00`; submitted Mon `18:00` → due immediately.
     - Weekend arrival (Sat `2026-11-07 15:00`): `scheduled` 24h → Sun `15:00`, deadline Wed `23:59:59`.
     - DST spring-forward / fall-back arrival date uses `Europe/Prague` wall clock for `checkInMoment` + elapsed hours.
     - Guest with blank timestamps falls back to `ReportingDeadline - 6h`; `manual` never due; `submitAfterHours <= 0` treated as `24`.
5. Update `go/internal/ubyport/completion_submit_test.go`:
   - For existing tests expecting immediate filing, set `date_from` on or before `now`.
   - Add subtests:
     - `"defers before check-in hour"` (`date_from: 2026-12-01`, `checkin_hour: 15`, `now: 2026-12-01 13:59 UTC` = `14:59` Prague → returns `(false, nil)`, `sender.calls == 0`, guest stays `pending`).
     - `"sends at check-in hour"` (`now: 2026-12-01 14:00 UTC` = `15:00` Prague → returns `(true, nil)`, `sender.calls == 1`, guest becomes `sent`).
     - `"partial 2/3 stay sends complete guests at/after check-in in immediate mode"`.
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
Expected: `ok` for all tested packages (note in report if DB tests were skipped due to missing `UBYHOST_TEST_DATABASE_URL`).

Run from repo root:
```bash
python3 scripts/context_lint.py 2>&1 | tail -30
```
Expected: `context lint: OK`.

## 7. Acceptance

- [ ] `ScheduledSendAt` and `DueForAutomaticSend` anchor both `scheduled` and `immediate` per-guest on `CheckInMoment` (`checkin_hour`, fallback `15:00` Prague) and guest submit time, clamped at `ReportingDeadline - 6h`.
- [ ] On a partial `2/3` stay, completed guests 1 & 2 file on their own schedule (`check-in + 24h`) without waiting for guest 3; guest 3 files in a separate batch when finished.
- [ ] `SubmitCompletedStay` never files before `CheckInMoment` and files immediately at/after `CheckInMoment`.
- [ ] `manual` never auto-files; `IgnoreSchedule: true` manual sends still work anytime.
- [ ] Zero files under `App/` changed; all §6 commands pass.

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
