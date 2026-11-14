# 1557: Go subscription billing, part 3: order and change a plan (POST /predplatne, POST /predplatne/zmena), ARES lookup

Status: todo
Depends on: 1556 | Base commit: none (one big PR mode: the branch that is checked out) | Branch: the current one
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** The owner wants one big pull request for the whole Go port. You work on the branch that is checked out now. Never create a branch, never push, never open a PR. After each step that changes a file, commit with the message `1557 step k` (k is the step number) and nothing else in the first line; end the message with the two trailer lines from the session reminder if one is given. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1557 step'` and `git show --stat` on those commits.

## 1. Objective

Add the host's order form post (with the ARES fill) and the plan change post to `go/internal/web/billing`. With this brief every method of `/predplatne` is served by Go, so the path can be switched as a whole.

## 2. Context

Rules (AGENTS.md): 1 filing is not touched; 2 privacy: no new personal-data field; one outbound request that Python already makes (ARES, IC only), see the PR text; 3 test data is made up (`@example.test`, test-only secrets); 4 no new dependency; 5 plain PostgreSQL through pgx with the Python SQL; 6 light mode, forms work without JavaScript; 8 never push to `main`.

**PR text (hard rule 2):** see the "PR text (outbound request)" paragraph below: one request to ares.gov.cz that Python already makes, the IC only, never made in tests.

