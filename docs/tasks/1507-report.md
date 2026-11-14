# 1507 report

## Files changed

46 paths from `docs/tasks/1507-files/SHA256SUMS`, plus `go/internal/web/auth/auth.go`, `go/internal/web/auth/auth_test.go`, `deploy/lightsail/docker-compose.yml`, `docs/tasks/1507-go-auth-signup.md`, `docs/tasks/1507-report.md`.

## Commands

| Command | Last lines | Notes |
|---|---|---|
| Step 0 sidecar `sha256sum -c` | `sidecar check done` | 46 files, anchors 11×1 |
| Step 1 copy | `copied 46` | |
| Step 2 `routes.py` | `routes: 4 rows appended; count 34 -> 38` | gofmt/build/vet empty |
| Step 3 `compose_env.py` | `added: UBYHOST_SIGNUP_ENABLED UBYHOST_SIGNUP_NOTIFY_EMAIL` | one deploy file |
| PG16 init/start | `server started` | port 55507, `/var/tmp/pg1507` |
| `gofmt -l internal/web/auth` | (empty) | |
| `go build ./...` | (empty) | |
| `go vet ./internal/... ./cmd/...` | (empty) | |
| `go test -v ./internal/web/auth/` | `TestSignupPagesMatchPython`, `TestSignupWorkspaceFromEmail`, `TestSignupDatabase`, `TestRoutesBuildWithoutPool` PASS; `ok .../auth` | **SKIP count: 0** |
| `go test` signup/turnstile/clientip/session/cmd | six `ok` lines | |
| `go mod tidy -diff` | (empty) | |
| `signup_pages_golden.py --check` | `rc=0` | |
| `pytest` test_go_signup_pages, test_go_auth_routes, test_go_public_pages | `4 passed in 3.07s` | |
| `context_lint.py` | `context lint: OK` | |

## §7 acceptance

- [x] Commits `1507 step 1`, `1507 step 2`, `1507 step 3`, `1507 report`
- [x] File set matches SHA256SUMS + shared edits + report
- [x] `sha256sum -c` quiet from repo root
- [x] Step 2 `auth.go`: `^+` count 5, `^-[^-]` count 0
- [x] §6 as stated, 0 skipped
- [x] No forbidden paths in 1507 commits

## Deviations

Installed `postgresql-16` on the executor VM (binaries were absent). Route baseline count was 34 (siblings on `go-wave3`), not 18.

## Questions

None.

## Owner steps left

Per brief §Owner: no production change until sign-up paths are added to `UBYHOST_GO_PATHS` later.