# 1558 report: go billing admin bank payments (executor run)

Mode: one big PR, local branch `go-wave3` (no push, no PR). Base reset: `git reset --hard go-wave3` (head 3b15c2bf5, brief 1557 merged).

## Files changed (step 1 commit c5671cf8c, sidecars copied, sha256 verified)
- go/internal/web/billing/payer.go (new)
- go/internal/web/billing/admin_actions.go (new)
- go/internal/web/billing/admin_actions_test.go (new)
- go/internal/mail/billing_paid.go (new)
- go/internal/mail/billing_paid_test.go (new)
- go/internal/web/billing/table.go (replaced)
- go/internal/web/billing/routes_inventory_test.go (replaced)
- go/cmd/ubyhost-web/register_web_billing_test.go (replaced)
- docs/tasks/1558-files/** (kept, committed in step 1)

## Commands
- Step 0 checks: all as stated (1557 steps present, 1555 files present, payer.go absent before, anchors count 1 each, 8 sidecars).
- Step 1 sha256sum -c: all 8 `: OK`.
- Step 2 gofmt / go build / go vet: no output.
- Step 3: PostgreSQL 16 started on port 5627, data in /var/tmp/pg1558: `server started`.
- Step 4: `ok` for go/internal/web/billing (19.5s), go/cmd/ubyhost-web (0.1s), go/internal/mail (12.3s).
- Step 4 -v named run: `--- PASS` for TestPyISODate, TestStatementUpload, TestStatementUploadRefusals, TestMarkPaid, TestSettle, TestRoutesNeedNoPool, TestBillingRoutesRegistered, TestBuildBillingPaid.
- SKIP count: 0 (full -v run of the three packages on PostgreSQL).
- Step 5: `server stopped`, directory deleted.
- context_lint: OK.

## Section 7
- [x] sha256sum OK for all 8
- [x] step 2 silent
- [x] three ok lines, 8 named tests PASS, 0 SKIP, 0 FAIL
- [x] only section 3 paths in the step 1 commit
- [x] no UBYHOST_GO_PATHS, Caddy, compose, env or App/ change; nothing pushed
- UI: not applicable (no template)

## Deviations
- PostgreSQL port 5627 (per task message) instead of the brief's 55504.

## Questions
None.

## Owner steps left
None here (routes dormant).
