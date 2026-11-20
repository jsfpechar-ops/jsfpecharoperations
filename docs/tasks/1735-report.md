# 1735 report

Status: review

## Commits

- `1735 step 1` — sidecars copied, MANIFEST OK
- `1735 step 2` — golden script (removed stray `doc =` in sidecar), golden verified
- `1735 step 3` — lifecycle tests (dedupe types/funcs vs guest_edit), i18n_keys + regenerate
- `1735 step 4` — dormant `register_web_stays_guest_lifecycle.go`

## Commands (last lines)

- `gofmt -l .` — empty
- `go vet ./internal/web/... ./cmd/...` — silent
- `go test ./internal/web/stays/... ./cmd/ubyhost-web/...` — ok
- `pytest tests/test_go_guest_lifecycle_golden.py` — 1 passed
- `context_lint.py` — OK

## Deviations

- Sidecar `go_guest_lifecycle_golden.py` had a syntax typo; one-line fix.
- `guest_lifecycle_test.go` sidecar duplicated symbols with `guest_edit_test.go`; renamed type and dropped duplicate unit tests.
- Added four flash keys to `i18n_keys.txt` + regenerated `i18n.json` (same pattern as 1732/1734 reports).

## §7

- [x] Dormant routes registered; not in `UBYHOST_GO_PATHS`
- [x] Golden parity test passes
- [ ] Host browser screenshots (no host page HTML change in this brief)

## Questions

None.