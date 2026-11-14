# 1591: Go customer admin, part 2: the operator's plan and price actions (discount, plan change, assign plan)

Status: todo
Depends on: 1590 | Base commit: none (one big PR mode: the branch that is checked out) | Branch: the current one
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (operator pages, billing and mail; no filing, no guest data)

> **One big PR mode.** The owner wants one big pull request for the whole Go port. You work on the branch that is checked out now. Never create a branch, never push, never open a PR, never call an `mcp__` tool. After each step that changes a file, commit with the message `1591 step k` (k is the step number) and nothing else in the first line; end the message with the two trailer lines from the session reminder if one is given. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1591 step'` and `git show --stat` on those commits.

## 1. Objective

Add the three operator actions that change a customer's price or plan and can issue, cancel and mail an invoice: `POST /admin/customers/{user_id}/sleva` (discount, unpaid invoices are reissued), `/plan` (one plan change, same engine as the host's page) and `/priradit` (first plan for a legacy host). These move money, so every amount path is pinned with fixed numbers.

## 2. Context

Rules (AGENTS.md): 1 filing is not touched; 2 privacy: no new personal-data field and no new outbound request; 3 test data is made up (`@example.test`, test-only secrets); 4 no new dependency; 5 plain PostgreSQL through pgx with the Python SQL; 6 light mode, forms work without JavaScript; 8 never push to `main`; 11 Go first.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. Invoices are issued by `billingjob.Invoicer` and the invoice mail is queued in the existing `email_outbox`; nothing leaves the server in this brief. Issuing an invoice inside the Go service reads the seller's details from environment variables, which the Go container does not receive yet: brief 1594 adds them to the compose file (see its step 2).

