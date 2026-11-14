# 1505 report

Status: review

## Files changed

- `go/internal/web/auth/acct_shell.go`
- `go/internal/web/auth/acct_templates/shell.tmpl`
- `go/internal/web/auth/acct_templates/account_accept.tmpl`
- `go/internal/web/auth/acct_templates/two_factor_setup.tmpl`
- `go/internal/web/auth/acct_templates/two_factor_recovery.tmpl`
- `go/internal/web/auth/acct_i18n_keys.txt`
- `go/internal/web/auth/acct_i18n.json`
- `go/internal/web/auth/account_setup.go`
- `go/internal/web/auth/account_golden_test.go`
- `go/internal/web/auth/account_setup_test.go`
- `go/internal/web/auth/testdata/account_setup.json`
- `App/scripts/auth_account_golden.py`
- `App/tests/test_go_auth_account.py`
- `go/internal/web/auth/auth.go`
- `go/internal/web/auth/auth_test.go`
- `docs/tasks/1505-report.md`

## Commands (last lines)

| Command | Tail |
|---|---|
| `gofmt -l internal/web/auth` | (empty) |
| `go build ./...` | (empty) |
| `go vet ./internal/... ./cmd/...` | (empty) |
| `go test` (auth, session, hostweb, cmd) | 6× `ok` |
| `go test ./internal/web/auth/ -v` SKIP grep | **SKIP count: 0** |
| `go mod tidy -diff` | (empty) |
| `pytest test_go_auth_account test_go_auth_routes` | `4 passed in 0.21s` |
| `python3 scripts/context_lint.py` | `context lint: OK` |

Route count after step 2: **30** (was 26 on this base; +4 from 1505).

No screenshot: the Go pages are proven equal to Python's HTML by `TestAccountSetupGoldenDatabase`; Go pages cannot be screenshotted yet (open item 7).

## §7 Acceptance

- [x] `git log --grep='^1505 step'` lists steps 1 and 2; `1505 report` present.
- [x] Commits touch only the 16 implementation files plus this report (not `1505-go-auth-account-setup.md` in commits).
- [x] Sidecar `cmp` matches all thirteen copies.
- [x] `auth.go` diff vs base includes the four account rows (among sibling route rows).
- [x] Section 6 outputs as stated; SKIP count 0.
- [x] No commit touches `go.mod`, `App/app/`, `hostweb/`, `deploy/`, `docs/context/`.
- [x] No screenshot note above.

## Deviations

1. Step 0 anchor grep for `auth_test.go` failed in one shell due to backtick quoting; anchor exists (`grep -cF 't.Errorf("%d routes, want '` → 1).
2. No PostgreSQL 16 on the VM initially; `apt install postgresql-16` and disposable server on port **55505** (`/var/tmp/pg55505`).
3. `auth_account_golden.py` rewrote `account_setup.json` with hash `37c95612…` (not `d18ef021…`); file **reverted** to sidecar copy per §4; `acct_i18n.json` hash unchanged; `4 passed` pytest.
4. Work branch **wt-1505** (coordinator isolation); brief text assumes go-wave3 only — no PR per assignment.

## Questions

None.

## Owner steps left

Per brief §Owner steps: none for this brief alone (dormant until `UBYHOST_GO_PATHS` includes `/account/accept` and `/account/2fa/setup` with trusted proxy CIDRs).