# 1221 report: Go billing invoicer

Status: review

## Files changed
- go/internal/billingjob/{doc,invoicer,items,send,unit_test,invoicer_test}.go (new)
- go/internal/billingjob/testdata/invoicer.golden.json (new, byte-identical to script output)
- go/internal/mail/billing_invoice.go (new)
- App/scripts/billing_invoice_golden.py (new)
- docs/tasks/1221-report.md (new)

## Commits
- f54076f 1221 step 1 (Go code)
- 7eb955b 1221 step 3 (golden script)

## Checks
- Step 0 sha256 check: all 9 attachments OK.
- gofmt, vet, go build ./...: silent.
- go test ./internal/billingjob ./internal/mail -count=1: `ok` (both).
- Postgres 16 (127.0.0.1:5441, started for this task): `TestInvoicerMatchesPython` PASS; `--- PASS` count 3.
- Golden script rerun: wrote invoicer.golden.json, no git diff, prefix 362662715998.
- go.mod, go.sum unchanged.
- python3 scripts/context_lint.py: "context lint: OK" (warnings only, not from this change).

## 7 acceptance
- [x] TestInvoicerMatchesPython passes against Postgres
- [x] build and vet clean, gofmt silent, go.mod/go.sum unchanged
- [x] has_pdf check: covered by the test (hash matches bytes, starts %PDF-)
- [x] only §3 files in the commits
- [x] golden script reproduces the JSON byte for byte

## Deviations
- No push and no PR (brief §0 and the owner's instruction: do not push).
- Postgres left running on port 5441 (data dir /var/tmp/pg1221).
- Done: steps 0 to 4 (step 4 = this report).

## Owner steps left
- Push the branch, then open the PR and merge when CI is green.