**All code is pre-written, compiled and tested.** Sidecars are `docs/tasks/1557-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Write nothing outside §3. Three of them (`table.go`, `routes_inventory_test.go`, `register_web_billing_test.go`) were created by brief 1555 and are replaced by the version that holds the routes of this stage; replace means the plain `cp` of step 1, there is nothing to merge.

**The thread (briefs 1555 to 1560).** Port the two Python route files of subscription billing into the existing Go package `go/internal/web/billing` (package `billingweb`): `App/app/routes/billing.py` (6 routes, the host's plan page `/predplatne`) and `App/app/routes/admin_billing.py` (7 routes, the operator's `/admin/fakturace`). Briefs 1340 and 1341 already ported the engine (`go/internal/billing`: quote, status machine, `Place`, `Change`, `Cancel`, `Resume`) and the read side of the operator page (`AdminPageData`, statement parser, exports as functions); billing job thread ported `go/internal/billingjob` (`Invoicer`: issue, `Storno`, `Send`) and `go/internal/pdf`. This thread adds the handlers, templates, the ARES lookup, the bank-payment write side and the registration `go/cmd/ubyhost-web/register_web_billing.go`. Nothing routes to them until the owner adds the paths to `UBYHOST_GO_PATHS`.

| Brief | Routes (method path, Python function) |
|---|---|
| 1555 | `GET /predplatne/faktury/{id}.pdf` (plan_invoice_pdf), `POST /predplatne/zrusit` (plan_cancel), `POST /predplatne/obnovit` (plan_resume), `GET /admin/fakturace/{id}.pdf` (billing_admin_pdf); shared gate, catalog, test helpers |
| 1556 | `GET /predplatne` (plan_page) with its template |
| 1557 | `POST /predplatne` (plan_order, ARES fill), `POST /predplatne/zmena` (plan_change) |
| 1558 | `POST /admin/fakturace/vypis` (billing_admin_statement), `POST /admin/fakturace/{id}/zaplaceno` (billing_admin_mark_paid); bank-payment write side, `billing_paid` mail |
| 1559 | `POST /admin/fakturace/{id}/storno` (billing_admin_storno), `GET /admin/fakturace/export-vse`, `GET /admin/fakturace/export` |
| 1560 | `GET /admin/fakturace` (billing_admin_page) with its template; the full inventory of 13 routes |

**Order:** 1555, 1556, 1557, 1558, 1559, 1560, each `Depends on` the one before. Three files (`table.go`, `routes_inventory_test.go`, `register_web_billing_test.go`) are named by all six briefs: each brief replaces them with the version for its stage, so the order above is the only valid one.

Caddy routes by path only, and a path in `UBYHOST_GO_PATHS` without a trailing `*` matches that exact path only, so this area needs four entries: `/predplatne`, `/predplatne/*`, `/admin/fakturace` and `/admin/fakturace/*` (`*` at the end is a prefix match, slashes included). Paths with two methods: `/predplatne` (GET 1556, POST 1557). `/admin/fakturace` is GET only. Every other path has one method. The paths become fully served by Go with these briefs: `/predplatne` after 1557, `/predplatne/zmena`, `/predplatne/zrusit`, `/predplatne/obnovit`, `/predplatne/faktury/{id}.pdf`, `/admin/fakturace` after 1560, `/admin/fakturace/vypis`, `/admin/fakturace/{id}/zaplaceno`, `/admin/fakturace/{id}/storno`, `/admin/fakturace/{id}.pdf`, `/admin/fakturace/export`, `/admin/fakturace/export-vse`. The writer could not read the server's `UBYHOST_GO_PATHS` and assumes neither `/predplatne` nor `/admin/fakturace` is in it; if one is, the routes of that prefix go live the moment the brief that adds them deploys.

**Every handler** starts with `d.enter` (or `d.csrf`, the integer check, `d.login` where the path has an integer id) in FastAPI's order: for a POST `hostweb.CSRF` first (header or `_csrf` field, multipart too), then FastAPI's 422 for a non-integer id, then `hostweb.Login` (host routes) or `admingate.Require` (operator routes: login, then 403 `Administrators only.` with no Content-Type). `/predplatne` routes are in Python's `_READ_ONLY_OPEN_PREFIXES`: a paused host may still post there, so those routes call `hostweb.Login` with the method masked to GET (finding F1). The host is `h.Workspace.ID` (Python `access.owner_id`); audit rows carry the signed-in user (Python `db.set_current_actor`).

**Known differences from Python (not fixed here, listed in every report):**

- F1. `hostweb.Login` (read-only) redirects every POST of a paused workspace to `/predplatne?paused=1`, but Python exempts the prefixes `/predplatne`, `/logout`, `/account`, `/settings`, `/exports` and three reservation paths (`auth.py` 507-560). This thread works around it for `/predplatne` only. Other Go areas that use `hostweb.Login` for POSTs under the other exempt paths have the same gap.
- F2. `billingjob.Invoicer.issue` (read-only) writes the audit row `platform_invoice_issued` with `actor_user_id` and `impersonator_user_id` NULL. Python's `db.audit` inside a request fills them from the signed-in user. Affects an order of a paused host (1557), a confirmed upgrade with a supplementary invoice (1557) and an operator storno (1559). The row exists and has the same actor text `system`, owner and detail.
- F3. A wrong method on a Go pattern answers Go's plain-text `405`; Python answers JSON `{"detail":"Method Not Allowed"}`. A non-integer path id answers `422` plain text; Python answers FastAPI's JSON.
- F4. `validation.ico_ok` and path integers accept only ASCII digits in Go; Python also accepts other Unicode digits.
- F5. A multipart body is capped at 11 MiB (hostweb's limit, applied before CSRF). Python has no cap: a statement over 5 MiB is "unreadable" at any size there; Go says "unreadable" up to 11 MiB and answers the CSRF recovery redirect above it.
- F6. `date.today()` is the server-local date in Python; Go uses `billingjob.Today(time.Now())`, the same choice the billing job makes.

**What this brief ports, with the Python lines:**

| Go | Python | What it does |
|---|---|---|
| `hostPlanOrder` | `routes/billing.py` `plan_order` 86-109 | CSRF, login (paused hosts allowed); billing off: 303 `/settings`; `billing.ReadForm` (existing, `billing_order.read_form` 62-90); `do=ares`: fill and re-render with the note (200, errors not shown); validation errors: re-render with the errors, status 400; else `billing.Place`: a ValueError-class refusal (no account, already ordered, whitelabel, no buyer, no plan) -> 303 with `err` `billing.order.error.state`; success -> 303 with `msg` `billing.order.done_now` (paused host, starts today), `done_trial` (date known) or `done_pending`, parameter `date` = `fmt_date(result date)` |
| `aresFill` | `_ares_fill` 112-126 | rate limit (`rate_limit.blocked("ares", owner, 20, 3600)`: `ares.rate_limited`), a bad IC (`ares.failure`, no lookup, no rate row), then record the lookup, look up, `ares.failure` when no data, else fill only the blank buyer fields name, street, city, zip, dic from the answer and say `billing.order.ares_done` |
| `AresClient.Lookup` | `ares.lookup` 126-151, `_map_payload` 98-117, `_street` 73-85 | see the PR text; 24 hour cache (a 404 is cached as unknown, a 5xx or a nameless answer is not), 4 second timeout, `User-Agent: UbyHost` |
| `hostPlanChange` | `plan_change` 128-151 | CSRF, login; billing off, no account, no ordered plan, or status not active/overdue: `err` state; `field`/`value` must be one of the form's choices (plan, billing_interval, addon_ttlock 0/1, addon_whitelabel 0) else `err` state; `billing.Change` (preview when `confirm` is not `1`: render the page with the preview, 200; confirm: 303 `msg` `billing.change.saved_<when>`) |

The order itself (`Place`) and the change (`Change`, `ApplyChange`) are brief 1340's code, pinned to Python by its golden file; this brief only wires them to the page. `Place` for a paused host issues the first invoice through `billingjob.Invoicer` (PDF, number, audit) and `Send` queues the invoice mail only when `UBYHOST_MAIL_BACKEND` is `console` or `ses`.

**PR text (outbound request, hard rule 2):** this brief adds one outbound request that Python already makes: `GET https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/<IC>` (the Czech business register, ARES), made only when a signed-in host presses "Fill from register" on the order form with a valid IC. It sends the IC only (the IC of a company is public register data), the header `User-Agent: UbyHost`, no cookie, no host identity; timeout 4 seconds; an answer is kept in memory for 24 hours. Reason: the host's order form fills the buyer's name, street, city, postcode and DIC from the register, as `App/app/ares.py` does today. The lookup is limited to 20 per host per hour (`rate_limit_event`, scope `ares`). Tests never reach the network: they give the client a stub transport.

**Money and date computations:**

| What | Python | Go | Test and fixed numbers |
|---|---|---|---|
| order period of a paused host | `billing_trial.period_end(day, interval)` | `billing.PeriodEnd` (existing) | `TestOrderWhenPausedStartsNow`: today 2026-11-13, year -> period 2026-11-13 to 2027-11-12 |
| first invoice | `issue_for_period`: Standard, year, 1 apartment, due 14 days | `billingjob.Invoicer` (existing) | same test: `UBY-2026-0001`, `119000` haler, issued 2026-11-13, due 2026-11-27 |
| flash date | `validation.fmt_date(result["date"])` | `fmtDate` | `TestOrderInTrial`: trial end `2026-11-20T10:00:00+00:00` -> `20.11.2026` |
| preview amounts | `_kc` on `period_total_before/after`, `supplementary_czk` | `kcWhole` | `TestPlanChange`: Standard to Max, annual, 1 apartment, period end 2027-03-31, today 2026-11-13: before `1 190`, after `1 760`, 4 whole months, `round(570 * 4 / 12)` = `190` to pay now |
| supplementary invoice | `issue_supplementary` | `Invoicer.IssueSupplementary` (existing) | same test: kind `supplementary`, `19000` haler, period 2026-11-13 to 2027-03-31 |
| zip code, street | `_map_payload`: `psc` 1000 -> `01000`; `12/3a` | `mapAresPayload` | `TestMapAresPayload`: `Hlavní 12/3a`, `01000`, `11000` |
| rate limit | 20 events per 3600 s | `session.RateBlocked` | `TestOrderAresFill`: 1 + 1 + 18 events -> the next lookup is refused without a request |

**Audit rows:** `billing_order` (`standard year`, actor = the signed-in username, `actor_user_id` set), `billing_change` (`plan now`), `billing_status`. `platform_invoice_issued` keeps NULL user ids (finding F2).

**Verified by the brief writer** (fresh throwaway worktree of the branch head; briefs 1555 to 1557 copied in order exactly as their step 1 does): gofmt empty, `go build ./...` and `go vet ./internal/web/billing/... ./internal/mail/ ./cmd/...` silent, `go test ./internal/web/billing/... ./cmd/ubyhost-web/... ./internal/mail/` ok on PostgreSQL 16 with the 9 named tests PASS and none skipped. The mapping, cache and failure cases of the ARES client are covered with a stub transport (no network). Not run: any Python test, any browser test (the pages are dormant).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/billing/ares.go` | create | `AresClient`: `ares.lookup` with its 24 hour cache, the payload mapping (`_map_payload`, `_street`) |
| `go/internal/web/billing/host_actions.go` | create | `hostPlanOrder`, `aresFill`, `hostPlanChange` |
| `go/internal/web/billing/host_actions_test.go` | create | tests: ARES client and mapping (stub transport), order validation, trial order, order of a paused host, ARES fill and rate limit, plan change preview and confirm |
| `go/internal/web/billing/table.go` | replace (created by 1555; this version holds the routes of this stage) | route table: adds `POST /predplatne`, `POST /predplatne/zmena`; `deps` gets the ARES client |
| `go/internal/web/billing/routes_inventory_test.go` | replace (created by 1555; this version holds the routes of this stage) | the table holds exactly the 7 routes of this stage |
| `go/cmd/ubyhost-web/register_web_billing_test.go` | replace (created by 1555; this version holds the routes of this stage) | the 7 routes reach their patterns |
| `docs/tasks/1557-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1557-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git log --oneline --grep='^1556 step' | tail -3` prints at least one line (brief 1556 is in this branch).
   - `ls go/internal/web/billing/routes.go go/internal/web/billing/table.go go/internal/web/billing/testenv_test.go 2>&1 | tail -3` lists the three files of brief 1555.
   - `ls go/internal/web/billing/ares.go go/internal/web/billing/host_actions.go 2>&1 | tail -1` says "No such file" (nothing of this brief is there yet).
   - `grep -cF "func Place(ctx context.Context, pool *pgxpool.Pool, inv Invoicer, owner int64, v OrderValues," go/internal/billing/order.go | tail -1` prints `1`.
   - `grep -cF "func RateBlocked(ctx context.Context, db *pgxpool.Pool, scope, key string, max, window int, now time.Time) (bool, error) {" go/internal/session/loginlink.go | tail -1` prints `1`.
   - `find docs/tasks/1557-files -name '*.txt' | wc -l | tail -1` prints `6`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1557-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   c916c7605012c8e6bfc7083121f8a24de2a9ab388980d0891e9cf3e661429424  go/internal/web/billing/ares.go
   70ae2e6304768a469360ddf2cbd57cc1173d6e8001becb45aadce5cf6fca5f28  go/internal/web/billing/host_actions.go
   ab7348e9384ab42839768da7540c91d3febae02c8ad49e252bdc2d4e7aabb331  go/internal/web/billing/host_actions_test.go
   a33310698b53b49a21b1e6cae5e4edc8d914ca844b1b56241dad9259461a5696  go/internal/web/billing/table.go
   f3256f88ef39d51f5823873a691a9294133a12f222dcf995bd32cda06bd78bbc  go/internal/web/billing/routes_inventory_test.go
   13e41f656fa298db8068631d6c9c9422cfca667842da0798c9cbfb61714a1f1f  go/cmd/ubyhost-web/register_web_billing_test.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1557 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/billing internal/mail cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/billing/... ./internal/mail/ ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). No commit (nothing changed).

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1557 && chown postgres /var/tmp/pg1557 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1557/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1557/data -o "-p 55503 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1557" -l /var/tmp/pg1557/log -w start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55503/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55503/postgres go test ./internal/web/billing/... ./cmd/ubyhost-web/... ./internal/mail/ -count=1 2>&1 | tail -30
   ```

   Expected: three lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/billing	<seconds>s`, `ok  ...go/cmd/ubyhost-web	<seconds>s` and `ok  ...go/internal/mail	<seconds>s`. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55503/postgres go test ./internal/web/billing/ ./cmd/ubyhost-web/ ./internal/mail/ -count=1 -v -run '^TestBillingRoutesRegistered$|^TestMapAresPayload$|^TestAresClient$|^TestOrderValidation$|^TestOrderInTrial$|^TestOrderWhenPausedStartsNow$|^TestOrderAresFill$|^TestPlanChange$|^TestRoutesNeedNoPool$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -40
   ```

   Expected: one `--- PASS` line for each of the 9 tests (TestBillingRoutesRegistered, TestMapAresPayload, TestAresClient, TestOrderValidation, TestOrderInTrial, TestOrderWhenPausedStartsNow, TestOrderAresFill, TestPlanChange, TestRoutesNeedNoPool), then three `ok` lines; no `--- SKIP`, no `--- FAIL`.

5. Stop and delete the throwaway server (skip if you used a server you did not start):

   ```bash
   su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1557/data -m fast stop' 2>&1 | tail -2; rm -rf /var/tmp/pg1557
   ```

   Expected: `server stopped`.

6. Write the report (§9), set `Status: review` and commit "1557 step 6".

## 5. Do not touch

`go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/internal/billingjob/`, `go/internal/pdf/`, `go/internal/billing/`, `go/cmd/ubyhost-web/main.go`, `registry.go` and every other `register_*.go`, the existing files of `go/internal/web/billing/` that brief 1341 created (`admin.go`, `analytics.go`, `bankimport.go`, `page.go`, `pyutil.go`, `admin_test.go`, `golden_test.go`, `testdata/`), `App/` (no Python file, no `App/tests/conftest.py`), `docs/context/*`, and every file not in §3. AGENTS.md rules that apply: 2 (privacy), 3 (no real data in tests), 4 (no new dependency: `go.mod` and `go.sum` stay as they are), 5 (SQL is plain PostgreSQL through pgx, taken from the Python), 8 (never push to `main`).

## 6. Commands

Exactly the commands of §4 (steps 1, 2, 4, 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 6 files.
- [ ] Step 2 printed nothing.
- [ ] Step 4 printed three `ok` lines and each of the 9 named tests printed `--- PASS` (none `SKIP`, none `FAIL`).
- [ ] `git log --oneline --grep='^1557 step' | tail -5` lists at least the step 1 commit, and `git show --stat --format=%h <that hash> | tail -20` lists only paths of §3.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed.
- [ ] UI (rules 7 and 10): the page is dormant (no path routes to it) and the Python-side browser and geometry tests drive the Python app and cannot load a Go-rendered page, so no 390 px screenshot can be taken in this PR. The UX gate runs on staging before the owner adds the path (brief 1412 is the pattern); the report says so.

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

Write `docs/tasks/1557-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git log --oneline --grep='^1557 step' | tail -10`, then `git show --stat --format=%h --grep='^1557 step' HEAD~5..HEAD | tail -30` or one `git show --stat <hash>` per commit).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `host_actions.go` (`hostPlanOrder`: the order of branches, ARES first, then errors with 400, then `Place`; `valueError` decides which failures are the state flash and which a 500; `hostPlanChange`: the `changeValues` whitelist and the `addon_` integer conversion; the acting user in `c.ctx()`) and `ares.go` (the URL, the header, the timeout and what is cached). `ares.go` is the only new outbound request: check the host name and that only the IC is in the URL.

## Owner steps

None here (dormant). Before the owner adds `/predplatne` to `UBYHOST_GO_PATHS` the UX gate of rule 10 runs on staging for the page in its four states, and the owner confirms that the container may reach `ares.gov.cz` (Python's container already does).
