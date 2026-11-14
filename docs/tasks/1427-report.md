# 1427 report (executor run, one big PR mode)

Status: review

## Files changed (step 1, commit "1427 step 1")
- go/internal/web/invoices/post_issue.go (create, 234 lines)
- go/internal/web/invoices/post_test.go (create)
- go/internal/web/invoices/fill_register_test.go (create)
- go/internal/web/invoices/routes_test.go (create)
- go/cmd/ubyhost-web/register_web_invoices_test.go (create)
- docs/tasks/1427-go-invoices-issue-preview.md (Status: review)
- docs/tasks/1427-report.md (this file)

## Commands (last lines)
- Step 0 anchors: ares.go, formctx.go, public.go present; post_issue.go absent; invoice_issue and invoice_preview anchors 1 each; 5 sidecars.
- sha256sum (5 files): all 5 match section 2.
- gofmt -l: no output. go build ./...: no output. go vet: no output.
- go test -count=1 ./internal/web/invoices/... ./cmd/ubyhost-web/...: `ok ...internal/web/invoices 31.529s`, `ok ...cmd/ubyhost-web 0.326s`.
- go test -v (both packages): 0 SKIP, 0 FAIL, 134 PASS.
- Section 7 regex count: 12.
- TestInvoiceRoutesRegistered: ok.
- go test ./cmd/... ./internal/web/...: every package ok.
- python3 scripts/context_lint.py: `context lint: OK` (warnings only about other briefs' files).

## Section 7
- [x] 5 sha256 match
- [x] gofmt, build, vet clean
- [x] invoices and ubyhost-web ok; 0 SKIP with PostgreSQL 16 on port 5621
- [x] 12 PASS for the regex
- [x] TestInvoiceRoutesRegistered ok
- [x] step commit shows only section 3 paths
- [x] nothing pushed, no branch created

## Deviations
Done: steps 0 to 3 (step 4 is this report). Left: none. PostgreSQL 5621 was started at /var/tmp/pg5621, stopped and deleted.

## Questions
None.

## Owner steps left
None (the brief's owner steps were not performed, as instructed).
