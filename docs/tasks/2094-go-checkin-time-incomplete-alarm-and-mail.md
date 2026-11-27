# 2094: Go check-in-time incomplete-form alarm and second host email

Status: done
Depends on: 2091 | Base commit: 52c418cf5 | Branch: task/2094-go-checkin-time-incomplete-alarm-and-mail
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Ensure hosts always receive both a **day-before** nudge (at `18:00` the day before arrival) AND a **second email + in-app alarm at check-in time** (`date_from` at `apartment.checkin_hour`, fallback `15:00` Europe/Prague) when guest forms are still incomplete — instead of the check-in-day email being silently suppressed by a shared idempotency key. Wire the check-in-time pass directly into Go's live `deadlines` job (`go/internal/calendar/`) so it runs in production immediately in 100% Go without waiting for the `mail` job cutover (`1770`), and align `go/internal/mailjob/reminders.go` with the exact same keys so there are zero duplicates once `mail` moves to Go.

## 2. Context

- **Tier B (Go jobs & mail):** Go only — never touch `App/` (owner 2026-11-27).
- Plan: `docs/plans/checkin-anchored-auto-filing.md`.
- **Root cause of the current gap:**
  - Today `reminder_host` uses the **same** idempotency key `reminder_host:{resID}:{date}` for both the day-before `18:00` nudge and check-in morning `09:00`. If the day-before email went out, Postgres rejects the second insert and **no check-in-day email is ever sent**.
  - Today's check-in-day trigger also fires at fixed `09:00` instead of the property's `checkin_hour` (fallback `15:00`), and day-before skips stays where a guest opened/claimed the link but left forms unfinished.
- **Complete 5-stage host safety net (zero gaps, zero spam):**
  1. **Day before, `18:00` Prague:** if forms are incomplete (unclaimed OR claimed-but-unfinished), send day-before email (key `reminder_host:day_before:{resID}:{date}`).
  2. **At check-in time (`checkin_hour` ?? `15:00` Prague, check-in day):** if forms are STILL incomplete, raise/refresh warning alert `guest_incomplete_checkin` (`guest_incomplete_checkin:{resID}`) AND queue a **distinct** host email (key `reminder_host:checkin:{resID}:{date}`, `kind = "reminder_host"`). Resolves the alert automatically when forms complete or check-in day passes.
  3. **`< 24h` before statutory deadline** (existing `filing_watchdog.go`): `deadline_at_risk` email + push.
  4. **`deadline - 6h`** (existing `ubyport/collect.go`): hard auto-send cap files all complete guests.
  5. **`deadline - 3h`** (existing `filing_stalled.go`): critical `filing_stalled` alert + host/operator email + heartbeat `/fail`.
- **Why run Stage 2 in `calendar.RunDeadlinesJob` too:** `deadlines` already runs in Go every 30 min in production (`status.md`). Using the exact same `email_outbox.idempotency_key` (`reminder_host:checkin:{resID}:{date}`) and alert `dedupe_key` (`guest_incomplete_checkin:{resID}`) in both `calendar/checkin_alarm.go` and `mailjob/reminders.go` guarantees immediate production coverage AND zero duplicate emails once `mailjob` (`1770`) goes live.

Verbatim excerpts to match before editing:

`go/internal/calendar/deadlines_job.go`:
```go
type DeadlinesSummary struct {
	Alerts      int
	RequestsDue int
	Watchdog    WatchdogResult
	Stalled     int
}
```
```go
	return runDeadlines(deadlinesSteps{
		check: func() (int, error) { return CheckDeadlines(ctx, pool, getenv, at, nil) },
		// Python's date.today() is the server's local date (TZ unset: UTC).
		dsrDue:      func() (int, error) { return RaiseDSRDueAlerts(ctx, pool, at.Local()) },
		watchdog:    func() (WatchdogResult, error) { return RunFilingWatchdog(ctx, pool, lookupEnv, at) },
		stalled:     func() (int, error) { r, err := RunFilingStalled(ctx, pool, getenv, at); return r.Stalled, err },
		raiseFailed: func() error { return jobs.RaiseFailed(ctx, pool, "deadlines") },
		ping:        ping,
		getenv:      getenv,
	})
```