**All code is pre-written, compiled and tested.** Sidecars are `docs/tasks/1591-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Write nothing outside §3. Two of them (`templates/i18n.json`, `templates/i18n_keys.txt`) were replaced by 1590; this version holds the keys of both stages and replaces them again: replace means the plain `cp` of step 1, there is nothing to merge.

**The thread (briefs 1590 to 1594).** Port the 7 routes of `App/app/routes/admin_customers.py` that Go does not serve yet (the file has 10 routes; briefs 1361, 1363 and 1364 ported `GET /admin/customers`, `GET /admin/customers/{user_id}` and `POST /admin/customers/{user_id}/aktivovat`; `GET /admin/funnel` is from brief 1361 and is not in that file) into the existing package `go/internal/web/customers` (package `customers`). Nothing routes to them until the owner adds the paths to `UBYHOST_GO_PATHS`.

| Brief | Routes (method path, Python function) | New files |
|---|---|---|
| 1590 | `POST /admin/customers/{user_id}/stav` (customer_status), `/prodlouzit` (customer_extend_trial), `/overit-znovu` (customer_resend_verification); the shared action guards | `actions.go`, `actions_account.go` |
| 1591 | `POST /admin/customers/{user_id}/sleva` (customer_discount), `/plan` (customer_plan), `/priradit` (customer_assign_plan) | `actions_billing.go`, `actions_invoicer.go` |
| 1592 | the six "System problems" counts of `admin_ops.overview()` (no route) | `ops.go` |
| 1593 | `GET /admin` (admin_home) with its template | `home.go`, `templates/admin_home.tmpl` |
| 1594 | registers the 7 routes in `go/cmd/ubyhost-web` and pins the route inventory (all 10 routes of the file) | `register_web_customers_test.go` |

**Order:** 1590, 1591, 1592, 1593, 1594, each `Depends on` the one before. The files `templates/i18n.json` and `templates/i18n_keys.txt` are named by 1590, 1591 and 1593: each brief replaces both with the version for its stage (1593's is the full catalog), so this order is the only valid one. Briefs 1360 to 1364 (customer admin list, detail, toggle) must already be in the branch; the billing engine (`go/internal/billing`, brief 1340), `go/internal/billingjob`, `go/internal/signup` and `billingweb.OperatorQueue` / `GetPortfolio` (brief 1341, `go/internal/web/billing/analytics.go`) are older still. The billing page thread 1555 to 1560 is not needed: 1593 reads only `OperatorQueue` and `GetPortfolio`, which exist since 1341.

**Every action handler** runs the same guards in Python's order: `hostweb.CSRF` first (header `X-CSRF-Token` or `_csrf` field; a failure answers the CSRF recovery redirect), then FastAPI's 422 for a `user_id` that is not an integer, then `requireAdmin` (signed out: 303 to `/login?next=<path>`; a host: 403 `Administrators only.`). The engines in `go/internal/billing` and `go/internal/signup` write the rows, the audit entries and the queued mail; the handler only reads the form, picks the flash and redirects to `/admin/customers/<id>` with `msg=` or `err=` (translated through the page catalog). The audit rows carry the signed-in operator (Python `db.set_current_actor`): `billing.WithAuditActor` and `signup.WithAuditActor` put the account in the context, with the impersonator when the operator is impersonating.

**Known differences from Python (not fixed here, listed in every report):**

- F1. A wrong method on a Go pattern answers Go's plain-text `405`; Python answers JSON `{"detail":"Method Not Allowed"}`. A non-integer `user_id` answers `422` plain text; Python answers FastAPI's JSON.
- F2. Python's `int(text)` also reads non-ASCII digits (for example Arabic-Indic); Go's `pyInt` accepts only ASCII digits, an optional sign and single underscores between digits, up to 4300 digits like Python. A value beyond plus or minus 2^40 is clamped (`clampInt`) before it reaches an engine, which refuses it as Python does.
- F3. `date.today()` is the server date in Python (a UTC container); Go uses the UTC date of the request time (`actionCtx.today`).
- F4. `billingjob.Invoicer` (read-only here) writes the audit row `platform_invoice_issued` with `actor_user_id` and `impersonator_user_id` NULL, as the billing job does; Python's `db.audit` inside a request fills both from the signed-in operator. `actions_invoicer.go` wraps the invoicer and sets both on the rows that one call just wrote (rows above the audit high-water mark of that call, action `platform_invoice_issued`, actor `system`, user NULL, the same owner). Two requests that issue invoices for the same customer at the same instant could in theory stamp each other's row with the operator; both are operator actions, so the effect is nil. Once `billingjob` reads the actor from the context the update finds nothing to do and the wrapper can go.
- F5. The plan change passes `billing.HostActor` as the engine's actor, as Python's `billing_order.change` does for the status rows it writes; the invoice and snapshot rows are as Python's.

**What this brief ports, with the Python lines (`App/app/routes/admin_customers.py`):**

| Go | Python | What it does |
|---|---|---|
| `DiscountHandler` | `customer_discount` 111-132 | `percent` (empty means `0`) through `pyInt`: not an integer `err` `billing.admin.discount.bad_percent`; `reason` stripped and cut to 200 characters; `billing.ApplyDiscount`; a refusal of the engine (a `ValueError` in Python) `err` `billing.admin.discount.<code>` (codes `discount_out_of_range`, `no_plan`, `reason_missing`); done `msg` `...done`, or `...done_reissued` when an unpaid invoice was cancelled and issued again |
| `PlanChangeHandler` | `customer_plan` 135-162 | `field` stripped, not in `billing.ChangeColumns`: `err` `billing.admin.plan.bad_field`; `apartments`, `addon_ttlock`, `addon_whitelabel` read through `pyInt` (not an integer `err` `...bad_value`), the two add-ons folded to 0 or 1; `plan` and `billing_interval` kept as typed; `billing.Change` with `confirm` true and today; an engine refusal `err` `...refused`; else the month snapshot is rewritten and `msg` `...done` |
| `AssignPlanHandler` | `customer_assign_plan` 165-181 | `billing.ReadForm` over all fields; any form error `err` `billing.admin.assign.error`; `billing.PlaceForOperator` (starts today, first invoice at once); refusal `err` `...refused`; else snapshot and `msg` `...done` |
| `requestInvoicer` | `db.set_current_actor` inside the request | see F4 |

**Money (every one has a test with fixed numbers):** `TestDiscountAction` pins the percent range 0 to 100 (`-1`, `101`, ` 100 ` accepted, `abc` refused), the 200-character reason cut and the empty reason; `TestDiscountReissuesUnpaidInvoice` pins that an unpaid invoice is stornoed and issued again with the discounted total; `TestPlanChangeAction` pins an apartment rise on a monthly and an annual plan (the annual rise issues a supplementary invoice) and the add-on fold; `TestAssignPlanAction` pins the first invoice of a placed plan and the refusal for a customer who already has one. The amounts come from `billing.Quote`, which has its own tests (brief 1340).

**Verified by the brief writer** (fresh throwaway worktree of the branch head; briefs 1590 and 1591 copied in order exactly as their step 1 does): gofmt empty; `go build ./...` and `go vet ./internal/web/customers/... ./cmd/...` silent; `go test ./internal/web/customers/... ./cmd/ubyhost-web/...` ok on PostgreSQL 16 with the five named tests PASS and 0 skipped; `go_host_i18n.py --check` exit 0 (with FastAPI stubbed in the writer's environment). The discount, the plan field handling and the assign path were read against `admin_customers.py` 111-181 and `billing_order`; no divergence other than F1 to F5. Not run: any Python test, any browser test.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/customers/actions_billing.go` | create | `DiscountHandler`, `PlanChangeHandler`, `AssignPlanHandler` |
| `go/internal/web/customers/actions_invoicer.go` | create | `requestInvoicer`: stamps the operator on the audit rows of the invoices one call issues (F4) |
| `go/internal/web/customers/actions_billing_test.go` | create | tests: guards, discount range and reissue, plan change, assign plan |
| `go/internal/web/customers/templates/i18n.json` | replace (created by 1361, replaced by 1590; version of this stage) | adds the flash strings of the three actions |
| `go/internal/web/customers/templates/i18n_keys.txt` | replace (created by 1361, replaced by 1590; version of this stage) | the key list that generates `i18n.json` |
| `docs/tasks/1591-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1591-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git log --oneline --grep='^1590 step' | tail -3` prints at least one line (brief 1590 is in this branch).
   - `ls go/internal/web/customers/actions.go go/internal/web/customers/actions_account.go 2>&1 | tail -2` lists both files of brief 1590.
   - `grep -cF "func actionHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, run actionFunc) http.HandlerFunc {" go/internal/web/customers/actions.go | tail -1` prints `1`.
   - `ls go/internal/web/customers/actions_billing.go 2>&1 | tail -1` says "No such file".
   - `grep -cF "func ApplyDiscount(ctx context.Context, pool *pgxpool.Pool, inv Invoicer, owner int64, percent int," go/internal/billing/engine.go | tail -1` prints `1`.
   - `grep -cF "func Change(ctx context.Context, pool *pgxpool.Pool, inv Invoicer, owner int64, field string, value any," go/internal/billing/order.go | tail -1` prints `1`.
   - `grep -cF "func PlaceForOperator(ctx context.Context, pool *pgxpool.Pool, inv Invoicer, owner int64, v OrderValues," go/internal/billing/order.go | tail -1` prints `1`.
   - `grep -cF "func ReadForm(form map[string]string) (OrderValues, map[string]string) {" go/internal/billing/order.go | tail -1` prints `1`.
   - `grep -cF "type Invoicer struct" go/internal/billingjob/*.go | grep -v ':0' | tail -1` prints one line with `:1`.
   - i18n catalog is in step with its key list (needs Python with FastAPI; use `App/.venv/bin/python` if that file exists, else `python3`; if the import fails write "CI only" in the report and go on): from the repo root `PY=python3; [ -x App/.venv/bin/python ] && PY=App/.venv/bin/python; $PY App/scripts/go_host_i18n.py --check 2>&1 | tail -5` prints nothing and exits 0.
   - `find docs/tasks/1591-files -name '*.txt' | wc -l | tail -1` prints `5`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1591-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   7cfd5f3ea0db8babece157bb53969f8d167a0013e33a228b70d8b8e0e4db5d17  go/internal/web/customers/actions_billing.go
   8ad71bdc87747c12f059e582ba4707ded85708090030399fc4d6618d8e7655a6  go/internal/web/customers/actions_billing_test.go
   c56fbd6d6709e88a6cfb93e250916696934e84ae96c8f81317df9f3e50c2df30  go/internal/web/customers/actions_invoicer.go
   bf9686d9e4ac5784d99ccb0b743bdafaba40e64c81a29ef22c1c248759102d69  go/internal/web/customers/templates/i18n.json
   d1b1641bda836e650e72940ac16e3e4fa2520b1517e02b9d9acec5dfd2781fc1  go/internal/web/customers/templates/i18n_keys.txt
   EOF
   ```

   Every line must end with `: OK`. Then commit "1591 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/customers cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/customers/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). No commit (nothing changed).

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1591 && chown postgres /var/tmp/pg1591 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1591/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1591/data -o "-p 55591 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1591" -l /var/tmp/pg1591/log -w start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55591/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55591/postgres go test ./internal/web/customers/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: two lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/customers	<seconds>s` and `ok  	...go/cmd/ubyhost-web	<seconds>s`. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55591/postgres go test ./internal/web/customers/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestBillingActionGuards$|^TestDiscountAction$|^TestDiscountReissuesUnpaidInvoice$|^TestPlanChangeAction$|^TestAssignPlanAction$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -40
   ```

   Expected: one `--- PASS` line for each of the 5 tests (TestBillingActionGuards, TestDiscountAction, TestDiscountReissuesUnpaidInvoice, TestPlanChangeAction, TestAssignPlanAction), then `ok` lines; no `--- SKIP`, no `--- FAIL`. Then count skips in the whole run and write the number in the report: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55591/postgres go test ./internal/web/customers/ ./cmd/ubyhost-web/ -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` must print `0`.

