# 0673 report: Go Connect start/return routes

Status: review

## Files changed
- `go/internal/payments/connect.go` (new, 450 lines): `Onboarder`, `ErrStripeOff`, `ErrNoEntity`, `ErrNoAccount`, `ConnectStartHandler` (GET and POST), `ConnectReturnHandler` (GET). Guards in Python order: CSRF (POST), login with expired-impersonation and acceptance checks, paused billing (POST), off gives 404, consent, then the Onboarder call.
- `go/internal/payments/connect_test.go` (new, 311 lines): fake Onboarder; 12 database subtests; a Python-text check for the three `impersonation.expired` strings.
- `docs/tasks/0673-report.md` (this file).
- Nothing in `App/`, `main.go`, `go.mod`, CI, compose, Caddy, templates, JS or CSS.

## Command results
- `gofmt -l .` clean after `gofmt -w` on the two new files.
- `go vet ./...` clean.
- `UBYHOST_TEST_DATABASE_URL=... go test ./internal/payments/ ./internal/session/ -count=1 -v`: all PASS, `ok` for both packages, no SKIP lines.
- `python3 scripts/context_lint.py`: `context lint: OK`.

## Section 7 acceptance
- [x] All payments and session tests pass with the database URL set, 0 skipped.
- [x] Diff touches only the section 3 files (plus this report).

## Deviations
- Commit message is the one given in the chat (`0673: Go Connect start/return routes behind an Onboarder`), with the Opus co-author and session trailers, not the `NNNN step k` format from the executor guide.
- Not ported, as the brief says: staging no-login, the no-accounts dev shortcut, and `request.state.lang`. Written in the file comment.
- Multipart CSRF form field is not read (only urlencoded). Noted in the file comment.
- Brief Status line left as `todo`. No PR opened and nothing pushed, per the chat instructions.

## Questions
- None.

## Owner steps left
- Brief 0674 implements the Onboarder and registers the routes in `main.go`.
- Push the branch and open the PR when you want it reviewed.
