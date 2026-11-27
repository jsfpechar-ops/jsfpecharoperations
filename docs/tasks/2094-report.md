# Report 2094: Check-in-time incomplete alarm & distinct second host email

- Created `go/internal/calendar/checkin_alarm.go` + tests and wired `RunCheckInIncompleteAlarm` into `RunDeadlinesJob` without blocking `watchdog`/`stalled`/heartbeat.
- Split host reminder idempotency keys in `go/internal/mailjob/reminders.go` (`reminder_host:day_before:{id}:{date}` vs `reminder_host:checkin:{id}:{date}`) and added check-in-started mail copy in `mailnotify` (`cs`/`en`/`vi`).
- Verified green with Postgres 16: `go test ./internal/calendar/... ./internal/mailjob/... ./internal/mailnotify/... -count=1`.
