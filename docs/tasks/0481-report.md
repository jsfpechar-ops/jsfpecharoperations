# 0481 report: Go UbyPort transport, Submit and submission claim

Status: review

## Files changed
- `go/go.mod`, `go/go.sum`: `github.com/Azure/go-ntlmssp v0.1.1` (step 1)
- `go/internal/ubyport/client.go`: `Client`, `NewClient`, `Post`, `Submit`, `Error` with kinds `ErrTransport`, `ErrOutcomeUnknown`, `ErrAuth` (step 2)
- `go/internal/ubyport/client_test.go`: httptest coverage, including a hand-built NTLM type-2 challenge (step 3)
- `go/internal/ubyport/claim.go`: `ClaimSendable`, `ReleaseSendableClaim` (step 4)
- `go/internal/ubyport/claim_test.go`: DB tests, skipped without `UBYHOST_TEST_DATABASE_URL` (step 5)

## Commands
- `gofmt -l .` (empty), `go vet ./...` (clean), `go test ./internal/ubyport/ -count=1 -v`: PASS. Tail: `ok github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport 0.326s`.
- The four claim tests SKIP locally (no `UBYHOST_TEST_DATABASE_URL`). CI must run them.
- `python3 scripts/context_lint.py`: `context lint: OK`.

## Deviations
- `go mod tidy` rewrote the `require` lines as a block, so `go.mod` is +3/-1 lines, not one added line. Same module set.
- Step 1 commit contains only go.mod/go.sum; it builds only together with step 2 (tidy drops an unused requirement).
- `UBYHOST_SOAP_WSA_HEADER` is read with `LookupEnv`, so a set-but-empty value counts as on, as in Python.
- Error kinds: `errors.Is(err, ErrTransport)` is true for auth and outcome-unknown errors, matching the Python class hierarchy.
- `Client.Post` builds an unknown-outcome error for a malformed endpoint, as Python does for `MissingSchema`.

## Not done
- `docs/context/decisions.md` and `docs/context/status.md` were not edited (no owner decision text was given in the brief beyond the reference).
- Claim tests not run against PostgreSQL.
