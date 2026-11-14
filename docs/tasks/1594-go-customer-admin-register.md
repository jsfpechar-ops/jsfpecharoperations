# 1594: Go customer admin, part 5: register the seven routes, the route inventory and the invoice environment

Status: review
Depends on: 1593 | Base commit: none (one big PR mode: the branch that is checked out) | Branch: the current one
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (operator pages, billing and mail; no filing, no guest data)

> **One big PR mode.** The owner wants one big pull request for the whole Go port. You work on the branch that is checked out now. Never create a branch, never push, never open a PR, never call an `mcp__` tool. After each step that changes a file, commit with the message `1594 step k` (k is the step number) and nothing else in the first line; end the message with the two trailer lines from the session reminder if one is given. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1594 step'` and `git show --stat` on those commits.

## 1. Objective

Register the seven new customer-admin routes (`GET /admin` and six `POST /admin/customers/{user_id}/...`) in `go/cmd/ubyhost-web`, pin that all ten routes of `admin_customers.py` are served by Go for every method, and pass the invoice seller's variables to the Go container so the plan, discount and assign actions can issue invoices there. After this brief the area is complete in Go; it stays dormant until the owner adds the paths.

## 2. Context

Rules (AGENTS.md): 1 filing is not touched; 2 privacy: no new personal-data field and no new outbound request; 3 test data is made up (`@example.test`, test-only secrets); 4 no new dependency; 5 plain PostgreSQL through pgx with the Python SQL; 6 light mode, forms work without JavaScript; 8 never push to `main`; 11 Go first.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The compose change only passes eight existing, non-secret variables (the seller's name, ICO, DIC, address, e-mail, bank account, IBAN and VAT status, which already print on every invoice) to the Go service. A bare key is passed through only when it is set in `.env`.

**All code is pre-written, compiled and tested.** Sidecars are `docs/tasks/1594-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Write nothing outside §3. `register_web_customers.go` already exists (briefs 1361, 1364 and the toggle); this version replaces it with the same file plus the seven new `mux.Handle` lines: replace means the plain `cp` of step 1. `register_web_customers_test.go` is new.

**The thread (briefs 1590 to 1594).** Port the 7 routes of `App/app/routes/admin_customers.py` that Go does not serve yet (the file has 10 routes; briefs 1361, 1363 and 1364 ported `GET /admin/customers`, `GET /admin/customers/{user_id}` and `POST /admin/customers/{user_id}/aktivovat`; `GET /admin/funnel` is from brief 1361 and is not in that file) into the existing package `go/internal/web/customers` (package `customers`). Nothing routes to them until the owner adds the paths to `UBYHOST_GO_PATHS`.

| Brief | Routes (method path, Python function) | New files |
|---|---|---|
| 1590 | `POST /admin/customers/{user_id}/stav` (customer_status), `/prodlouzit` (customer_extend_trial), `/overit-znovu` (customer_resend_verification); the shared action guards | `actions.go`, `actions_account.go` |
| 1591 | `POST /admin/customers/{user_id}/sleva` (customer_discount), `/plan` (customer_plan), `/priradit` (customer_assign_plan) | `actions_billing.go`, `actions_invoicer.go` |
| 1592 | the six "System problems" counts of `admin_ops.overview()` (no route) | `ops.go` |
| 1593 | `GET /admin` (admin_home) with its template | `home.go`, `templates/admin_home.tmpl` |
| 1594 | registers the 7 routes in `go/cmd/ubyhost-web` and pins the route inventory (all 10 routes of the file) | `register_web_customers_test.go` |

**Order:** 1590, 1591, 1592, 1593, 1594, each `Depends on` the one before. The files `templates/i18n.json` and `templates/i18n_keys.txt` are named by 1590, 1591 and 1593: each brief replaces both with the version for its stage (1593's is the full catalog), so this order is the only valid one. Briefs 1360 to 1364 (customer admin list, detail, toggle) must already be in the branch; the billing engine (`go/internal/billing`, brief 1340), `go/internal/billingjob`, `go/internal/signup` and `billingweb.OperatorQueue` / `GetPortfolio` (brief 1341, `go/internal/web/billing/analytics.go`) are older still. The billing page thread 1555 to 1560 is not needed: 1593 reads only `OperatorQueue` and `GetPortfolio`, which exist since 1341.

**Why the compose file:** the Go container receives only the variables listed under `ubyhost-go: environment:` in `deploy/lightsail/docker-compose.yml`. `billingjob.Invoicer` (used by the plan, discount and assign actions of brief 1591) reads `UBYHOST_BILLING_BANK_ACCOUNT`, `UBYHOST_BILLING_IBAN`, `UBYHOST_BILLING_VAT_STATUS`, `UBYHOST_OPERATOR_NAME`, `_ICO`, `_DIC`, `_ADDRESS` and `_EMAIL`; only `UBYHOST_OPERATOR_EMAIL` is listed today. Without them an invoice issued by Go has an empty seller, or is refused ("no invoice is issued without the IBAN", `docs/ENVIRONMENT.md`). `TestGoServiceGetsInvoiceEnv` pins the eight names. The compose file is deploy configuration, not Python application code: go-first's list of Python exceptions does not apply and no `App/app/` file is touched. Other Go briefs that issue invoices (the billing thread 1555 to 1560) have the same need; step 2 checks first that none of the names is in the block yet.

**What the route test pins** (`register_web_customers_test.go`): it reads the `@router.get/post` decorators of `App/app/routes/admin_customers.py` and requires exactly 10; every one, plus `GET /admin/funnel`, must resolve in the real mux to a pattern of its own (not the `/` catch-all); every one sent without a session answers `303` to `/login?next=<path>` (a POST carries a valid CSRF token first, as the guards run in Python's order), with a nil database pool, so no handler touches the database before the gate.

**Known differences from Python:** those listed in briefs 1590 to 1593 (F1 plain-text 405 and 422, `int()` digits, the invoice audit stamp, the MRR/ARR display).

**Route table of the area after this brief** (method path -> Go handler): `GET /admin` HomeHandler; `GET /admin/customers` ListHandler; `GET /admin/customers/{user_id}` DetailHandler; `POST /admin/customers/{user_id}/aktivovat` ToggleActiveHandler; `POST /admin/customers/{user_id}/stav` StatusHandler; `/prodlouzit` ExtendTrialHandler; `/overit-znovu` ResendVerificationHandler; `/sleva` DiscountHandler; `/plan` PlanChangeHandler; `/priradit` AssignPlanHandler; `GET /admin/funnel` FunnelHandler (redirect).

**Verified by the brief writer** (fresh throwaway worktree of the branch head; briefs 1590 to 1594 copied in order exactly as their step 1 does, then the compose patch of step 2): gofmt empty; `go build ./...` and `go vet ./internal/web/customers/... ./cmd/...` silent; `go test ./internal/web/customers/... ./cmd/ubyhost-web/...` ok on PostgreSQL 16 with the three named tests PASS and 0 skipped (before the compose patch `TestGoServiceGetsInvoiceEnv` fails with the seven missing names, which is what step 2 fixes); `go_host_i18n.py --check` exit 0. Not run: any Python test, `docker compose config` (no Docker in the writer's environment).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_customers.go` | replace (existing; the same routes plus seven) | registers the seven new routes |
| `go/cmd/ubyhost-web/register_web_customers_test.go` | create | the route inventory, the signed-out test, the compose test |
| `deploy/lightsail/docker-compose.yml` | edit (step 2) | seven environment keys in the `ubyhost-go` block |
| `docs/tasks/1594-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1594-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git log --oneline --grep='^1593 step' | tail -3` prints at least one line (brief 1593 is in this branch).
   - `ls go/internal/web/customers/home.go go/internal/web/customers/actions_account.go go/internal/web/customers/actions_billing.go 2>&1 | tail -3` lists the three files.
   - `grep -c "^func [A-Za-z]*Handler(pool \*pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc" go/internal/web/customers/home.go go/internal/web/customers/actions_account.go go/internal/web/customers/actions_billing.go | tail -3` prints `home.go:1`, `actions_account.go:3` and `actions_billing.go:3`.
   - `grep -cF 'customers.ToggleActiveHandler' go/cmd/ubyhost-web/register_web_customers.go | tail -1` prints `1` (the file is the version of the earlier briefs).
   - `ls go/cmd/ubyhost-web/register_web_customers_test.go 2>&1 | tail -1` says "No such file".
   - `grep -cF '  ubyhost-go:' deploy/lightsail/docker-compose.yml | tail -1` prints `1`.
   - `grep -c '^      UBYHOST_OPERATOR_EMAIL:$' deploy/lightsail/docker-compose.yml | tail -1` prints `1` (the anchor of step 2; the Python service may list it too, but the script works inside the `ubyhost-go` block only)
   - `find docs/tasks/1594-files -name '*.txt' | wc -l | tail -1` prints `2`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1594-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   af0ce54528965fb40ae855ad732645df3aa9cf56da2ff3355d0d8c9a40c2d59e  go/cmd/ubyhost-web/register_web_customers.go
   ea43626e4f0cfa69df0e944fe62638c4a96df7c0e8c78d3a016bacaa47bdeb04  go/cmd/ubyhost-web/register_web_customers_test.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1594 step 1".

2. Pass the invoice variables to the Go service (one call, repo root). The script only inserts keys inside the `ubyhost-go` block and stops with an assertion error if an anchor is missing or appears twice. First check that none of the names is in the block yet: `awk '/^  ubyhost-go:/,0' deploy/lightsail/docker-compose.yml | grep -c 'UBYHOST_BILLING_IBAN:\|UBYHOST_OPERATOR_NAME:' | tail -1` must print `0`; more: STOP (§8). Then:

   ```bash
   python3 - <<'PYEOF'
   import re
   path = "deploy/lightsail/docker-compose.yml"
   text = open(path).read()
   start = text.index("\n  ubyhost-go:\n") + 1
   m = re.compile(r"(?m)^  [a-z]").search(text, start + 4)
   end = m.start() if m else len(text)
   block = text[start:end]
   def put(block, before, names):
       anchor = "      %s:\n" % before
       assert block.count(anchor) == 1, before
       return block.replace(anchor, "".join("      %s:\n" % n for n in names) + anchor)
   def after(block, anchor_name, names):
       anchor = "      %s:\n" % anchor_name
       assert block.count(anchor) == 1, anchor_name
       return block.replace(anchor, anchor + "".join("      %s:\n" % n for n in names))
   block = put(block, "UBYHOST_BILLING_ENABLED", ["UBYHOST_BILLING_BANK_ACCOUNT"])
   block = after(block, "UBYHOST_BILLING_ENABLED", ["UBYHOST_BILLING_IBAN", "UBYHOST_BILLING_VAT_STATUS"])
   block = put(block, "UBYHOST_OPERATOR_EMAIL", ["UBYHOST_OPERATOR_ADDRESS", "UBYHOST_OPERATOR_DIC"])
   block = after(block, "UBYHOST_OPERATOR_EMAIL", ["UBYHOST_OPERATOR_ICO", "UBYHOST_OPERATOR_NAME"])
   open(path, "w").write(text[:start] + block + text[end:])
   PYEOF
   git diff --stat -- deploy/lightsail/docker-compose.yml | tail -3
   ```

   Expected: `7 insertions(+)` and nothing else. Then commit "1594 step 2".

3. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/customers cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/customers/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). No commit (nothing changed).

4. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1594 && chown postgres /var/tmp/pg1594 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1594/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1594/data -o "-p 55594 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1594" -l /var/tmp/pg1594/log -w start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55594/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 5.

5. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55594/postgres go test ./internal/web/customers/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: two lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/customers	<seconds>s` and `ok  	...go/cmd/ubyhost-web	<seconds>s`. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55594/postgres go test ./internal/web/customers/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestCustomerRoutesAllServedByGo$|^TestCustomerRoutesNeedLogin$|^TestGoServiceGetsInvoiceEnv$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -40
   ```

   Expected: one `--- PASS` line for each of the 3 tests (TestCustomerRoutesAllServedByGo, TestCustomerRoutesNeedLogin, TestGoServiceGetsInvoiceEnv), then `ok` lines; no `--- SKIP`, no `--- FAIL`. Then count skips in the whole run and write the number in the report: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55594/postgres go test ./internal/web/customers/ ./cmd/ubyhost-web/ -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` must print `0`.

6. Stop and delete the throwaway server (skip if you used a server you did not start):

   ```bash
   su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1594/data -m fast stop' 2>&1 | tail -2; rm -rf /var/tmp/pg1594
   ```

   Expected: `server stopped`.

7. Write the report (§9), set `Status: review` and commit "1594 step 7".

## 5. Do not touch

`go/internal/hostweb/`, `go/internal/session/`, `go/internal/billing/`, `go/internal/billingjob/`, `go/internal/signup/`, `go/internal/web/billing/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `registry.go` and every `register_*.go` that is not named in §3, the existing files of `go/internal/web/customers/` that briefs 1361 to 1364 created (`detail.go`, `handlers.go`, `handlers_test.go`, `pages.go`, `pages_test.go`, `query.go`, `query_test.go`, `testdata/`, the existing templates), `App/` (no Python file, no `App/tests/conftest.py`), `docs/context/*`, and every file not in §3. AGENTS.md rules that apply: 2 (privacy), 3 (no real data in tests), 4 (no new dependency: `go.mod` and `go.sum` stay as they are), 5 (SQL is plain PostgreSQL through pgx, taken from the Python), 8 (never push to `main`), 11 (Go first: no file under `App/app/` is named in §3, so no exception of go-first applies).

