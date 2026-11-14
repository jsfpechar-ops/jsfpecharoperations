# 1593: Go customer admin, part 4: the operator console home GET /admin

Status: todo
Depends on: 1592 | Base commit: none (one big PR mode: the branch that is checked out) | Branch: the current one
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (operator pages, billing and mail; no filing, no guest data)

> **One big PR mode.** The owner wants one big pull request for the whole Go port. You work on the branch that is checked out now. Never create a branch, never push, never open a PR, never call an `mcp__` tool. After each step that changes a file, commit with the message `1593 step k` (k is the step number) and nothing else in the first line; end the message with the two trailer lines from the session reminder if one is given. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1593 step'` and `git show --stat` on those commits.

## 1. Objective

Port `GET /admin` (`admin_home` in `App/app/routes/admin_customers.py`, template `admin_home.html`) to Go with the host layout: the MRR/ARR/overdue/trialing stats, the System problems list (counts from brief 1592), and the four queues (overdue invoices, trials ending, unverified sign-ups, ending at renewal).

## 2. Context

Rules (AGENTS.md): 1 filing is not touched; 2 privacy: no new personal-data field and no new outbound request; 3 test data is made up (`@example.test`, test-only secrets); 4 no new dependency; 5 plain PostgreSQL through pgx with the Python SQL; 6 light mode, forms work without JavaScript; 8 never push to `main`; 11 Go first.

**PR text (hard rule 2):** read-only page; no new outbound request and no new personal-data field. It shows the display names and invoice numbers Python shows to the operator.

