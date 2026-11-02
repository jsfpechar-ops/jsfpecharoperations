# 0677 report: Go routes for payment requests

## Files
- New: go/internal/payments/requests.go, requests_test.go, i18n_keys.txt, i18n.json
- Edited: go/cmd/ubyhost-web/main.go (two POST routes), go/internal/ubyport/notify.go and cancelled_notify.go (OutboxMail change)
- Brief status set to review

## Commands (tails)
- gofmt -l, go vet ./..., go build ./...: clean
- UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/t0677 go test ./internal/payments/ ./internal/ubyport/ ./internal/hostweb/ ./cmd/... -count=1: ok payments, ok ubyport, ok hostweb, cmd no test files
- payments: 0 skipped (--- SKIP count 0)
- App: go_host_i18n.py --check: no output (clean); pytest tests/test_go_host_i18n.py: 2 passed
- context_lint.py: context lint OK (warning only: 36 commits touched App since status.md, orchestrator to update)

## Acceptance (section 7)
Ticked: all listed Go tests pass with the DB URL set, 0 skipped in payments; vet, gofmt, build clean; i18n check passes.

## Deviations beyond the brief
- ubyport: added exported wrappers PyString and NormaliseEmail, and a payloadJSON method; OutboxMail gets Payload string, ApartmentID becomes *int64 (callers pass &id).
- Route tests use a fake LinkSender for the card rail. SendPaymentLink itself is covered by paylink_test.go, not re-tested here.
- Czech mail subject and text are constants in requests.go, from the cs entries of mail_payment_request_* in App/app/i18n.py (the host catalog does not carry mail strings).
- isdigit is ASCII-only; Python also accepts other Unicode digits. Amount or id overflow gives the invalid flash, not a 500.
- Tests seed legal_acceptance rows because Login redirects hosts without accepted terms.

## Questions
- None blocking. Bad CSRF on a same-site request redirects to the recovery page (303), which the test asserts.

## Owner steps left
- Review, then merge with scripts/merge-pr-on-green.sh. Nothing pushed; no PR opened from here.
