# 2077 implementation report

Status: review

Files changed: `go/internal/mailnotify/claim.go`, `claim_i18n.go`, `claim_test.go`, `go/internal/web/stays/claim_seed.go`, `claim_ops.go`, `claim_seed_test.go`.

Checks run:

- `go test ./internal/mailnotify/ -run 'ClaimMailGolden|Golden|MatchesPython' -count=1 -v`: PASS; golden, reminder, fee, and door-code tests passed, including six-language claim subject checks against the Python catalog strings and completed-stay variation.
- `go test ./internal/web/stays/ -run 'ClaimMailOutbox|ClaimSeed|ClaimOps' -count=1 -v` with the isolated migrated DB: PASS; new outbox test covers guest start, host resend, reply-to, encrypted token decryption, markers, escaped HTML, no eligible reply address, and replay producing one row. One pre-existing signed-out redirect test skipped.
- `git diff --check`: PASS.

Completed: localized subject/body/HTML, resend kind and dedupe key selection, shared host/guest resend encryption and payload builder, scoped reply address, synthetic six-language subject checks against Python catalog copy, completed-stay variation, and outbox assertions.

Deviations: full HTML byte-for-byte comparison with the Python composer was not practical because the repo Python environment lacks its runtime dependencies. Tests check the Python catalog copy, marker placement, and existing shell escaping. One pre-existing signed-out redirect test is skipped as documented in its test. No live mail was sent.

Owner steps: none. No push, PR, or deployment performed.
