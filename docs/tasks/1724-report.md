# 1724 report: guest form save

Status: review

## Files changed

- `go/internal/web/guest/form_save.go` (sidecar + gofmt)
- `go/internal/web/guest/form_save_test.go`
- `go/internal/web/guest/testdata/form_save_golden.json`
- `go/internal/web/guest/wave_routes.go` (removed `RegisterFormSave` 501 stub; real handler in `form_save.go`)
- `App/scripts/go_form_save_golden.py`
- `App/tests/test_go_form_save_golden.py`
- `go/cmd/ubyhost-web/register_web_guest_form_save.go` (unchanged on main; wave PR)
- `go/cmd/ubyhost-web/register_web_guest_form_save_test.go` (unchanged on main)

## Commands (last lines)

- `sha256sum -c docs/tasks/1724-files/MANIFEST.sha256`: 7× OK (after gofmt on `form_save.go` only)
- `gofmt -l .`: empty (guest tree)
- `go vet ./internal/web/guest/... ./cmd/ubyhost-web/...`: silent
- `go test ./internal/web/guest/... -count=1`: pass
- `go test ./cmd/ubyhost-web/... -count=1`: pass
- `go test ./internal/web/... ./cmd/ubyhost-web/... -count=1`: **settings** package fails without `UBYHOST_TEST_DATABASE_URL` (pre-existing; not in §3)
- `pytest tests/test_go_form_save_golden.py -q`: 1 passed
- `python3 scripts/context_lint.py`: OK

## §7 acceptance

- [x] Sidecars copied; wave stub replaced with real `RegisterFormSave`
- [x] Route registration test green
- [x] Golden shape test green
- [ ] Full DB golden parity (`UBYHOST_TEST_DATABASE_URL`) not run in this environment
- [ ] Host browser / 390px screenshots (guest POST; no host page change)

## Deviations

- Step 0 anchor `register_web_guest_form_save.go` already on main from guest wave PR (#1205); copy was no-op for register files.
- `wave_routes.go` edited (not in brief §3 table) per wave rollout: stub removal.
- `gofmt -w` on `form_save.go` after copy (brief §6 allows empty `gofmt -l`).

## Questions

None.

## Owner steps

None.