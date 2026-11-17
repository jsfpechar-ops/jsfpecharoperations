# 1702b report

Status: review

## Files (git show --stat, commit 6841c74)

- go/internal/web/properties/apartment_detail.go (+43/-)
- go/internal/web/properties/apartment_detail_refused_test.go (new, 118)
- go/internal/web/properties/apartmentdetail/apartment_detail.tmpl
- go/internal/web/properties/apartmentdetail/i18n.json
- go/internal/web/properties/apartmentdetail/i18n_keys.txt
- docs/tasks/1702b-go-apartment-update.md (Status: ready to review)
- docs/tasks/1702b-report.md (this file)

Step 0 and step 1 hashes: all `: OK`.

## Commands (last lines)

- Step 2, gofmt: no output. `go build ./...` rc=0, `go vet` rc=0. Build printed only `go: downloading ...` module lines (no errors).
- Step 3: "Python checks: CI only (no App/.venv)".
- Step 5, `go test ./internal/web/properties/... ./cmd/ubyhost-web/...` on PostgreSQL 16 (throwaway, port 55473): `ok` properties 24.3s, `ok` cmd/ubyhost-web 3.5s, rc=0. Named tests: `--- PASS` TestApartmentDetailFee, RefusedBasics, RefusedFeeAndLock, Door. SKIP count: 0.
- Context lint (`scripts/context_lint.py`): OK.

## Acceptance (§7)

- [x] Step 0: 5 sidecars, 4 pre-hashes OK; step 1: 5 OK.
- [x] Step 2 printed no errors (see deviation).
- [x] Step 3: CI only, no App/.venv.
- [x] Step 5: two ok lines, four named tests PASS, SKIP 0.
- [x] Log lists step 1 only; stat shows only §3 paths.
- [x] No route added; nothing in App/ or UBYHOST_GO_PATHS changed.

## Deviations

- Step 2: `go build` printed module-download lines to stderr. Exit codes were 0; no error output.
- Done: steps 0 to 7 (step 6 is pending, see below). Nothing left.
- PostgreSQL cluster stopped; `pg_ctl status` says no server running. A zombie `[postgres]` process (PID 5133) remains until reaped by its parent.

## Questions

None.

## Owner steps left

None.

UX pending until 1705: template change on dormant /apartments/{id}; the 390/768/1280 screenshots and the layout lint of the refused save move to 1705 (with 1702c's POST).

1702c is next.
