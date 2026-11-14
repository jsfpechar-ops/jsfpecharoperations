Status: review

## Files

`App/scripts/auth_deletion_golden.py`, `go/internal/web/auth/deletion.go`, `go/internal/web/auth/deletion_test.go`, `go/internal/web/auth/testdata/schedule_deletion.json`, `go/internal/web/auth/auth.go`, `go/internal/web/auth/auth_test.go`, `go/internal/web/auth/i18n_keys.txt`, `go/internal/web/auth/i18n.json`, `docs/tasks/1509-go-auth-deletion.md` (Status).

## Commands (last 5 lines; SKIP count **0**)

- `edit_routes.py`: `added` / `route count 39 -> 40`
- `auth_deletion_golden.py`: `wrote schedule_deletion.json` / `wrote i18n.json`
- `sha256sum schedule_deletion.json`: `8dadea91…eff4c8` (matches brief)
- targeted `go test` (step 4): five `--- PASS`, `ok …/auth 1.986s`, no SKIP
- `go test ./internal/web/auth/... ./internal/mail/... ./cmd/ubyhost-web/...`: all `ok` (auth 29.069s)
- golden subcases: `20` lines `--- PASS`
- `gofmt -l`, `go build ./...`, `go vet`, `go mod tidy -diff`: empty
- `pytest test_go_auth_routes.py`: `2 passed in 0.12s`
- `context_lint.py`: `context lint: OK`

## §7 acceptance

- [x] `1509 step` 1–3 and `1509 report`
- [x] Commit file set = §3 nine files + brief Status
- [x] `cmp` sidecar `.txt` vs repo: clean
- [x] `grep -c d.scheduleDeletion auth.go` → 1
- [x] Step 4 / §6 outputs; `TestScheduleDeletionGoldenDatabase` 20/20, 0 SKIP
- [x] No forbidden paths in `1509` commits

## Deviations

None.

## Questions

None.

## Owner steps

Merge with wave PR; add `/admin/users/*/schedule-deletion` to `UBYHOST_GO_PATHS` when switching the admin users POST block (see brief §Owner steps).