5. Stop and delete the throwaway server (skip if you used a server you did not start):

   ```bash
   su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1591/data -m fast stop' 2>&1 | tail -2; rm -rf /var/tmp/pg1591
   ```

   Expected: `server stopped`.

6. Write the report (§9), set `Status: review` and commit "1591 step 6".

## 5. Do not touch

`go/internal/hostweb/`, `go/internal/session/`, `go/internal/billing/`, `go/internal/billingjob/`, `go/internal/signup/`, `go/internal/web/billing/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `registry.go` and every `register_*.go` that is not named in §3, the existing files of `go/internal/web/customers/` that briefs 1361 to 1364 created (`detail.go`, `handlers.go`, `handlers_test.go`, `pages.go`, `pages_test.go`, `query.go`, `query_test.go`, `testdata/`, the existing templates), `App/` (no Python file, no `App/tests/conftest.py`), `docs/context/*`, and every file not in §3. AGENTS.md rules that apply: 2 (privacy), 3 (no real data in tests), 4 (no new dependency: `go.mod` and `go.sum` stay as they are), 5 (SQL is plain PostgreSQL through pgx, taken from the Python), 8 (never push to `main`), 11 (Go first: no file under `App/app/` is named in §3, so no exception of go-first applies).

## 6. Commands

Exactly the commands of §4 (steps 1, 2, 4, 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 5 files.
- [ ] Step 2 printed nothing.
- [ ] Step 4 printed the `ok` lines, each of the 5 named tests printed `--- PASS`, and the skip count is `0` (none `SKIP`, none `FAIL`).
- [ ] `git log --oneline --grep='^1591 step' | tail -5` lists at least the step 1 commit, and `git show --stat --format=%h <that hash> | tail -20` lists only paths of §3.
- [ ] `go_host_i18n.py --check` exited 0, or the report says "CI only". No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed. The handlers are not registered yet (brief 1594).
- [ ] UI: not applicable (no template or page in this brief).

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

Write `docs/tasks/1591-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git log --oneline --grep='^1591 step' | tail -10`, then one `git show --stat --format=%h <hash>` per commit).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `actions_billing.go` (money and state: the percent parse and range, the 200-character reason cut, that the plan change passes `confirm` true like Python, the add-on fold to 0 or 1, the refusal mapping so that only engine refusals become a flash and any other error is a 500) and `actions_invoicer.go` (the audit `UPDATE` is bounded by the high-water mark, the action, actor `system` and the owner, so it cannot touch an older row).

## Owner steps

None here (routes dormant, not registered until brief 1594). Before the owner switches `/admin/customers/*` to Go (brief 1594 owner steps), he should try one discount and one plan change on staging against a copy of the data, because they issue real invoices.
