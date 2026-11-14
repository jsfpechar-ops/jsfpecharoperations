# 1555 report (executor: Haiku 5.5, one big PR mode)

Branch: local `go-wave3` (worktree reset to it first). Nothing pushed, no PR.

## Files (commit `1555 step 1`, 9 files, all from §3, copied from sidecars)
- go/internal/web/billing/routes.go, routes_test.go, testenv_test.go, i18n_keys.txt, i18n.json, table.go, routes_inventory_test.go
- go/cmd/ubyhost-web/register_web_billing.go, register_web_billing_test.go
- docs/tasks/1555-go-billing-shared-pdfs.md (Status: review), docs/tasks/1555-report.md

## Commands
- Step 0: reset OK; brief, sidecar dir and dependency check (`ls go/internal/web/billing`) OK; all 5 checks as stated.
- Step 1: `sha256sum -c` printed `: OK` for all 9 files.
- Step 2: gofmt, `go build ./...`, `go vet` printed nothing.
- Step 3: PostgreSQL 16 started on port 5615 (task message port; brief text said 55501), data in /var/tmp/pg1555. Server started.
- Step 4: `go test ./internal/web/billing/... ./cmd/ubyhost-web/... ./internal/mail/ -count=1` ->
  `ok .../internal/web/billing 4.416s`, `ok .../cmd/ubyhost-web 0.108s`, `ok .../internal/mail 6.558s`.
  Named tests -v: PASS for TestRoutesNeedNoPool, TestHostInvoicePDF, TestAdminInvoicePDF, TestCancelResume, TestPausedHostStillPostsToPlanPage, TestCSRFRequired, TestBillingRoutesRegistered.
- Skips in the billing, registration and mail packages with the test URL set: **0**.
- Step 5: server stopped, /var/tmp/pg1555 removed.
- Lint: `context_lint.py` OK.

## Deviations
- Port 5615 instead of 55501 (per task message).
- Step 6 commit is made together with this report.

## Questions
None.

## Owner steps
None (nothing switched on; no path added to UBYHOST_GO_PATHS).
