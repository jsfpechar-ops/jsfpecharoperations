# 1588 report

## Files changed

- `go/cmd/ubyhost-web/register_web_stayfees_all_test.go` (create)
- `docs/tasks/1588-report.md` (create)
- `docs/tasks/1588-go-stay-fee-all-routes-test.md` (Status → review)

## Commands

**Step 0** (preflight): branch `wt-1588`, stay-fee Go files present, test file absent, one sidecar `.txt`.

**Step 1** sha256:
```
go/cmd/ubyhost-web/register_web_stayfees_all_test.go: OK
```

**Step 2** (from `go/`):
```
--- PASS: TestStayFeesAllRoutesRegistered (0.00s)
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.056s
```
gofmt and `go vet ./cmd/...` produced no output.

## §7 Acceptance

- [x] `sha256sum -c` printed `: OK`.
- [x] gofmt and vet printed nothing; the test printed `--- PASS` and `ok` (no `SKIP`, no `FAIL`).
- [x] Commits touch only the test file, this report, and the brief.
- [x] No path added to `UBYHOST_GO_PATHS`; work on `wt-1588`, not `main`.

## Deviations

User assignment: branch `wt-1588` (not brief default), `git reset --hard origin/go-wave3`, push `wt-1588` only (no PR). Brief step 2 only; no PostgreSQL needed for this test.

## Questions

None.

## Owner steps

None (1589 owns rollout).