**All code is pre-written, compiled and tested.** Sidecars are `docs/tasks/1593-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Write nothing outside §3. Two of them (`templates/i18n.json`, `templates/i18n_keys.txt`) were replaced by 1591; this version is the complete catalog of the area and replaces them again: replace means the plain `cp` of step 1, there is nothing to merge. `templates/admin_home.tmpl` is new and is picked up by the package's template embed (`go:embed`), which already covers `templates/*.tmpl`.

**The thread (briefs 1590 to 1594).** Port the 7 routes of `App/app/routes/admin_customers.py` that Go does not serve yet (the file has 10 routes; briefs 1361, 1363 and 1364 ported `GET /admin/customers`, `GET /admin/customers/{user_id}` and `POST /admin/customers/{user_id}/aktivovat`; `GET /admin/funnel` is from brief 1361 and is not in that file) into the existing package `go/internal/web/customers` (package `customers`). Nothing routes to them until the owner adds the paths to `UBYHOST_GO_PATHS`.

| Brief | Routes (method path, Python function) | New files |
|---|---|---|
| 1590 | `POST /admin/customers/{user_id}/stav` (customer_status), `/prodlouzit` (customer_extend_trial), `/overit-znovu` (customer_resend_verification); the shared action guards | `actions.go`, `actions_account.go` |
| 1591 | `POST /admin/customers/{user_id}/sleva` (customer_discount), `/plan` (customer_plan), `/priradit` (customer_assign_plan) | `actions_billing.go`, `actions_invoicer.go` |
| 1592 | the six "System problems" counts of `admin_ops.overview()` (no route) | `ops.go` |
| 1593 | `GET /admin` (admin_home) with its template | `home.go`, `templates/admin_home.tmpl` |
| 1594 | registers the 7 routes in `go/cmd/ubyhost-web` and pins the route inventory (all 10 routes of the file) | `register_web_customers_test.go` |

**Order:** 1590, 1591, 1592, 1593, 1594, each `Depends on` the one before. The files `templates/i18n.json` and `templates/i18n_keys.txt` are named by 1590, 1591 and 1593: each brief replaces both with the version for its stage (1593's is the full catalog), so this order is the only valid one. Briefs 1360 to 1364 (customer admin list, detail, toggle) must already be in the branch; the billing engine (`go/internal/billing`, brief 1340), `go/internal/billingjob`, `go/internal/signup` and `billingweb.OperatorQueue` / `GetPortfolio` (brief 1341, `go/internal/web/billing/analytics.go`) are older still. The billing page thread 1555 to 1560 is not needed: 1593 reads only `OperatorQueue` and `GetPortfolio`, which exist since 1341.

**What this brief ports, with the Python lines:**

| Go | Python | What it does |
|---|---|---|
| `HomeHandler` | `admin_home` 25-40 | `requireAdmin` (signed out: 303 to `/login?next=/admin`; a host: 403 `Administrators only.`); today is the Europe/Prague date (`pragueDay`, `config.TIMEZONE`); `billingweb.OperatorQueue(day)`, `Summary(day)` (the counts by state), `GetPortfolio(day)` only when billing is on (`UBYHOST_BILLING_ENABLED`), `Ops` and `ReviewAlertCount` (brief 1592) |
| `templates/admin_home.tmpl` | `templates/admin_home.html` | Go twin: the banner `customers.billing_off` when billing is off, the four stats, `admin.today.clear` when there is nothing, else the problems list (a row only when its count is not 0, link `/admin/operations#<anchor>`) and the four queue tables |
| `homeView` and the `home*` types | the Jinja `set problems` and `set queues_empty` | the lists Jinja builds inline; `ui_section` call blocks are written out as their markup (Go templates cannot pass a block as `caller`) |

**Known differences from Python (not fixed here, listed in every report):**

- F1. A wrong method on `/admin` answers Go's plain-text `405`; Python's JSON `{"detail":"Method Not Allowed"}`.
- F2. MRR and ARR: `admin_home.html` passes the portfolio's whole-crown `mrr_czk` and `arr_czk` to the `money_czk` filter, which expects haler, so Python prints one hundredth of the real value. Go reproduces it on purpose (`moneyCZK(portfolio.MRRCZK)`), so the page matches Python until the owner decides to fix both; the test pins it. It is a display bug of Python and is listed in the owner steps of brief 1594.
- F3. For a customer whose unverified row has no username, `display_name or username` prints an empty name in Python (the row has no `username` key); Go prints the same empty name.
- F4. Layout chrome (page title, tabs, the help tip) comes from the Go host layout (`go/internal/hostweb/layout`), as on the pages of briefs 1361 and 1364; no golden file compares the full HTML, `TestHomePage` compares the visible lines and the links.

**Dates and numbers:** `TestHomePage` runs over the golden seed with today 2026-11-13 and pins the dates `16.11.2026`, `20.11.2026`, `14.11.2026`, `01.12.2026` (through `fmtDate`, `dd.mm.yyyy`), the MRR and ARR through `moneyCZK` of the portfolio's own numbers, the overdue invoice of the customer "Gina Overdue", and that the page does not say "All clear" while problems exist; the Czech title and section names; and billing off (no stats, the neutral banner).

**Verified by the brief writer** (fresh throwaway worktree of the branch head; briefs 1590 to 1593 copied in order exactly as their step 1 does): gofmt empty; `go build ./...` and `go vet ./internal/web/customers/... ./cmd/...` silent; `go test ./internal/web/customers/... ./cmd/ubyhost-web/...` ok on PostgreSQL 16 with the two named tests PASS and 0 skipped; `go_host_i18n.py --check` exit 0 (FastAPI stubbed in the writer's environment). The template was read line by line against `admin_home.html`. Not run: any Python test, any browser test (the page is dormant and no screenshot can be taken, see §7).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/customers/home.go` | create | `HomeHandler`, the view types, `nameOr` |
| `go/internal/web/customers/templates/admin_home.tmpl` | create | Go twin of `admin_home.html` |
| `go/internal/web/customers/home_test.go` | create | `TestHomePage`, `TestHomePageNeedsAdmin` |
| `go/internal/web/customers/templates/i18n.json` | replace (created by 1361, replaced by 1590 and 1591; the complete catalog) | adds the console home strings |
| `go/internal/web/customers/templates/i18n_keys.txt` | replace (created by 1361, replaced by 1590 and 1591) | the key list that generates `i18n.json` |
| `docs/tasks/1593-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1593-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git log --oneline --grep='^1592 step' | tail -3` prints at least one line (brief 1592 is in this branch).
   - `grep -cF "func Ops(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, at time.Time) (OpsCounts, error) {" go/internal/web/customers/ops.go | tail -1` prints `1`.
   - `grep -cF "func ReviewAlertCount(ctx context.Context, pool *pgxpool.Pool) (int64, error) {" go/internal/web/customers/ops.go | tail -1` prints `1`.
   - `grep -cF "func OperatorQueue(ctx context.Context, q DB, today time.Time) (Queue, error) {" go/internal/web/billing/analytics.go | tail -1` prints `1`.
   - `grep -cF "func GetPortfolio(ctx context.Context, q DB, today time.Time) (Portfolio, error) {" go/internal/web/billing/analytics.go | tail -1` prints `1`.
   - `grep -cF "func Summary(ctx context.Context, pool *pgxpool.Pool, today time.Time) (map[string]int64, error) {" go/internal/web/customers/query.go | tail -1` prints `1`.
   - `grep -cF "func adminTabs(lang tr, current string) [][]any {" go/internal/web/customers/pages.go | tail -1` prints `1`.
   - `grep -cF "func pragueDay(at time.Time) time.Time {" go/internal/web/customers/pages.go | tail -1` prints `1`.
   - `grep -cF "func billingOn(getenv func(string) string) bool {" go/internal/web/customers/pages.go | tail -1` prints `1`.
   - `grep -cF "func moneyCZK(haler int64) string {" go/internal/web/customers/detail.go | tail -1` prints `1`.
   - `grep -cF "func fmtDate(v any) string {" go/internal/web/customers/detail.go | tail -1` prints `1`.
   - `ls go/internal/web/customers/home.go go/internal/web/customers/templates/admin_home.tmpl 2>&1 | tail -2` says "No such file" for both.
   - i18n catalog is in step with its key list (needs Python with FastAPI; use `App/.venv/bin/python` if that file exists, else `python3`; if the import fails write "CI only" in the report and go on): from the repo root `PY=python3; [ -x App/.venv/bin/python ] && PY=App/.venv/bin/python; $PY App/scripts/go_host_i18n.py --check 2>&1 | tail -5` prints nothing and exits 0.
   - `find docs/tasks/1593-files -name '*.txt' | wc -l | tail -1` prints `5`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1593-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   9f11c31bb3d04b0afaaf106a1b5d474b0da91dea2498ce0aafd969c86853148d  go/internal/web/customers/home.go
   39df4a254f35b6056cf35d823f6ad5edb894a7838e13c3144f80a6c31685f324  go/internal/web/customers/home_test.go
   9fdcb6db8f5de3a257f30806730b21e88059fbf83fe2d421a0b95fc82bccebb1  go/internal/web/customers/templates/admin_home.tmpl
   d1377cc70fd3742ac1fd9577f40fdc0a1faaa874908cddbed0a407b43d416d5f  go/internal/web/customers/templates/i18n.json
   e7ecb49d303d7f6231d3b8cc3456349b631e920a162ee46d955dc5e1648d9d0c  go/internal/web/customers/templates/i18n_keys.txt
   EOF
   ```

   Every line must end with `: OK`. Then commit "1593 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/customers cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/customers/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). No commit (nothing changed).

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1593 && chown postgres /var/tmp/pg1593 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1593/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1593/data -o "-p 55593 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1593" -l /var/tmp/pg1593/log -w start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55593/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55593/postgres go test ./internal/web/customers/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: two lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/customers	<seconds>s` and `ok  	...go/cmd/ubyhost-web	<seconds>s`. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55593/postgres go test ./internal/web/customers/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestHomePage$|^TestHomePageNeedsAdmin$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -40
   ```

   Expected: one `--- PASS` line for each of the 2 tests (TestHomePage, TestHomePageNeedsAdmin), then `ok` lines; no `--- SKIP`, no `--- FAIL`. Then count skips in the whole run and write the number in the report: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55593/postgres go test ./internal/web/customers/ ./cmd/ubyhost-web/ -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` must print `0`.

5. Stop and delete the throwaway server (skip if you used a server you did not start):

   ```bash
   su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1593/data -m fast stop' 2>&1 | tail -2; rm -rf /var/tmp/pg1593
   ```

   Expected: `server stopped`.

6. Write the report (§9), set `Status: review` and commit "1593 step 6".

## 5. Do not touch

`go/internal/hostweb/`, `go/internal/session/`, `go/internal/billing/`, `go/internal/billingjob/`, `go/internal/signup/`, `go/internal/web/billing/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `registry.go` and every `register_*.go` that is not named in §3, the existing files of `go/internal/web/customers/` that briefs 1361 to 1364 created (`detail.go`, `handlers.go`, `handlers_test.go`, `pages.go`, `pages_test.go`, `query.go`, `query_test.go`, `testdata/`, the existing templates), `App/` (no Python file, no `App/tests/conftest.py`), `docs/context/*`, and every file not in §3. AGENTS.md rules that apply: 2 (privacy), 3 (no real data in tests), 4 (no new dependency: `go.mod` and `go.sum` stay as they are), 5 (SQL is plain PostgreSQL through pgx, taken from the Python), 8 (never push to `main`), 11 (Go first: no file under `App/app/` is named in §3, so no exception of go-first applies).

## 6. Commands

Exactly the commands of §4 (steps 1, 2, 4, 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 5 files.
- [ ] Step 2 printed nothing.
- [ ] Step 4 printed the `ok` lines, each of the 2 named tests printed `--- PASS`, and the skip count is `0` (none `SKIP`, none `FAIL`).
- [ ] `git log --oneline --grep='^1593 step' | tail -5` lists at least the step 1 commit, and `git show --stat --format=%h <that hash> | tail -20` lists only paths of §3.
- [ ] `go_host_i18n.py --check` exited 0, or the report says "CI only". No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed. `GET /admin` is not registered yet (brief 1594).
- [ ] UI (rules 7 and 10): the page is dormant (nothing routes to it and it is not registered until brief 1594) and the Python-side browser and geometry tests drive the Python app and cannot load a Go-rendered page, so no 390 px screenshot can be taken in this PR. The UX gate runs on staging before the owner adds the path (brief 1412 is the pattern); the report says so.

## 8. Stop and ask

Stop, and write the report, if:

- a check, hash or file count of step 0 or step 1 is not as stated;
- a test fails twice (read the last 30 lines, fix nothing in the sidecar files yourself: report);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1593-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git log --oneline --grep='^1593 step' | tail -10`, then one `git show --stat --format=%h <hash>` per commit).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `templates/admin_home.tmpl` against `admin_home.html` (the problems list shows a row only for a non-zero count, links `/admin/operations#<anchor>`; the overdue table links the invoice PDF `/admin/fakturace/{id}.pdf` and the customer page; F2 the MRR display) and of `home.go` (that `requireAdmin` runs before any query, that `GetPortfolio` is called only when billing is on).

## Owner steps

None here (route dormant, not registered until brief 1594). The UX gate of rule 10 for `/admin` runs on staging first (see brief 1594 owner steps).
