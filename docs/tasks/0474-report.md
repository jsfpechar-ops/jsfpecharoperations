# 0474 report (Go G1a)

Status: review
Executor: Haiku 5.5. Branch task/0474-go-g1a, not pushed.

## Done
- Step 5 per the 2026-11-01 decision: compressed cases load the Python token; Go Dumps round-trips through Go Loads, carries the Python timestamp, its signature is HMAC-SHA1 (django-concat key) over Go's signed string, and its decompressed JSON bytes equal Python's. Uncompressed cases stay byte-identical. Negative tests pass.
- Step 6: go/internal/schema/goose.go and goose_test.go. Pending reads unqualified `to_regclass('goose_db_version')` so the test schema works (Python uses `public.`).
- Step 7: go/cmd/ubyhost-web/main.go (healthz, metrics, goose check, SIGTERM shutdown, slog, URL redacted).
- Step 8: `go` job in .github/workflows/ci.yml, placed before `smoke`.
- Step 9: decisions.md line and architecture.md row.
- go.mod: `go mod tidy` alone chose pgx v5.12.0 and go 1.25.0. Pinned by hand to pgx v5.12.0, go 1.24, toolchain go1.25.14; tidy then kept x/text v0.24.0 (indirect).
- Fixture count: 19 (`fixtures written: 19`). Drift check: committed fixtures unchanged.

## Commands (tails)
- gofmt -l: empty. go vet: empty.
- go test ./... with UBYHOST_TEST_DATABASE_URL: `ok internal/schema 0.028s`, `ok internal/secure 0.009s`, cmd has no test files.
- go build ./cmd/ubyhost-web: ok.
- crypto_fixtures.py: `fixtures written: 19`. pytest test_crypto_fixtures.py: `2 passed in 0.22s`.
- Pending probe: DB had goose 1 pending, so apply ran: `PostgreSQL schema apply OK: database=ubyhost_test, version=33, tables=67, goose=1.` After that, extra file 99999_probe.sql: `goose files pending: [99999]`, rc=1.
- context_lint.py: FAIL (see Questions).

## Smoke (built binary, /tmp/wt0474-ubyhost-web)
- GET /healthz: `{"status":"ok","version":"go-dev","data_dir_writable":true,"database_ok":true}`
- GET /metrics: `# TYPE ubyhost_go_up gauge` / `ubyhost_go_up 1` / `ubyhost_go_http_requests_total{route="/healthz",code="200"} 1`
- GET /nope: 404. SIGTERM: shutdown rc=0, log `stopped`.

## Deviations
- The smoke ran the built binary instead of `go run`, so the kill reaches the server itself.
- Commit trailer is Co-Authored-By Opus 5.5, as the orchestrator asked.
- The CI `go` job is not run (no push). Owner: after push, confirm it is green.

## Questions
- context_lint FAILS: docs/context/decisions.md is about 2240 tokens, cap 2200, after my appended 0474 line. I did not measure the file before the edit. Choose: (a) the orchestrator compacts decisions.md (the brief does not cover this), then I rerun the lint; (b) raise the cap. I did not compact.

## Owner steps left
- Push the branch, check the `go` CI job is green, then merge via scripts/merge-pr-on-green.sh.

## Files
go/go.mod, go/go.sum, go/internal/secure/secure_test.go, go/internal/schema/goose.go, go/internal/schema/goose_test.go, go/cmd/ubyhost-web/main.go, .github/workflows/ci.yml, docs/context/decisions.md, docs/context/architecture.md, docs/tasks/0474-go-g1a-skeleton-and-crypto-conformance.md, docs/tasks/0474-report.md.

## Diff stat (origin/main)
 .github/workflows/ci.yml                           |  33 +
 App/scripts/crypto_fixtures.py                     | 135 +++
 App/tests/test_crypto_fixtures.py                  |  48 +
 docs/context/architecture.md                       |   1 +
 docs/context/decisions.md                          |   1 +
 .../0474-go-g1a-skeleton-and-crypto-conformance.md |  69 ++
 docs/tasks/0474-report.md                          |  45 +
 go/cmd/ubyhost-web/main.go                         | 193 ++++
 go/go.mod                                          |  16 +
 go/go.sum                                          |  28 +
 go/internal/schema/goose.go                        |  98 +++
 go/internal/schema/goose_test.go                   | 101 +++
 go/internal/secure/digest.go                       |  27 +
 go/internal/secure/fernet.go                       | 173 ++++
 go/internal/secure/secure_test.go                  | 289 ++++++
 go/internal/secure/signer.go                       | 135 +++
 go/internal/secure/testdata/fixtures.json          | 970 +++++++++++++++++++++
 17 files changed, 2362 insertions(+)

## Orchestrator resolution
- Lint stop: the decisions line was shortened (and the 0465b line trimmed by four words); `context lint: OK`. decisions.md sits at the cap: the next orchestrator compacts it before appending.
- Known gap for G4: Go's JSON encoder escapes U+2028/U+2029 and formats floats differently from Python; session payloads hold ints, bools and short ASCII strings only, so G1 is unaffected. G4 re-checks any payload it adds.
- pgx 5.7.6 failed dependency-review (GHSA-9jj7-4m8r-rfcm, GHSA-xgrm-4fwx-7qm8, critical); moved to pgx v5.12.0, which needs Go 1.25: toolchain go1.25.14.
