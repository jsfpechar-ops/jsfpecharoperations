# 0682: Go dashboard calendar JSON
Status: blocked
Depends on: 0676 (hostweb, on main) | Base commit: origin/main | Branch: task/0682-go-calendar
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 80k tokens
## 1. Objective
Port `GET /dashboard/calendar` (`App/app/routes/dashboard_calendar.py` lines 15-133) to a new Go package `go/internal/calendar` and register it in `go/cmd/ubyhost-web/main.go`. Byte-identical JSON to Python. Production unchanged: Go container off.
## 2. Context
Python source of truth (grep `^def `, read one function at a time): `dashboard_calendar.py` (`parse_dates`, `parse_range`, `_visual_hour`, `_hour_is_valid`, `events`, `calendar_data`); `App/app/reporting.py` `reservation_progress` (395-468), `guest_issues`/`guest_is_complete` (319-335), `guest_identity_verified` (268), `guest_filed_by_hand` (2156), `expected_guest_count` (350), `deadline_cell` (751-793) with `_filing_stamp`/`_latest_filing`/`filed_at` (722-750), `reservation_deadline_anchor` (2306), `FINISHED_STATUSES`; `App/app/deadlines.py` `urgency`, `hours_left`, `local_now`, `reporting_deadline`; `App/app/demo.py` `is_demo_stay`; `App/app/access.py` `owner_id`, `apartments`; `App/app/auth.py` `require_login`.
Go to reuse (do not duplicate): `go/internal/hostweb` (Login guard), `go/internal/session`, `go/internal/validation` (`GuestIsComplete`, `GuestIsReportable`, `ParseISODate`), `go/internal/ubyport/collect.go` (`LoadGuests` + `FieldDecrypter` for decrypted guest rows, `ReportingDeadline`, deadline anchor logic, Prague time helpers), `go/internal/palette/db.go` `apartmentRows` pattern for owner scoping (NULL-safe owner). If a helper you need is unexported in `ubyport`, export it with a one-line doc comment (smallest change) instead of copying it; say so in the report.
Rules: guard failure returns exactly what Python returns for a JSON route (check `require_login`; palette 0679 did the same, copy its behaviour). Invalid range/property -> 422 `{"error":"invalid_range"}`; property not in the owner's active list -> 404 `{"error":"not_found"}`; all responses `Cache-Control: no-store`. JSON: Python `JSONResponse` = compact, `ensure_ascii=False`; key order exactly as Python dict order; `guests`/`complete`/`expected` ints (`expected` may be null); `preview`/`timingFallback` bools. Never expose guest identity. The guest key loading (data key) must match how `ubyport` loads it; a stay whose guests will not decrypt: mirror `preload_guests` fallback (per-stay read, that stay's error fails the request like Python).
## 3. Files
Create: `go/internal/calendar/calendar.go` (split into `progress.go` if over ~400 lines), `calendar_test.go`. Edit: `go/cmd/ubyhost-web/main.go` (one route), at most small exports in `go/internal/ubyport`. Write `docs/tasks/0682-report.md`.
## 4. Steps
1. Package + route `GET /dashboard/calendar`.
2. Unit tests (no DB): parse_range edge cases (bad format, year 1899/2102, end<=start, 371 days, `property=0`, `property=abc`); visual hour (None, -1, 24, "7", 7); tone for every status x overdue combination; deadline_cell states countdown/filed_on_time/filed_late (late hours floor, min 1)/none.
3. DB tests (skip without `UBYHOST_TEST_DATABASE_URL`, then must run with it, 0 skipped): signed out; another owner's stay absent; archived stay/apartment/inactive apartment absent; cancelled stay absent; stay ending exactly on `from` included (`date_to >= from`), starting on `to` excluded; property filter; foreign guest complete+verified unsent -> ready; demo source -> preview true and tone not ready; exact byte output for one small fixture (hardcode expected JSON).
4. Commit: `0682: Go dashboard calendar JSON`.
## 5. Do not touch
`App/` (read only), templates, JS, CSS, CI, compose, Caddy, `go.mod`/`go.sum`, other Go packages except `main.go` and minimal `ubyport` exports.
## 6. Commands
- Own worktree: `git worktree add -b task/0682-go-calendar /tmp/wt0682 origin/main`; work only there.
- Local Postgres (once): `pg_ctlcluster 16 main start; su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'ubyhost'\""`. Schema: see how other Go DB tests set up tables (grep `UBYHOST_TEST_DATABASE_URL` in `go/internal/palette`).
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go build ./... && UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres go test ./internal/calendar/ ./internal/ubyport/ ./cmd/... -count=1 2>&1 | tail -30`.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
calendar tests pass with the DB URL set, 0 skipped; ubyport tests still pass; vet/gofmt/build clean.
## 8. Stop and ask
Stop if the Python lines no longer match, or a schema change or new dependency seems needed.
## 9. Report
`docs/tasks/0682-report.md`: command tails, `git diff --stat origin/main`, anything decided beyond section 2, known differences from Python.
