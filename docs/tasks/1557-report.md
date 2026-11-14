# 1557 report: Go subscription billing, part 3 (POST /predplatne, POST /predplatne/zmena, ARES lookup)

Status: review. One big PR mode: commits on branch go-wave3 (no push, no PR).

## 1. Files changed (commits "1557 step 1" and "1557 step 6")

- go/internal/web/billing/ares.go (create, sidecar)
- go/internal/web/billing/host_actions.go (create, sidecar)
- go/internal/web/billing/host_actions_test.go (create, sidecar)
- go/internal/web/billing/table.go (replace, sidecar)
- go/internal/web/billing/routes_inventory_test.go (replace, sidecar)
- go/cmd/ubyhost-web/register_web_billing_test.go (replace, sidecar)
- docs/tasks/1557-report.md (create), docs/tasks/1557-go-billing-host-order-change.md (Status line only)

## 2. Commands (last lines)

- sha256sum -c (step 1): all 6 files `: OK`.
- gofmt / go build / go vet (step 2): no output.
- go test ./internal/web/billing/... ./cmd/ubyhost-web/... ./internal/mail/ -count=1 (PostgreSQL 16 on 127.0.0.1:5624):
  `ok ...internal/web/billing 20.381s`, `ok ...cmd/ubyhost-web 0.189s`, `ok ...internal/mail 14.401s`
- Named tests with -v: 9 of 9 `--- PASS` (TestBillingRoutesRegistered, TestMapAresPayload, TestAresClient, TestOrderValidation, TestOrderInTrial, TestOrderWhenPausedStartsNow, TestOrderAresFill, TestPlanChange, TestRoutesNeedNoPool).
- SKIP count: 0 (grep for `--- SKIP` and for "skip" both 0).
- Server stopped and /var/tmp/pg1557 deleted.
- python3 scripts/context_lint.py: `context lint: OK`.

## 3. Section 7 ticked

- [x] sha256sum OK for all 6 files
- [x] Step 2 printed nothing
- [x] Step 4: three ok lines, 9 named tests PASS, no SKIP/FAIL
- [x] Commits listed; only section 3 paths touched
- [x] No UBYHOST_GO_PATHS, Caddy, compose, env or Python change; nothing pushed
- [ ] UI: dormant page, no 390 px screenshot possible in this PR. The UX gate runs on staging before the owner adds the path (per the brief).

## 4. Deviations

- PostgreSQL port 5624 (from the task message) instead of the brief's 55503; data dir /var/tmp/pg1557 as the brief says.
- Step 0 `ls` of ares.go was masked by `tail -1`; the step 1 copy created it, so no effect.

## 5. Questions

None.

## 6. Owner steps left

Do not add /predplatne to UBYHOST_GO_PATHS until the UX gate of rule 10 has run on staging. Confirm the container may reach ares.gov.cz.
