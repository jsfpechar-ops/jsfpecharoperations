# 1722 report

Status: review

## Commits

- `1722 step 1` — sidecar copy, `wave_routes.go` party stub removal (#1205)
- `1722 step 3` — `partyMailEnabled` rename (clash with `shared.go`); drop duplicate `testPoolOptional` in `party_test.go`

## Commands (last lines)

- `sha256sum -c MANIFEST.sha256` — 7× OK (step 1); manifest no longer matches `party.go` after rename
- `gofmt -l .` — empty after gofmt
- `go vet ./internal/web/guest/... ./cmd/ubyhost-web/...` — silent
- `go test ./internal/web/guest/... ./cmd/ubyhost-web/... -count=1` — ok (guest, ubyhost-web)
- `pytest tests/test_go_party_golden.py` — 1 passed
- `python3 scripts/context_lint.py` — OK

## §7

- [x] Party routes registered via `register_web_guest_party.go`; stubs removed from `wave_routes.go`
- [x] `TestPartyGoldenHTTP`, `TestGuestPartyRoutesRegistered` pass
- [x] No `UBYHOST_GO_PATHS` / deploy edits

## Deviations

- Renamed `mailEnabled` → `partyMailEnabled` in `party.go` (main already had `mailEnabled` in `shared.go`)
- Removed duplicate `testPoolOptional` from `party_test.go` (exists in `shell_test.go`)

## Questions

None.

## Owner steps

None.