`go/internal/mailjob/reminders.go`:
```go
		// 0245 (idea E): nobody has opened the guest link by 18:00 the day before arrival.
		// The mail key is the check-in-day key, so a stay never gets a second host reminder.
		early := start.Equal(tomorrow) && hour >= 18 && r.ClaimState == "" && !complete &&
			p.Status != "reported" && p.Status != "not_required" && r.Source != "demo"
		if early || (start.Equal(today) && !complete && hour >= 9) {
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/mailnotify/reminder.go` | edit | Add `CheckInStarted bool` and `CheckInHour int` to `ReminderHostInput`; build distinct check-in-time subject/intro/preheader/footer when `CheckInStarted` is true |
| `go/internal/mailnotify/i18n_strings.json` | edit | Add `mail.reminder_host.*_checkin` keys in `cs`, `en`, `vi` (no em-dashes) |
| `go/internal/mailnotify/reminder_test.go` | edit | Add unit tests for `BuildReminderHost` with `CheckInStarted: true` (claimed partial vs unclaimed) |
| `go/internal/calendar/checkin_alarm.go` | create | `RunCheckInIncompleteAlarm(ctx, pool, getenv, at)`: checks active non-demo stays arriving today once `now >= checkInMoment` (`checkin_hour` ?? `15:00` Prague), resolves alert when complete or past check-in day, raises `guest_incomplete_checkin` alert and enqueues `reminder_host` with key `reminder_host:checkin:{resID}:{date}` when incomplete |
| `go/internal/calendar/deadlines_job.go` | edit | Add `CheckInAlarms int` to `DeadlinesSummary` and call `RunCheckInIncompleteAlarm` inside `RunDeadlinesJob` / `runDeadlines` (errors logged without blocking `watchdog` or `stalled` heartbeat) |
| `go/internal/calendar/checkin_alarm_test.go` | create | DB/unit tests: does not fire before `checkin_hour`; fires at `checkin_hour` (and `15:00` when `checkin_hour` is NULL); fires even when day-before `reminder_host:{resID}:{date}` already exists; idempotent on repeat runs; skips completed/demo/reported stays; resolves alert once forms complete |
| `go/internal/mailjob/reminders.go` | edit | Select `a.checkin_hour`; trigger day-before (`hour >= 18`, incomplete, key `reminder_host:day_before:{resID}:{date}`) and check-in-time (`hour >= checkinHour`, incomplete, `CheckInStarted: true`, key `reminder_host:checkin:{resID}:{date}`) |
| `go/internal/mailjob/reminders_test.go` | edit | Update/add tests confirming both day-before AND check-in-time host emails queue with distinct keys and respect `checkin_hour` |

No other file may change.

## 4. Steps

1. In `go/internal/mailnotify/reminder.go` and `i18n_strings.json`:
   - Add `CheckInStarted bool` and `CheckInHour int` to `ReminderHostInput`.
   - When `CheckInStarted` is true, format check-in hour as `fmt.Sprintf("%02d:00", hour)` and render dedicated keys (`mail.reminder_host.subject_checkin`, `subject_checkin_unclaimed`, `preheader_checkin`, `intro_checkin`, `footer_checkin`) in `cs`, `en`, `vi` (e.g. EN intro: `"Check-in for %(property)s started at %(hour)s today (%(date)s), and guest registration is still incomplete."`). No em-dashes.
   - Add tests in `go/internal/mailnotify/reminder_test.go`.
2. Create `go/internal/calendar/checkin_alarm.go`:
   - Query active non-archived non-demo stays on active non-archived apartments where `r.date_from <= today` (bounded to recent stays, e.g. last 7 days through today) including `a.checkin_hour`, `a.legal_entity_id`, `a.owner_user_id`, `a.internal_name`, `a.uby_name`, and `reservation_claim` fields (`state`, `email_masked`).
   - Compute `AlertProgresses` and check `formsComplete`:
     - If complete or `start < today`: resolve `guest_incomplete_checkin:{resID}`.
     - If `start == today` and `!complete` and `status not in ("reported", "not_required")`:
       - Compute `checkInHour := ubyport.DefaultCheckinHour` (15), overridden by `a.checkin_hour` when `0..23`.
       - If `localNow.Hour() < checkInHour`: continue (not check-in time yet).
       - Raise warning alert `guest_incomplete_checkin` (`dedupe_key = "guest_incomplete_checkin:<id>"`).
       - Look up legal entity contact email; if present and `watchdogMailEnabled(getenv)`, build `mailnotify.BuildReminderHost` with `CheckInStarted: true, CheckInHour: checkInHour` and insert into `email_outbox` with `ON CONFLICT (idempotency_key) DO NOTHING` using key `fmt.Sprintf("reminder_host:checkin:%d:%s", resID, startStr)` and `kind = "reminder_host"`.
