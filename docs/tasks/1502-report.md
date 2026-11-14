# 1502 report

Status: review

## Files changed

`go/internal/web/auth/authpage/*` (package + templates), `login.go`, `login_test.go`, `testdata/login.json`, `auth.go`, `auth_test.go`, `App/scripts/auth_login_golden.py`, `App/tests/test_go_auth_pages.py`, `deploy/lightsail/docker-compose.yml`, `docs/tasks/1502-go-auth-login.md` (Status).

## Commands (last 5 lines each)

- Step 1 `go test ./internal/web/auth/authpage/`: `ok …/authpage 0.009s`
- Step 3 edits: `added 4 rows` / `route count 18 -> 22`; tests: two `ok` (auth 12.6s, authpage).
- Step 4 golden: `wrote login.json`, `wrote i18n.json`; hashes match sidecar; pytest `5 passed`.
- Step 5 compose: `added 4 keys`; diff `1 file, 5 insertions`; `16 passed` wp32.
- §6 go test (auth, hostweb, session, turnstile, clientip, ubyhost-web): nine `ok` lines; **SKIP count: 0**.
- §6 pytest: `21 passed`; context_lint: `OK`.

## §7 Acceptance

- [x] Commits: steps 1, 3, 4, 5, report.
- [x] 19 section-3 paths in commits (+ brief Status).
- [x] `cmp` sidecar vs tree: clean.
- [x] Four login routes in `auth.go`; `UBYHOST_GO_PATHS` count unchanged (2).
- [x] §6 as stated; 0 skipped.
- [x] No forbidden paths in commits.

## Deviations

- Branch `wt-1502` from `origin/go-wave3` (project isolation); not pushed from `go-wave3`.
- Installed `postgresql-16`; started disposable PG on 55502 with `sudo -u postgres` (`su postgres` unavailable).

## Questions

None.

## Owner steps left

1. No path switch until owner adds `/login` and `/login/link` to `UBYHOST_GO_PATHS`.
2. After deploy: verify Turnstile + `UBYHOST_TRUSTED_PROXY_CIDRS` in Go container (brief § Owner 2).
3. Decide mail delivery when Go serves login (brief § Owner 3).
4. UX gate at switch (brief § Owner 4).