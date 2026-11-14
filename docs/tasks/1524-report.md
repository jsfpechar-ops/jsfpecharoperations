# 1524 report: Go port of Invoice details with the VAT register lookup

Status: review. Executor: Haiku 5.5. One big PR mode: commit `1524 step 2` (files) and `1524 step 3` (status and report) on the current branch (go-wave3 reset). No push, no PR.

## Files changed (`1524 step 2`)
- go/internal/web/properties/vatregister.go (+221)
- go/internal/web/properties/invoice_details.go (+288)
- go/internal/web/properties/invoice_details_test.go (+177)
- go/cmd/ubyhost-web/register_web_properties_invoice.go (+20)

Sidecar sha256: 4 of 4 OK. No existing file changed. No patches applied, no catalog regeneration, no venv needed.

## Commands (last lines of output)
- `gofmt -l .` empty; `go build ./...` ok; `go vet` clean.
- `go test -count=1 -v ./internal/web/properties/ ./cmd/ubyhost-web/`: `ok` for both packages, exit 0, 0 FAIL, 0 SKIP. TestParseVAT, TestInvoiceDetailsSave and TestInvoiceDetailsLookup all PASS.
- `python3 scripts/context_lint.py`: `context lint: OK`.

PostgreSQL: disposable server on port 5631, data in /var/tmp/pg1524 (stopped and removed afterwards).

## Section 7
- [x] Step 2: 4 OK; gofmt, vet, build clean; section 6 tests pass.
- [x] Commits touch only section 3 paths.

## Deviations, questions, owner steps
- None in the code. Brief Status line set to `review`.
- Owner: confirm the Go container reaches `adisrws.mfcr.cz` before the lookup is used on Go.
