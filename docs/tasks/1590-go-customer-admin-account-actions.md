# 1590: Go customer admin, part 1: the operator's account actions (status, extend trial, resend verification)

Status: review
Depends on: 1364 (the customer admin pages 1360 to 1364 are in the branch) | Base commit: none (one big PR mode: the branch that is checked out) | Branch: the current one
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (operator pages, billing and mail; no filing, no guest data)

> **One big PR mode.** The owner wants one big pull request for the whole Go port. You work on the branch that is checked out now. Never create a branch, never push, never open a PR, never call an `mcp__` tool. After each step that changes a file, commit with the message `1590 step k` (k is the step number) and nothing else in the first line; end the message with the two trailer lines from the session reminder if one is given. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1590 step'` and `git show --stat` on those commits.

## 1. Objective

Add the three operator actions that need no invoice to `go/internal/web/customers`: `POST /admin/customers/{user_id}/stav` (change the billing status through the state machine), `/prodlouzit` (extend a running trial) and `/overit-znovu` (resend the verification link of a pending sign-up), together with the guards every operator action of this area shares. They change what a customer owes or can do, so each branch is pinned by a test.

## 2. Context

Rules (AGENTS.md): 1 filing is not touched; 2 privacy: no new personal-data field and no new outbound request; 3 test data is made up (`@example.test`, test-only secrets); 4 no new dependency; 5 plain PostgreSQL through pgx with the Python SQL; 6 light mode, forms work without JavaScript; 8 never push to `main`; 11 Go first.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The resend queues one `signup_verify` mail through the existing `email_outbox` (the engine `signup.ResendOperator` does that, as Python's `signup.resend_operator` does).

**All code is pre-written, compiled and tested.** Sidecars are `docs/tasks/1590-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Write nothing outside §3. Two of them (`templates/i18n.json`, `templates/i18n_keys.txt`) were created by brief 1361 and extended by 1364; this version adds the keys of this stage and replaces them: replace means the plain `cp` of step 1, there is nothing to merge. The catalog `i18n.json` is generated from `i18n_keys.txt` by `App/scripts/go_host_i18n.py`; the sidecar pair is already in step, and `--check` proves it.

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
- F4. Audit actor of `Cancel` and `Resume` (status `canceling`, and `active` from `canceling`): Python's `billing_order.cancel` and `resume` take no actor and write the row with the host actor; Go passes `billing.HostActor` as the engine does, and the signed-in operator still reaches `actor_user_id` through the context (as `db.audit` does). Every other status move uses the actor text `operator:<username>`.

**What this brief ports, with the Python lines (`App/app/routes/admin_customers.py`):**

| Go | Python | What it does |
|---|---|---|
| `actionHandler` (`actions.go`) | `router = APIRouter(dependencies=[Depends(security.protect_host_post)])`, `_require_admin` | the guards above; the multipart/urlencoded form readers `formValue`, `formMap` (the last value of a field, as Starlette's `FormData.get`) |
| `StatusHandler` | `customer_status` 241-262 | `status` stripped; not one of `trial_pending trialing active overdue canceling paused`: `err` `billing.admin.status.bad`. `canceling` -> `billing.Cancel`; `active` -> `billing.Resume` when the account is `canceling`, else `billing.SetStatus`; the rest `SetStatus`. Refused (the state machine says no): `err` `...refused`, nothing written. Else the month snapshot is rewritten (`billing.WriteMonthSnapshot`) and `msg` `...done` |
| `ExtendTrialHandler` | `customer_extend_trial` 184-202 | `days` through `pyInt`; unreadable or the engine's `bad_days`: `err` `billing.admin.extend.bad_days`; no running trial (empty end): `err` `...not_trialing`; else `msg` `billing.admin.extend.done` with `days` |
| `ResendVerificationHandler` | `customer_resend_verification` 228-238 | `signup.ResendOperator`: true `msg` `customers.ops.verify_sent`, false `err` `customers.ops.verify_refused` |

**Numbers and dates (tests with fixed values):** the trial end moves by `days` days, 1 to 365 (the engine's rule, pinned in `TestExtendTrialAction` with a fixed trial end); `TestPyIntAndClamp` pins `int()` of ` 7 `, `+7`, `1_0`, `_1`, `1__0`, `7.0`, an empty string and a value of 5000 digits.

**Verified by the brief writer** (fresh throwaway worktree of the branch head; the sidecars of 1590 copied exactly as step 1 does): gofmt empty; `go build ./...` and `go vet ./internal/web/customers/... ./cmd/...` silent; `go test ./internal/web/customers/... ./cmd/ubyhost-web/...` ok on PostgreSQL 16 (the named tests PASS, 0 skipped); `go_host_i18n.py --check` exit 0. The status machine, the trial extension and the guards were read against `admin_customers.py` 184-262 and `billing_order`; no divergence other than F1 to F4. Not run: any Python test, any browser test (the actions have no page).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/customers/actions.go` | create | `actionCtx`, `actionHandler` (CSRF, integer check, admin gate, audit actor), `formValue`, `formMap`, `pyInt`, `clampInt`, `valueError` |
| `go/internal/web/customers/actions_account.go` | create | `StatusHandler`, `ExtendTrialHandler`, `ResendVerificationHandler` |
| `go/internal/web/customers/actions_test.go` | create | tests: guards, status machine, trial extension, resend, `int()` rules |
| `go/internal/web/customers/templates/i18n.json` | replace (created by 1361; version of this stage) | adds the flash strings of the three actions |
| `go/internal/web/customers/templates/i18n_keys.txt` | replace (created by 1361; version of this stage) | the key list that generates `i18n.json` |
| `docs/tasks/1590-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1590-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `grep -cF "func DetailHandler(" go/internal/web/customers/detail.go | tail -1` prints `1` (briefs 1360 to 1364 are in this branch; `git log --oneline --grep='^1364 step' | tail -3` prints at least one line when the branch history is complete).
   - `ls go/internal/web/customers/actions.go 2>&1 | tail -1` says "No such file" (nothing of this brief is there yet).
   - `grep -cF "func requireAdmin(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, at time.Time) (*session.Host, bool) {" go/internal/web/customers/handlers.go | tail -1` prints `1`.
   - `grep -cF "func stamp(t time.Time) string {" go/internal/web/customers/handlers.go | tail -1` prints `1`.
   - `grep -cF "func pyStrip(s string) string" go/internal/web/customers/query.go | tail -1` prints `1`.
   - `grep -cF "func ResendOperator(ctx context.Context, pool *pgxpool.Pool, userID int64, actor string, getenv func(string) string, now time.Time) (bool, error) {" go/internal/signup/register.go | tail -1` prints `1`.
   - `grep -cF "func WriteMonthSnapshot(ctx context.Context, pool *pgxpool.Pool, month, now string) (int, error) {" go/internal/billing/snapshot.go | tail -1` prints `1`.
   - `grep -cF "func ExtendTrial(ctx context.Context, pool *pgxpool.Pool, owner int64, days int, actor string," go/internal/billing/order.go | tail -1` prints `1`.
   - i18n catalog is in step with its key list (needs Python with FastAPI; use `App/.venv/bin/python` if that file exists, else `python3`; if the import fails write "CI only" in the report and go on): from the repo root `PY=python3; [ -x App/.venv/bin/python ] && PY=App/.venv/bin/python; $PY App/scripts/go_host_i18n.py --check 2>&1 | tail -5` prints nothing and exits 0.
   - `find docs/tasks/1590-files -name '*.txt' | wc -l | tail -1` prints `5`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1590-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   cc3ab8bb57eb94a6b0372f1beea01c1496df1957bd84b64beeae22adbb794889  go/internal/web/customers/actions.go
   c07a6a3829ae29ede1265cca2a4dbc151643c00a5ae95dc5e8fe0107a638aa89  go/internal/web/customers/actions_account.go
   c72ef09489ddb2eaf942cdd238aae88f5c544744459b4d4efa3ca634da85faf2  go/internal/web/customers/actions_test.go
   875df9bfe6a2775ad8a16d0d977ef4baee62c8b52ba1c3cae5300b58b3024d31  go/internal/web/customers/templates/i18n.json
   4c41b9906f94064ac7f0e685a3604d3984fe652862c5b927152d278ee91fbc3e  go/internal/web/customers/templates/i18n_keys.txt
   EOF
   ```

   Every line must end with `: OK`. Then commit "1590 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/customers cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/customers/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). No commit (nothing changed).

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1590 && chown postgres /var/tmp/pg1590 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1590/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1590/data -o "-p 55590 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1590" -l /var/tmp/pg1590/log -w start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55590/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55590/postgres go test ./internal/web/customers/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: two lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/customers	<seconds>s` and `ok  	...go/cmd/ubyhost-web	<seconds>s`. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55590/postgres go test ./internal/web/customers/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestAccountActionGuards$|^TestStatusAction$|^TestExtendTrialAction$|^TestResendVerificationAction$|^TestPyIntAndClamp$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -40
   ```

   Expected: one `--- PASS` line for each of the 5 tests (TestAccountActionGuards, TestStatusAction, TestExtendTrialAction, TestResendVerificationAction, TestPyIntAndClamp), then `ok` lines; no `--- SKIP`, no `--- FAIL`. Then count skips in the whole run and write the number in the report: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55590/postgres go test ./internal/web/customers/ ./cmd/ubyhost-web/ -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` must print `0`.

5. Stop and delete the throwaway server (skip if you used a server you did not start):

   ```bash
   su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1590/data -m fast stop' 2>&1 | tail -2; rm -rf /var/tmp/pg1590
   ```

   Expected: `server stopped`.

6. Write the report (§9), set `Status: review` and commit "1590 step 6".

## 5. Do not touch

`go/internal/hostweb/`, `go/internal/session/`, `go/internal/billing/`, `go/internal/billingjob/`, `go/internal/signup/`, `go/internal/web/billing/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `registry.go` and every `register_*.go` that is not named in §3, the existing files of `go/internal/web/customers/` that briefs 1361 to 1364 created (`detail.go`, `handlers.go`, `handlers_test.go`, `pages.go`, `pages_test.go`, `query.go`, `query_test.go`, `testdata/`, the existing templates), `App/` (no Python file, no `App/tests/conftest.py`), `docs/context/*`, and every file not in §3. AGENTS.md rules that apply: 2 (privacy), 3 (no real data in tests), 4 (no new dependency: `go.mod` and `go.sum` stay as they are), 5 (SQL is plain PostgreSQL through pgx, taken from the Python), 8 (never push to `main`), 11 (Go first: no file under `App/app/` is named in §3, so no exception of go-first applies).

## 6. Commands

Exactly the commands of §4 (steps 1, 2, 4, 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 5 files.
- [ ] Step 2 printed nothing.
- [ ] Step 4 printed the `ok` lines, each of the 5 named tests printed `--- PASS`, and the skip count is `0` (none `SKIP`, none `FAIL`).
- [ ] `git log --oneline --grep='^1590 step' | tail -5` lists at least the step 1 commit, and `git show --stat --format=%h <that hash> | tail -20` lists only paths of §3.
- [ ] `python3`/`go_host_i18n.py --check` (step 0 or the end of step 4) exited 0, or the report says "CI only". No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed. The handlers are not registered yet (brief 1594).
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

Write `docs/tasks/1590-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git log --oneline --grep='^1590 step' | tail -10`, then one `git show --stat --format=%h <hash>` per commit).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `actions_account.go` (the status switch: that `canceling` and the return from `canceling` use `Cancel` and `Resume`, never a raw `SetStatus`; that a refused move writes nothing and answers `err`; the trial `days` range) and of `actions.go` (guard order: CSRF, then the integer check, then the admin gate; `actor()` is `operator:<username>`; the audit context carries the operator). Tier A does not apply; this thread has no filing, deletion or auth change.

## Owner steps

None here (routes dormant, not even registered until brief 1594). The path switch is in the owner steps of brief 1594.
