# 1592 report: Go customer admin, the six "System problems" counts

Status: review (one big PR mode, branch worktree-agent-a1099d50f6a1bbe03, no push, no PR)

## 1. Files changed

- `e18b32c` (1592 step 1): `go/internal/web/customers/ops.go` (+192), `go/internal/web/customers/ops_test.go` (+188). Both match the sha256 of the sidecars. No other path changed.

## 2. Commands

- `sha256sum -c` of the 2 sidecars: `ops.go: OK`, `ops_test.go: OK`.
- Step 2 (`gofmt -l`, `go build ./...`, `go vet ./internal/web/customers/... ./cmd/...`): no output.
- Step 4, `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55903/postgres go test ./internal/web/customers/... ./cmd/ubyhost-web/... -count=1`:
  ```
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/customers	9.613s
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.116s
  ```
- Named tests, `go test ./internal/web/customers/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestOpsCounts$|^TestOpsTimeHelpers$'`:
  ```
  === RUN   TestOpsCounts
  --- PASS: TestOpsCounts (0.48s)
  === RUN   TestOpsTimeHelpers
  --- PASS: TestOpsTimeHelpers (0.00s)
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/customers	0.498s
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.080s [no tests to run]
  ```
  The `[no tests to run]` line for `cmd/ubyhost-web` is expected: the two named tests live in the customers package.
- Full verbose run of both packages: exit 0, 55 `--- PASS`, **SKIP count: 0**.
- `python3 scripts/context_lint.py`: `context lint: OK`.

## 3. §7 acceptance

- [x] sha256sum of step 1: 2 of 2 OK.
- [x] Step 2 printed nothing.
- [x] Step 4: ok lines, both named tests PASS, 0 SKIP, 0 FAIL.
- [x] Step 1 commit lists only §3 paths.
- [x] No route added, no Caddy/compose/env/Python file changed, nothing pushed.
- [x] UI: not applicable.

## 4. Deviations

- PostgreSQL port: the brief's step 4 names port 55592 and `/var/tmp/pg1592`. The orchestrator instructed port 55903 and data dir `/var/tmp/pg-1592`; I used those. Server started and stopped; data dir removed.
- Step 0 and the other pre-flight checks matched the brief exactly.
- `App/.venv` symlink was not created: this brief has no i18n or Python step.
- Known differences F1 and F2 from the brief still apply and are not fixed here (request-time clock; `parseOpsTime` layouts).

## 5. Questions

None.

## 6. Owner steps left

None (no route in this brief).
