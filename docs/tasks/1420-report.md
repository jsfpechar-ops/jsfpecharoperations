# 1420 report: Go invoice pages foundation

Status: review (one big PR mode: commits on the current branch, no push, no PR)

## Files (diff stat of commit `1420 step 1`, 8 files, 1512 insertions)

- go/internal/web/invoices/handlers.go, dec.go, i18n_keys.txt, i18n.json, dec_test.go, handlers_test.go, i18n_test.go
- go/cmd/ubyhost-web/register_web_invoices.go

All eight sha256 values match section 2.

## Commands (last 5 lines each)

- `gofmt -l internal/web/invoices cmd/ubyhost-web` (from go/): no output
- `go build ./...`: no output
- `go vet ./internal/web/invoices/... ./cmd/...`: no output
- `go test -count=1 ./internal/web/invoices/... ./cmd/ubyhost-web/...`:
  `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/invoices 0.011s`
  `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web 0.059s`
- `go test -v ./internal/web/invoices/... | grep -c -- '--- SKIP'`: 0
- `go test -v -run 'TestParseDecimal|TestVATParts|TestMoneyCZK|TestEveryKey|TestBadID'`: 5 PASS lines
- `go list ./internal/web/invoices/`: prints the package path
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings only, none for this brief's files)

## Section 7

- [x] 8 sha256 values match
- [x] gofmt, build and vet print nothing
- [x] go test ok for both packages, no SKIP
- [x] 5 named PASS lines
- [x] go list prints the package path
- [x] Step commits: `1420 step 1` (b56cdfc0e) only; section 3 paths only
- [x] Nothing pushed, no branch created

## Deviations

- Done: steps 0 to 3. Left: none.
- The step 0 dependency check's `head -6` cut off the `go/internal/pdf` listing. I listed `go/internal/pdf` on its own: it exists and has files.
- Tests were run without `UBYHOST_TEST_DATABASE_URL`, as section 4 says this brief needs no database. The PostgreSQL server on port 5601 was not started.
- Step 3 commit: the report and the brief Status line are committed as `1420 step 3`.

## Questions

None.

## Owner steps left

None. Nothing is switched on; no route is registered.
