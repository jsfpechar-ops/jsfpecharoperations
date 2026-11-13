# 1200 report

Status: review

## 1. Files changed (`git diff --stat 29f86658 -- go/`)

```
go/cmd/ubyhost-web/main.go            | 140 ++--------
go/cmd/ubyhost-web/main_test.go       |  23 ++
go/cmd/ubyhost-web/register_filing.go |  47 ++++
go/cmd/ubyhost-web/register_jobs.go   |  78 ++++++
go/cmd/ubyhost-web/register_schema.go |  39 +++
go/cmd/ubyhost-web/register_web.go    |  39 +++
go/internal/jobs/queue.go             |  21 +-
go/internal/jobs/queue_test.go        |  13 +
```

Plus this brief and report under docs/tasks/.

## 2. Commands

- `gofmt -l ./cmd ./internal/jobs`: no output.
- `go vet ./...`: no output.
- `go test ./cmd/ubyhost-web/ ./internal/jobs/ -count=1`: both `ok`.
- Route set vs base 29f86658: same 20 `mux.Handle` patterns. Only the concatenation order of the grep differs, and ServeMux does not depend on registration order.
- `python3 scripts/context_lint.py`: OK.

## 3. Acceptance

- [x] Only §3 files changed.
- [x] Same route patterns.
- [x] jobNames covers all 15 kinds and matches host_i18n.py English.
- [x] Tests pass without a DB.

## 4. Deviations

None. The Opus diff review found no issues.

## 5. Questions

None.

## 6. Owner steps left

1. Merge when CI is green.
