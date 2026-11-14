# 1590 report

Status: review (one big PR mode; no push, no PR, no mcp tool)

## 1. Files changed

- `fbabd2c` 1590 step 1: `go/internal/web/customers/actions.go`, `actions_account.go`, `actions_test.go`, `templates/i18n.json`, `templates/i18n_keys.txt` (721 insertions, only §3 paths)
- step 6: `docs/tasks/1590-report.md`, brief status line

## 2. Commands

- Step 0: grep anchors all `1`; `actions.go` absent; `1364` commits present (`022ad2c`, `01e1176`, `79f840f`); sidecars = 5; `App/scripts/go_host_i18n.py --check` run with `App/.venv` (symlink to /var/tmp/ubyvenv, not committed) exit 0.
- Step 1 sha256sum -c: all 5 `: OK`.
- Step 2 `gofmt -l`, `go build ./...`, `go vet ./internal/web/customers/... ./cmd/...`: no output.
- Step 4: `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55901/postgres go test ./internal/web/customers/... ./cmd/ubyhost-web/... -count=1`
  ```
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/customers	5.742s
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.116s
  ```
- Step 4 named tests (`-v -run '^TestAccountActionGuards$|^TestStatusAction$|^TestExtendTrialAction$|^TestResendVerificationAction$|^TestPyIntAndClamp$'`):
  ```
  --- PASS: TestAccountActionGuards (0.70s)
  --- PASS: TestStatusAction (0.85s)
  --- PASS: TestExtendTrialAction (0.81s)
  --- PASS: TestResendVerificationAction (0.93s)
  --- PASS: TestPyIntAndClamp (0.00s)
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/customers	3.300s
  ```
- SKIP count over the whole run (`-v`, both packages): **0**. 48 `--- PASS` lines in total, no FAIL.
- Step 5: PostgreSQL stopped (`server stopped`), data dir removed.
- Context lint (§6): `context lint: OK`.

## 3. Section 7 acceptance

- [x] sha256sum: 5 files OK
- [x] step 2 silent
- [x] step 4: ok lines, 5 named tests PASS, 0 SKIP, 0 FAIL
- [x] `git log --grep='^1590 step'` lists step 1; stat lists only §3 paths
- [x] `go_host_i18n.py --check` exit 0
- [x] no `UBYHOST_GO_PATHS`, Caddy, compose, env or Python file changed; nothing pushed
- [x] UI: not applicable

## 4. Deviations

- The brief's step 6 asked for a commit of the report; done as `1590 step 6`.
- Step 0 Python check needed a venv: `App/.venv` symlinked to `/var/tmp/ubyvenv` (untracked, not committed).

## 5. Questions

None.

## 6. Owner steps left

None for this brief (routes stay dormant until brief 1594).