3. Wire `RunCheckInIncompleteAlarm` into `go/internal/calendar/deadlines_job.go`:
   - Add `checkIn func() (int, error)` step in `deadlinesSteps` (optional nil-safe for existing unit tests) and `CheckInAlarms int` on `DeadlinesSummary`.
   - Run it after `dsrDue` (before `watchdog`) so an error is logged/flagged without ever preventing `watchdog`, `stalled`, or the filing heartbeat from running.
4. Update `go/internal/mailjob/reminders.go`:
   - Select `a.checkin_hour` in `reminderRowsSQL` and scan into `r.CheckinHour *int64`.
   - Day-before (`start == tomorrow && hour >= 18 && !complete && status not in ("reported", "not_required") && source != "demo"`): enqueue with key `reminder_host:day_before:{resID}:{date}` (`Tomorrow: true`).
   - Check-in-time (`start == today && hour >= checkInHour && !complete && status not in ("reported", "not_required") && source != "demo"`): raise `guest_incomplete_checkin` alert and enqueue with key `reminder_host:checkin:{resID}:{date}` (`CheckInStarted: true, CheckInHour: checkInHour`).
5. Add and run tests in `checkin_alarm_test.go`, `reminders_test.go`, `reminder_test.go`; run §6 commands.

## 5. Do not touch

- Anything under `App/` (Python is retired; owner 2026-11-27).
- `go/internal/calendar/filing_watchdog.go` and `filing_stalled.go` (existing `<24h` and `-3h` alarms unchanged).
- `go/migrations/` (no schema change; reuses existing `email_outbox` and `alert` tables).
- Hard rules: never block the filing heartbeat; never emit personal guest names into alert text or logs; no new dependency.

## 6. Commands

Run from `go/`:
```bash
go test ./internal/calendar/... ./internal/mailjob/... ./internal/mailnotify/... 2>&1 | tail -30
```
Expected: `ok` for all 3 packages.

Run from repo root:
```bash
python3 scripts/context_lint.py 2>&1 | tail -30
```
Expected: `context lint: OK`.

## 7. Acceptance

- [ ] A stay with incomplete forms receives **both** the day-before reminder email (18:00 day before) AND a second check-in-time email + `guest_incomplete_checkin` alert once `checkin_hour` (fallback `15:00` Prague) arrives on check-in day.
- [ ] Check-in-time alarm runs inside Go's live `deadlines` job (`calendar.RunDeadlinesJob`) and shares the exact idempotency key `reminder_host:checkin:{resID}:{date}` with `mailjob/reminders.go`, so zero duplicate emails occur even when both run.
- [ ] Completing the forms (or passing check-in day) automatically resolves `guest_incomplete_checkin`.
- [ ] Demo, cancelled, already-complete, and already-reported stays never trigger the alarm or email.
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

Write `docs/tasks/2094-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/calendar/deadlines_job.go` (verify `watchdog` / `stalled` / filing heartbeat are never blocked by the new step)
- `go/internal/calendar/checkin_alarm.go` (idempotency key, demo/reported exclusions, no guest PII in alerts)
- `go/internal/mailjob/reminders.go` (distinct day-before vs check-in-time keys)

## Owner steps

1. Merge PR after green CI with `scripts/merge-pr-on-green.sh <PR>`.
2. On staging, create a stay for today with `checkin_hour` set to the current Prague hour and no guests, trigger `deadlines`, and verify one `guest_incomplete_checkin` alert and one `reminder_host` email with key `reminder_host:checkin:<id>:<today>` are queued.
