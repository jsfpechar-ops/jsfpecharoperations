# 1860 report: stay detail data and Build

Branch: `task/1860-1864-stay-page` | Status: **review**

## Files

`go/internal/web/stays/detail_export.go`, `detail_export_test.go`; `go/internal/web/invoices/stay_export.go`, `stay_export_test.go`; `go/internal/doorcodes/view_stay.go`, `view_stay_test.go`; `go/internal/web/staydetail/{types,load,panels,panels_test,view,view_test}.go`; briefs refreshed (step 0).

## Commands (last 5 lines)

```
ok  	.../internal/web/staydetail	0.017s
ok  	.../internal/web/stays	(cached)
ok  	.../internal/web/invoices	(cached)
ok  	.../internal/doorcodes	0.004s
context lint: OK
```

DB tests: 3 skipped (no `UBYHOST_TEST_DATABASE_URL`). Sidecar unit tests: 0 skipped.

## §7

- [x] sha256sum 9 OK; vet/test/gofmt clean; stays/invoices/doorcodes tests pass
- [x] `TestStayDetailEqualsListHelpers`, `TestSendHint`, `TestActiveInvoiceForStayWrapsUnexported`, `TestIsDemoStay`, `TestHandFilingView` pass without DB
- [ ] With test DB: `TestViewForStay`, owner scope, submissions union, claim idempotent (not run here)
- [x] Diff limited to §3 + brief refresh + report

## Helpers (step 1)

`stays.StayProgress`, `validation.GuestIssues`/`GuestIsComplete`, `invoices.ActiveInvoiceForStay`, `doorcodes.(*Service).ViewForStay`, `billingjob.MailEnabled`/`PublicBaseURL`, `ai.HavelSafeLocalPath`, `palette.LinkKey`, `deadlines.ReportingDeadline`, `isDemoStay` (local).

## Deviations

None.

## Questions

None.