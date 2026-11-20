# 1597a report

## Files

- `go/internal/web/stays/claim_seed.go` — `EnsureClaimRow`, `StartClaim`, `ConfirmClaim`, `LockGuestAccess`
- `go/internal/web/stays/claim_seed_test.go`, `testdata/demo_claim_golden.json`
- `go/internal/web/stays/claim_ops.go` — `startClaimResend` returns secret
- `App/scripts/go_demo_claim_golden.py`, `App/tests/test_go_demo_claim_golden.py`

## Commands

- `sha256sum -c docs/tasks/1597a-files/MANIFEST.sha256` — six `: OK`
- `go test ./internal/web/stays/ -count=1 -run 'DemoClaim|ClaimSeed'` — pass (`TestClaimSeedParity` skipped without DB URL)
- `pytest tests/test_go_demo_claim_golden.py` — 1 passed

## §7

- [x] Checksums
- [x] Tests
- [x] Diff scope

## Deviations

None.

## Owner steps

None (package export only; no route switch).