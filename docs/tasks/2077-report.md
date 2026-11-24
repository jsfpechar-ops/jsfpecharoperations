# 2077 implementation report

Status: blocked

Files changed: `go/internal/mailnotify/claim.go`, `claim_i18n.go`, `claim_test.go`, `go/internal/web/stays/claim_seed.go`, `claim_ops.go`.

Checks run:

- `go test ./internal/mailnotify/ -run 'ClaimMailGolden|Golden|MatchesPython' -count=1 -v`: PASS; golden, reminder, fee, and door-code tests passed, including `TestClaimMailGolden`.
- `go test ./internal/web/stays/ -run 'ClaimMailOutbox|ClaimSeed|ClaimOps' -count=1 -v`: PASS; claim seed and ops checks passed. One pre-existing signed-out redirect test skipped.
- `git diff --check`: PASS.

Completed: localized subject/body/HTML, resend kind and dedupe key selection, shared host/guest resend encryption and payload builder, scoped reply address, and a synthetic six-language builder check.

Deviations: the named focused tests do not exercise queued outbox payloads, token encryption, replay, or completed-stay rendering through either route. `TestClaimMailOutbox` is not implemented. No live mail was sent. The report is blocked pending these focused assertions and delivery-timing review.

Owner steps: none. No push, PR, or deployment performed.
