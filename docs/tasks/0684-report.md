# 0684 report: Go payment QR PNG
Status: review
Branch: task/0684-go-payment-qr | Base: origin/main 2ba2039

## Files changed
- `go/internal/payments/qrpng.go` (new): `QRPNGHandler` for `GET /payments/qr/{file}`, SPAYD, normalise_account, ascii_upper, PNG.
- `go/internal/payments/qrpng_test.go` (new): unit tests (no DB) and DB tests (skip without `UBYHOST_TEST_DATABASE_URL`).
- `go/cmd/ubyhost-web/main.go`: one route line.
- `go/go.mod`, `go/go.sum`: go-qrcode v0.0.0-20200617195104-da1b6568686e added.
- `docs/tasks/0684-go-payment-qr-png.md`: Status set to review.

## Commands (last lines)
- `gofmt -l .`, `go vet ./...`, `go build ./...`: clean, no output.
- `go test ./internal/payments/ ./cmd/... -count=1 2>&1 | tail -20`: `ok ... internal/payments`, `ok ... cmd/ubyhost-web`.
- `python3 scripts/context_lint.py | tail -1`: `context lint: OK`.
- `go test -v` skips: 15 DB tests in payments package (TestQRPNGDatabase among them) skip because no `UBYHOST_TEST_DATABASE_URL`. They compile; CI runs them.

## Steps
1. go get go-qrcode at the pinned version: done.
2. Port: done.
3. Unit tests (SPAYD IBAN and account strings from Python, ascii_upper cases with limit 60, PNG 270x270 and signature): done.
4. DB tests written (signed out 303, other owner 404, rail card 404, no bank account 404, good row 200 image/png, missing row and HTML path 404): not run locally.
5. Commit: done.

## Deviations
- Only one `legal_entity` case tested in DB: "no bank account" (iban and bank_account NULL). The "no legal_entity row" branch is in code (ErrNoRows gives 404) but has no DB test.
- go.mod: go-qrcode is in the direct require block. `golang.org/x/text` moved from indirect to direct (it is now imported by qrpng.go); no new module added. `go mod tidy` could not run offline.

## Known differences
- PNG bits differ from Python (accepted by brief). For the test payload both are version 5, 270x270. The test checks size and PNG signature only, not the decoded payload.
- ascii_upper: NFKD, then drop characters with non-zero canonical combining class, then upper (ß to SS special-cased), then QR filter. Matches the Python test strings.
- Missing variable symbol renders as "None" in X-VS, as Python's f-string does.
- Go regex uses ASCII digits; Python `\d` also matches Unicode digits. Stored bank_account values are normalised ASCII, so this is not reachable in practice.
- Huge ids beyond int64 return 404 (Python would hit a DB error).

## Owner steps left
- Merge via `scripts/merge-pr-on-green.sh` after CI runs the DB tests. Go container is off in production, so no deploy action.
