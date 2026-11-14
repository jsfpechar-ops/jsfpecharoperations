# 1426 report: Go invoice pages, ARES register lookup (executor run, one big PR mode)

Status: review. No push, no PR, no branch created. Commits on the current branch: `1426 step 1`, `1426 step 3`.

## Files changed (§3 only)

- `go/internal/web/invoices/ares.go` (new, sha256 13b7a971... matches §2)
- `go/internal/web/invoices/ares_test.go` (new, sha256 e2e4c5f3... matches §2)
- `docs/tasks/1426-report.md`, and the brief Status line (`review`)

Step 0 anchors matched. Dependency check printed `1` and `go/internal/web/invoices/pages_new.go`.

## Commands (last lines)

- `gofmt -l internal/web/invoices cmd/ubyhost-web`: no output.
- `go build ./...`: no output.
- `go vet ./internal/web/invoices/... ./cmd/...`: no output.
- `go test -count=1 -v ./internal/web/invoices/... ./cmd/ubyhost-web/...` without a database: `ok` for both packages, 42 PASS, 24 SKIP. All skips are existing DB-dependent invoice-page tests. No ARES test skipped.
- Same command with a disposable PostgreSQL 16 on port 5618 (data in `/var/tmp/pg1426`, run as user `nobody`): `ok` for both packages, 123 PASS, **0 SKIP**. Server stopped and data directory deleted afterwards.
- `go test -count=1 -v -run 'TestICOOK|TestMapAres|TestAres' ./internal/web/invoices/ | grep -c '^--- PASS'`: 3.
- `grep -n 'http.Client\|ares.gov.cz' ares.go`: line 30 (the one URL, `ares.gov.cz/.../ekonomicke-subjekty/%s`), line 31 (one client, `aresTimeout`).
- `python3 scripts/context_lint.py`: `context lint: OK`. Warnings only, all about files named by other open briefs.

## §7 acceptance

- [x] Both sha256 values match §2.
- [x] gofmt, build and vet print nothing.
- [x] `go test` prints `ok` for both packages, with 0 skips when PostgreSQL is running.
- [x] The ARES filter gives 3 PASS.
- [x] One client, 4-second timeout, one URL.
- [x] Step commits list only §3 paths.
- [x] Nothing pushed, no branch created.

## Deviations

Brief §4 step 2 says no database is needed, but the package's existing tests skip without one. Per the task instructions, a disposable PostgreSQL was started on 5618 so that none is skipped. The §4 step 2 count with PostgreSQL is 0 skips.

## Questions

None.

## Owner steps left

None. Nothing is switched on; the pages stay dormant until brief 1427's owner steps.
