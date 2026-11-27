# Report 2091: Go check-in-anchored per-guest auto-filing

- Implemented `go/internal/ubyport/schedule.go` (`EffectiveCheckinHour`, `ScheduledSendAt`) and `schedule_test.go`.
- Updated `go/internal/ubyport/collect.go` and `completion_submit.go` so auto-filing never fires before `checkin_hour` (fallback `15:00` Prague), applies per-guest `COALESCE(filled_at, updated_at, created_at)`, and caps at `ReportingDeadline - 6h`.
- Verified green with Postgres 16: `go test ./internal/ubyport/... ./internal/web/staydetail/... -count=1`.
