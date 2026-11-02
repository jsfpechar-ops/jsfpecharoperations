# 0686: Go dashboard calendar: DB tests
Status: todo
Depends on: 0685 | Base commit: task/0682-go-calendar | Branch: task/0682-go-calendar (worktree /tmp/wt0682)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 80k tokens
## 1. Objective
Brief 0682 step 3: DB tests for `GET /dashboard/calendar` in `go/internal/calendar/handler_test.go`, skipped without `UBYHOST_TEST_DATABASE_URL`, 0 skipped with it. Copy the DB test setup (schema, seeding, signed-in session cookie) from `go/internal/palette/palette_test.go`.
## 2. Context
First fix (review of 0685): `handler.go` swallows the `hostweb.Login` response into a discard writer and answers 401 JSON. Python `calendar_data` returns `require_login`'s guard as-is (303 to `/login?next=...`, acceptance redirect, impersonation-expired handling). Pass the real `w` to `hostweb.Login` and just `return` when it gives a nil host; drop `discard` if unused. Also check the assumed column types (active, date_from/date_to, declared_guests, expected_guests_override, identity_verified_at, manual_filed_at, submitted_at) against `App/app/migrations/` or `go/internal/schema` and fix scans.
Cases to cover:
Signed out -> 303 to `/login?next=/dashboard/calendar`; another owner's stay absent; archived stay, archived apartment and inactive apartment absent (inactive apartment also absent from `properties`); cancelled stay absent; stay ending exactly on `from` included, starting on `to` excluded; `property` filter; property of another owner -> 404; bad range -> 422 with `Cache-Control: no-store`; foreign guest complete + identity verified + not sent -> status ready, tone ready; same stay with source demo -> preview true and tone not ready; one guest sent with submitted_at -> reported, tone done; apartment checkin_hour NULL -> displayStart `T12:00` and timingFallback true; exact byte output for one small fixture (hardcode the expected JSON string). Guest document columns must be encrypted with the test data key the way other Go DB tests do (grep `EncryptString` in go/internal tests).
## 3. Files
Create `go/internal/calendar/handler_test.go`. Fix bugs the tests find in `go/internal/calendar` only. Append a 0686 section to `docs/tasks/0682-report.md`, set both 0682 and 0685/0686 brief Status lines to review. Commit `0686: Go calendar DB tests`.
## 4. Steps
Write the tests, run, fix, commit.
## 5. Do not touch
Everything outside `go/internal/calendar` and the report.
## 6. Commands
Own database: `su postgres -c "createdb ubyhost0686" 2>&1 | tail -2`. From `/tmp/wt0682/go`: `test -z "$(gofmt -l .)" && go vet ./... && UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/ubyhost0686 go test ./internal/calendar/ ./cmd/... -count=1 -v 2>&1 | grep -E "^(--- |ok|FAIL|PASS)" | tail -40`. Repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
All calendar tests pass with the DB URL set, 0 skipped.
## 8. Stop and ask
If a test reveals a Python/Go difference you cannot resolve in 2 tries, record it in the report and move on.
## 9. Report
Append a 0686 section to `docs/tasks/0682-report.md` with the test tail and known differences.
