# 1422 report: Go invoice store

Status: review

## Files changed (§3)

- `go/internal/web/invoices/store.go` (create, sidecar copy, sha256 1f7a24c2...bda2 matches)
- `go/internal/web/invoices/testenv_test.go` (create, sha256 3ced8dc7...acd04a matches)
- `go/internal/web/invoices/store_test.go` (create, sha256 71dfbca6...79cc matches)
- `docs/tasks/1422-go-invoices-store.md` (Status line only: todo to review)

Commits: `1422 step 1` (219b32820). Step 3 report commit follows. No push, no branch, no PR.

## Commands (last lines)

- Step 0 anchors: `dec.go`, `draft.go` listed; `store.go` absent; `_write_issued(` 1, `allocate_number(` 1, `func Render(in Invoice` 1; 3 sidecars.
- Step 1 sha256: all three match §2.
- PostgreSQL 16 started on port 5605, data under `/var/tmp/pg1422` (stopped and removed afterwards).
- `gofmt -l internal/web/invoices cmd/ubyhost-web`: no output.
- `go build ./...`: no output.
- `go vet ./internal/web/invoices/... ./cmd/...`: no output.
- `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5605/postgres?sslmode=disable go test -count=1 -v ./internal/web/invoices/... ./cmd/ubyhost-web/...`: `ok` for `internal/web/invoices` (7.6 s) and `cmd/ubyhost-web`. Zero SKIP lines.
- §7 `-run 'TestIssue|TestNumbering|TestStayLimit|TestCancel|TestDownload|TestHelpers'`: 8 `--- PASS`.
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings only, none for §3 files).

## §7 acceptance

- [x] sha256 values match
- [x] gofmt, build, vet clean
- [x] `ok` for both packages, no SKIP with PostgreSQL
- [x] 8 PASS for the -run pattern
- [x] step commits present, §3 paths only
- [x] nothing pushed, no branch created

## Deviations

- Data directory was `/var/tmp/pg1422` (common instructions) rather than the brief's `pg1420`; port 5605 as the task message said.
- Commit for step 3 is the report commit; the brief's step 3 has no file changes beyond step 1.

## Questions

None.

## Owner steps left

None.
