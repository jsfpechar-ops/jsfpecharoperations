# 1593 report: GET /admin home (Go)

Status: review. One big PR mode: commits on the checked-out branch, no push, no PR.

## 1. Files changed

Commit `988629e 1593 step 1` (5 files, 425 insertions; sidecars copied from `docs/tasks/1593-files`, hashes verified):
- go/internal/web/customers/home.go (158)
- go/internal/web/customers/home_test.go (107)
- go/internal/web/customers/templates/admin_home.tmpl (81)
- go/internal/web/customers/templates/i18n.json (55, replaced)
- go/internal/web/customers/templates/i18n_keys.txt (24, replaced)

Steps 2 to 5 changed nothing. Step 6 commits this report and the brief status.

## 2. Commands (last 5 lines each)

- Step 1: `sha256sum -c` printed `: OK` for all 5 files.
- Step 2: `gofmt -l`, `go build ./...`, `go vet ./internal/web/customers/... ./cmd/...`: no output.
- Step 0 i18n: `App/.venv/bin/python App/scripts/go_host_i18n.py --check` exit 0, no output (App/.venv is a symlink to /var/tmp/ubyvenv, never committed).
- Step 4: `go test ./internal/web/customers/... ./cmd/ubyhost-web/... -count=1`
  ```
  ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/customers  18.381s
  ok  github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web  0.141s
  ```
- Step 4 named tests: `go test ./internal/web/customers/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestHomePage$|^TestHomePageNeedsAdmin$'`
  ```
  --- PASS: TestHomePage (2.34s)
  --- PASS: TestHomePageNeedsAdmin (1.34s)
  ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/customers	3.703s
  ok  github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.093s [no tests to run]
  ```
- Full verbose run of both packages: 57 `--- PASS`, 0 `--- FAIL`, 0 `--- SKIP`. The PostgreSQL tests ran (`UBYHOST_TEST_DATABASE_URL` pointed at the local PostgreSQL 16 on port 55904).
- `python3 scripts/context_lint.py`: `context lint: OK`.

**SKIP count: 0.**

## 3. Section 7 acceptance

- [x] sha256 check: 5 of 5 OK.
- [x] Step 2 silent.
- [x] Step 4: both named tests PASS, 0 SKIP, 0 FAIL.
- [x] Commit list and stat show only section 3 paths.
- [x] `go_host_i18n.py --check` exit 0. No `UBYHOST_GO_PATHS` change; no Caddy, compose, env or Python file changed; nothing pushed. `GET /admin` is not registered (brief 1594).
- [ ] Screenshots: not taken. The page is dormant (nothing routes to it until 1594), so there is no 390 px page to shoot. The UX gate (rules 7 and 10) runs on staging before the owner adds the path.

## 4. Deviations

- PostgreSQL started on port 55904, data dir `/var/tmp/pg-1593`, as the owner instructed (the brief says 55593 and `/var/tmp/pg1593`). Stopped and removed after step 4.
- `App/.venv` symlinked to `/var/tmp/ubyvenv` so the i18n check could import FastAPI. Not committed.
- Commit messages carry the session trailer lines, as the session reminder asked.

## 5. Questions

None.

## 6. Owner steps left

- Brief 1594 registers the routes. The UX gate for `/admin` runs on staging before the path is added to `UBYHOST_GO_PATHS`.
- Known difference F2 (MRR and ARR printed at one hundredth, reproduced on purpose) is listed for the owner decision in brief 1594.
