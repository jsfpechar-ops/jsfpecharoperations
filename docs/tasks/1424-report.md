# Report 1424: Go invoice pages: mark paid, cancel and the public download link

Status: review
Executor: Haiku 5.5 (one big PR mode, branch kept, no push, no PR)

## Files changed (§3 only)

- `go/internal/web/invoices/actions.go` (new, copied from sidecar, sha256 matches §2)
- `go/internal/web/invoices/public.go` (new, copied from sidecar, sha256 matches §2)
- `go/internal/web/invoices/actions_test.go` (new, copied from sidecar, sha256 matches §2)
- `docs/tasks/1424-report.md` (this file)
- `docs/tasks/1424-go-invoices-actions.md` (Status line set to review)

## Commands (last lines)

- Step 0 checks: `pages_detail.go` and `pdf_download.go` listed; `actions.go` "No such file"; `def invoice_mark_paid` 1; `def read_download_token(` 1; `func (s *TimedSerializer) Loads(` 1; sidecar count 3.
- Step 1 hashes: `bbf7fac0...a6a4 actions.go`, `6812121e...f4e8 public.go`, `c016e641...d79c actions_test.go`. All match §2.
- PostgreSQL: started on port 5612 (`/var/tmp/pg1424`), answered `1`, stopped and directory deleted.
- `gofmt -l internal/web/invoices cmd/ubyhost-web`: no output.
- `go build ./...`: no output.
- `go vet ./internal/web/invoices/... ./cmd/...`: no output.
- `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5612/postgres go test -count=1 ./internal/web/invoices/... ./cmd/ubyhost-web/...`:
  - `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/invoices 32.116s`
  - `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web 0.186s`
- Skip count (`go test -v ./internal/web/invoices/`, grep `--- SKIP`): **0**.
- Named PASS count (`-run 'TestMarkPaid|TestCancelAction|TestPublic'`): **4**.
- `python3 scripts/context_lint.py`: `context lint: OK` (WARN lines are other briefs' open files, not blocking).

## §7 acceptance

- [x] 3 sha256 values match §2
- [x] gofmt, build, vet print nothing
- [x] go test ok for both packages; 0 SKIP with PostgreSQL
- [x] named PASS count is 4
- [x] step commits (`1424 step 1`, `1424 step 3`) touch only §3 paths
- [x] nothing pushed, no branch created

## Deviations

- PostgreSQL port 5612 and data dir `/var/tmp/pg1424` per task message (brief text names 55432 and pg1420).
- Commands run one per call where the shell guard refused a compound `git` command.

## Questions

None.

## Owner steps left

None. Pages stay dormant until `UBYPORT`-independent switch in brief 1427 (`UBYHOST_GO_PATHS`).