## 6. Commands

Exactly the commands of §4 (steps 1, 3, 5, 6, 2). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 2 files.
- [ ] Step 3 printed nothing.
- [ ] Step 5 printed the `ok` lines, each of the 3 named tests printed `--- PASS`, and the skip count is `0` (none `SKIP`, none `FAIL`).
- [ ] `git log --oneline --grep='^1594 step' | tail -5` lists at least the step 1 commit, and `git show --stat --format=%h <that hash> | tail -20` lists only paths of §3.
- [ ] `git diff --stat HEAD~1 -- deploy/lightsail/docker-compose.yml | tail -3` after step 2 shows only added lines (seven `+` lines). No path was added to `UBYHOST_GO_PATHS`; no Caddy or env file changed; no Python application file changed; nothing was pushed.
- [ ] UI: not applicable in this brief (no template). The only template of the thread, `admin_home.tmpl`, is dormant; see brief 1593 §7.

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

Write `docs/tasks/1594-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git log --oneline --grep='^1594 step' | tail -10`, then one `git show --stat --format=%h <hash>` per commit).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `register_web_customers.go` (ten routes, every `m.wrap` label equals its path pattern, handler names match the table above) and the compose hunk (only the seven added keys, inside the `ubyhost-go` block, no value written: a key without a value passes the host's variable through only when set).

## Owner steps

These steps are for the Lightsail STAGING server first (the UX gate, brief 1412 is the pattern), then, after the gate passed, for production. The `.env` file is in `/opt/ubyhost/deploy/lightsail/` (see `docs/LIGHTSAIL.md`). Do them only after the whole big PR is merged and deployed.

1. Connect to the server: `ssh ubuntu@<server address>` (staging first). Go to the folder: `cd /opt/ubyhost/deploy/lightsail`. Check that the Go service runs: `docker compose ps | grep -i go`; if no `go` line is running, stop and tell the orchestrator.
2. Check the invoice seller's variables are set in `.env`: `grep -c '^UBYHOST_BILLING_IBAN=\|^UBYHOST_OPERATOR_NAME=\|^UBYHOST_OPERATOR_ICO=' .env` prints `3`. Less than 3: the Python side issues no invoices either; do not continue and tell the orchestrator. Then restart the Go service so it picks up the new compose keys: `docker compose --profile go up -d ubyhost-go`.
3. Write down the current setting: `grep -n '^UBYHOST_GO_PATHS' .env` and copy the whole line into a note.
4. Open the file: `nano .env`. Keep what is inside the double quotes of the `UBYHOST_GO_PATHS=` line and add a space and these three entries, still inside the quotes: `/admin /admin/customers /admin/customers/*`. `/admin` has no star on purpose: it matches only the console home, so every other `/admin/...` page stays on Python. `/admin/customers` (exact) is the list; `/admin/customers/*` (prefix, slashes included) is the detail page and all six POST actions. If the line already holds `/admin/customers` or `/admin/customers/*` (an earlier brief of this area asked for them), add only the entries that are missing and do not repeat one. Do not add `/admin/fakturace`: that belongs to the billing briefs (1555 to 1560). Save with Ctrl+O, Enter, Ctrl+X.
5. Check and apply: `./scripts/caddy-validate.sh` (it must end without an error), then `docker compose up -d caddy`. Open the site and make sure the login page still loads.
6. On staging only, check by hand with a copy of the data: open `/admin`, then one customer; extend a running trial by 1 day; change a status and change it back; set a discount of 10 and then 0 (watch that an unpaid invoice is cancelled and issued again and that the invoice mail is queued); open `/admin/operations` (still Python) from the "System problems" links. Then run the UX gate of rule 10 for `/admin` (`test_layout_lint_browser.py` green, 390, 768 and 1280 px screenshots, design-system checklist) and send the screenshots to the orchestrator. Do not do step 4 on production before the gate passed.
7. The console home shows MRR and ARR one hundredth of their real value (F2 of brief 1593); Python shows the same. Tell the orchestrator if you want that fixed in Go and Python together (one small brief).
8. To go back: `nano .env`, put back the line written down in step 3, run `./scripts/caddy-validate.sh` and `docker compose up -d caddy`.
