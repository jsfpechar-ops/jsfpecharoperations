# 1855: Port GET /reservations to Go, part 1: query and view model

<<<<<<< HEAD
Status: todo
Depends on: none | Base commit: tip of main | Branch: task/1855-go-stays-list-query
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (checkpoint at 60k; hand over per [workflow](../context/workflow.md#when-haiku-reaches-the-cap))
Tier: B (read-only page, no data change)
Pairs with 1856 (template, route, parity). 1855 goes first, then 1856, then 1857, then 1858.
=======
Status: review
Depends on: none | Base commit: tip of main | Branch: task/1855-go-stays-list-query
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (checkpoint at 60k; hand over per [workflow](../context/workflow.md#when-haiku-reaches-the-cap))
Tier: B (read-only page, no data change)
Pairs with 1843 (template, route, parity). 1855 goes first, then 1843, then 1840, then 1841.
>>>>>>> origin/cursor/1855-go-stays-list-2385

> **One PR mode.** Commit each step as `1855 step k`. Never push, merge or deploy. Every command ends in `| tail -30`. Anchors are quoted from the tip: if one is not found verbatim, STOP and report.

## Open questions

None. Owner decision 2026-11-17 ("No python only go"): the Stays fixes ship in Go only; a port comes first ([go-first](../context/go-first.md)).

## 1. Objective

<<<<<<< HEAD
Create the Go package `go/internal/web/stays` with the read-only data side of `GET /reservations`: parse the query, run the same SQL as Python, and build a view model (rows, chips, filter state, pager URLs). No template, no route registration (1856). Result must equal Python for the same data.
=======
Create the Go package `go/internal/web/stays` with the read-only data side of `GET /reservations`: parse the query, run the same SQL as Python, and build a view model (rows, chips, filter state, pager URLs). No template, no route registration (1843). Result must equal Python for the same data.
>>>>>>> origin/cursor/1855-go-stays-list-2385

## 2. Context

Rules 1 (filing correctness: this page shows send state, read it exactly as Python does), 2, 5 (Go SQL stays Postgres-portable), 11. Python reference is READ-ONLY: `App/app/routes/admin.py` lines ~3683-3880 (`RESERVATION_PAGE_SIZE = 5`, `RESERVATION_RANGES`, `reservations_list`, `page_url`). Read it with `sed -n 3683,3740p`, then 3740-3830, then 3830-3880 (150 lines max each). Existing Go package to copy conventions from: `go/internal/web/customers/` (`query.go`, `query_test.go`, `handlers.go`). Prague civil date: find the Go equivalent with `grep -rn 'Prague\|LoadLocation' go/internal --include=*.go -l | head`.

Query keys (from Python): `status` (active|cancelled|ignored|all; else active), `apartment` (int), `from`, `to` (dates), `range` (upcoming|current|past|all|archive|custom; else custom if from/to or archive_scope, else upcoming), `archive_scope=1`, `report=failed`, `page`. Chips are Upcoming, Current, Past, Report failed, Archived; the reset link goes to `range=all`. Page size 5.

## 3. Files

Python is NOT changed (this brief only reads it; go-first exception 1, port plumbing, does not even apply because no Python file is edited).
- New `go/internal/web/stays/query.go`: `type Params`, `ParseParams(url.Values, today time.Time) Params`, `type Row`, `func List(ctx, db, accountID, Params) (View, error)`.
- New `go/internal/web/stays/view.go`: `type View` (Rows, Total, Page, PageCount, Chips []Chip{Key,Label,Href,Current}, FilterSummary, ResetHref, PrevURL, NextURL), `pageURL(n)` that keeps every filter key except `page` (same rule as Python `query_params = [... if key != "page"]`).
- New `go/internal/web/stays/query_test.go`, `view_test.go` (table tests; DB tests skip without `UBYHOST_TEST_DATABASE_URL`, like the siblings).
- Read-only: the Python files above, `docs/context/test-map.md`.

## 4. Steps

0. Anchors. `grep -nF 'RESERVATION_PAGE_SIZE = 5' App/app/routes/admin.py | tail -30`; `ls go/internal/web | tail -30` (expect no `stays`). If `stays` exists, STOP.
1. Read the Python in the three ranges above. Write `ParseParams` and the range-to-dates rules exactly (upcoming: from=today; past: to=yesterday; current: both today; all/archive: none; custom keeps from/to). Table test per rule with a fixed `today`.
2. Port the SELECT, the overdue and urgency columns and the `ORDER BY` verbatim (copy the SQL text; bind with the Go db helper used in `customers/query.go`). Test with the DB fixture style of `customers/query_test.go`: seed 6 stays, assert page 1 has 5 rows and page 2 has 1, order equals Python's expected order (compute it from the Python test `App/tests/test_0523_stays_list.py`, read-only).
3. Build chips and `pageURL`. Tests: each chip href keeps `apartment` and `status`, drops `page`, `from`, `to`; `report=failed` chip has no `range`; Archived chip is `range=archive`; reset is `range=all`; `NextURL` on page 1 has every filter and `page=2`; `PrevURL` empty on page 1.
4. Run: `cd go && go vet ./internal/web/stays/... 2>&1 | tail -30` then `go test ./internal/web/stays/... 2>&1 | tail -30`.

## 5. Do not touch

<<<<<<< HEAD
Any file under `App/`; `go/cmd/`; Caddy; `UBYHOST_GO_PATHS`; templates (1856); other Go packages.
=======
Any file under `App/`; `go/cmd/`; Caddy; `UBYHOST_GO_PATHS`; templates (1843); other Go packages.
>>>>>>> origin/cursor/1855-go-stays-list-2385

## 6. Commands

From `go/`: `go vet ./internal/web/stays/... 2>&1 | tail -30`; `go test ./internal/web/stays/... 2>&1 | tail -30`; `gofmt -l internal/web/stays | tail -30` (expect empty). Root: `python3 scripts/context_lint.py 2>&1 | tail -30`. DB tests skipping without the env var is allowed here; say how many skipped.

## 7. Acceptance

- Package builds and tests pass; chips, pager URLs and range rules match the Python rules listed in step 1 and 3.
- `git diff --stat` shows only `go/internal/web/stays/*` (and this brief's status line).
- Owner steps: none.

## 8. Stop and ask

Stop at 30 tool calls or 60k tokens, if the Python SQL needs a table or column that has no Go helper, or if a step needs a file not named in section 3.

## 9. Report

What changed; last 30 lines of each test output; skipped-test count; any Python behaviour you could not match.
