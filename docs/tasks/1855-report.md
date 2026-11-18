# 1855 report

Status: review

## Files

- `go/internal/web/stays/params.go`, `query.go`, `overdue.go`, `view.go`
- `go/internal/web/stays/query_test.go`, `view_test.go`
- `docs/tasks/1855-go-stays-list-query.md` status → review

## Commands

```
go vet ./internal/web/stays/...
ok  	.../go/internal/web/stays	0.006s
gofmt -l internal/web/stays (empty after format)
python3 scripts/context_lint.py → FAIL only missing report (fixed here)
```

DB test `TestListPaginationAndOrder`: skipped without `UBYHOST_TEST_DATABASE_URL` (1 skipped in CI env).

## §7

- [x] Package builds; chips, pager URLs, range rules tested
- [x] diff is stays + brief + report

## Deviations

None.

## Questions

None.

## Owner steps

None.