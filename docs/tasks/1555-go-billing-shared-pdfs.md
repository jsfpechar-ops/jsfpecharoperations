# 1555: Go subscription billing, part 1: shared gate, catalog, test helpers, invoice PDFs, cancel and resume

Status: review
Depends on: none | Base commit: none (one big PR mode: the branch that is checked out) | Branch: the current one
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** The owner wants one big pull request for the whole Go port. You work on the branch that is checked out now. Never create a branch, never push, never open a PR. After each step that changes a file, commit with the message `1555 step k` (k is the step number) and nothing else in the first line; end the message with the two trailer lines from the session reminder if one is given. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1555 step'` and `git show --stat` on those commits.

## 1. Objective

Add the shared base of the subscription billing web area to `go/internal/web/billing` (route table, CSRF, login and operator gates in Python's order, catalog, test helpers, registration) and four routes: the host's invoice PDF, cancel and resume of a plan, and the operator's invoice PDF. The pages stay dormant until the owner adds the paths to `UBYHOST_GO_PATHS`.

## 2. Context

Rules (AGENTS.md): 1 filing is not touched; 2 privacy: no new personal-data field, no outbound request in this brief; 3 test data is made up (`@example.test`, a test-only secret); 4 no new dependency; 5 plain PostgreSQL through pgx with the Python SQL; 6 light mode, no JavaScript needed; 8 never push to `main`.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. This brief only reads `platform_invoice` (stored PDF bytes), `billing_account` and writes the status and audit rows Python writes.

**All code is pre-written, compiled and tested.** Sidecars are `docs/tasks/1555-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Write nothing outside §3.

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

| Go (`routes.go`) | Python | What it does |
|---|---|---|
| `hostInvoicePDF` | `routes/billing.py` `plan_invoice_pdf` 175-189 | login; the invoice of the host's own workspace as `inline` PDF, else 303 to `/predplatne` (also for a missing id, a storno of another host, an invoice with no owner) |
| `hostCancel` | `plan_cancel` 153-162 | login; with billing on and `billing.Cancel` true: 303 `/predplatne` with `msg` `billing.cancel.done`, else `err` `billing.order.error.state` |
| `hostResume` | `plan_resume` 164-173 | the same with `billing.Resume`, `billing.resume.done` |
| `adminInvoicePDF` | `routes/admin_billing.py` `billing_admin_pdf` 115-125 | operator only; any invoice as PDF, a missing id redirects to `/admin/fakturace` |
| `getInvoiceFile`, `pdfBytes` | `billing_invoices.get` 243-246, `pdf_bytes` 260-272 | always the stored bytes, checked against `pdf_sha256`; missing or changed bytes are a 500 (Python's ValueError), never a re-render |
| `csrf`, `login`, `enter`, `gate` | `security.protect_host_post` (router dependency), `auth.require_login` 516-565, `admin_accounts._require_admin` 716-723 | see the thread note |

Path segment `{invoice_id}.pdf` is a Go wildcard `{file}` (a wildcard must be a whole segment): the handler answers `404 {"detail":"Not Found"}` for a segment without `.pdf` (Python has no such route) and `422` for a non-integer.

**Money and dates:** none computed here. The PDF is the stored document; the test pins the response bytes, the headers (`application/pdf`, `inline; filename="<number>.pdf"`) and the hash check.

**Audit rows:** `billing.Cancel` and `billing.Resume` write `billing_status` (`active->canceling`) with actor `host` replaced by the signed-in username and `actor_user_id` set (test: `host1 active->canceling 1`).

**The catalog.** `i18n_keys.txt` lists every key the six briefs read (`billing.*` groups, `ares.*`, `admin.tab.*` and a few single keys); `i18n.json` is its output, so later briefs add no catalog file.

**Registration.** `register_web_billing.go` hands `billingweb.Routes` to `registerRoutes`; no other file of `go/cmd` changes. `Routes` never touches the pool, so `parseGoKinds` and the registration test can call it with a nil pool.

**Verified by the brief writer** (fresh throwaway worktree of the branch head, sidecars copied exactly as step 1 does, then the same for briefs 1556 to 1560 in order): gofmt empty, `go build ./...` and `go vet ./internal/web/billing/... ./internal/mail/ ./cmd/...` silent, `go test ./internal/web/billing/... ./cmd/ubyhost-web/... ./internal/mail/` ok on PostgreSQL 16 with the 7 named tests PASS and none skipped; `python3 App/scripts/go_host_i18n.py --check` clean. Not run: any Python test, any browser test (the pages are dormant).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/billing/routes.go` | create | `Route`, `call`, `gate`, `enter` / `csrf` / `login` (Python dependency order), flash and redirect helpers, stored-PDF reading, the four handlers |
| `go/internal/web/billing/routes_test.go` | create | tests of the four routes (PDF, cancel, resume, paused host, CSRF) |
| `go/internal/web/billing/testenv_test.go` | create | test helpers: seeded users, accounts and invoices, session cookie, CSRF pair, request helper |
| `go/internal/web/billing/i18n_keys.txt` | create | host keys of all six briefs (one list for the thread) |
| `go/internal/web/billing/i18n.json` | create | generated from host_i18n.py by `App/scripts/go_host_i18n.py` (do not edit) |
| `go/cmd/ubyhost-web/register_web_billing.go` | create | registers `billingweb.Routes` through `registerRoutes` |
| `go/internal/web/billing/table.go` | create | `deps`, `Routes`, `newRoutes`: the route table (4 routes at this stage) |
| `go/internal/web/billing/routes_inventory_test.go` | create | the table holds exactly the routes of the stage, none twice |
| `go/cmd/ubyhost-web/register_web_billing_test.go` | create | each ported route reaches its own pattern, not the catch-all |
| `docs/tasks/1555-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1555-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `ls go/internal/web/billing/admin.go go/internal/web/billing/pyutil.go go/internal/billingjob/invoicer.go go/internal/session/admingate/admingate.go 2>&1 | tail -4` lists the four files.
   - `grep -cF "func Cancel(ctx context.Context, pool *pgxpool.Pool, owner int64, actor string) (bool, error) {" go/internal/billing/order.go | tail -1` prints `1`.
   - `grep -cF "func testPool(t *testing.T) *pgxpool.Pool {" go/internal/web/billing/admin_test.go | tail -1` prints `1`.
   - `ls go/internal/web/billing/routes.go go/cmd/ubyhost-web/register_web_billing.go 2>&1 | tail -2` says "No such file" for both.
   - `find docs/tasks/1555-files -name '*.txt' | wc -l | tail -1` prints `9`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1555-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   ed2bab1928c54d44e7ce14745c3ee7292f924bed77007c5a2a93bfe4afd1b4d0  go/internal/web/billing/routes.go
   ce2ef63e8e7c668809f73343851556298b53b089ca6ab24d915a55476a359147  go/internal/web/billing/routes_test.go
   2d4307e81ae622159af23ed18247cf9e85c20c0d82039e88093ae0d37a4ea82b  go/internal/web/billing/testenv_test.go
   b7293204cadb08af58db66f27939afe3a0a257ff210bdaf267a107dedb79eca5  go/internal/web/billing/i18n_keys.txt
   8a65be01568dbc5eea5bbd27522fb14ef126656e099234bc0ab0371ec3d4f5c7  go/internal/web/billing/i18n.json
   c115cf91a91a7b2df8f8578bf87d5f516a31c5b7b9695dd8bcd97f3ce4796adc  go/cmd/ubyhost-web/register_web_billing.go
   5f2540a26ffb72d9c565978cbdca6c87f5628a1a5ee62e4b9ba8afe2a9923108  go/internal/web/billing/table.go
   ac8b6d305961744f45f0bdd2a9301cf4233b190d15c451725e8fcfc57cea8226  go/internal/web/billing/routes_inventory_test.go
   23f1ff30b3a184f8cc0ee260d65fe3934b529ce82e9e80c0f111ea91c8fdaf44  go/cmd/ubyhost-web/register_web_billing_test.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1555 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/billing internal/mail cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/billing/... ./internal/mail/ ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). No commit (nothing changed).

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1555 && chown postgres /var/tmp/pg1555 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1555/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1555/data -o "-p 55501 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1555" -l /var/tmp/pg1555/log -w start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55501/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55501/postgres go test ./internal/web/billing/... ./cmd/ubyhost-web/... ./internal/mail/ -count=1 2>&1 | tail -30
   ```

   Expected: three lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/billing	<seconds>s`, `ok  ...go/cmd/ubyhost-web	<seconds>s` and `ok  ...go/internal/mail	<seconds>s`. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55501/postgres go test ./internal/web/billing/ ./cmd/ubyhost-web/ ./internal/mail/ -count=1 -v -run '^TestBillingRoutesRegistered$|^TestHostInvoicePDF$|^TestAdminInvoicePDF$|^TestCancelResume$|^TestPausedHostStillPostsToPlanPage$|^TestCSRFRequired$|^TestRoutesNeedNoPool$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -40
   ```

   Expected: one `--- PASS` line for each of the 7 tests (TestBillingRoutesRegistered, TestHostInvoicePDF, TestAdminInvoicePDF, TestCancelResume, TestPausedHostStillPostsToPlanPage, TestCSRFRequired, TestRoutesNeedNoPool), then three `ok` lines; no `--- SKIP`, no `--- FAIL`.

5. Stop and delete the throwaway server (skip if you used a server you did not start):

   ```bash
   su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1555/data -m fast stop' 2>&1 | tail -2; rm -rf /var/tmp/pg1555
   ```

   Expected: `server stopped`.

6. Write the report (§9), set `Status: review` and commit "1555 step 6".

## 5. Do not touch

`go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/internal/billingjob/`, `go/internal/pdf/`, `go/internal/billing/`, `go/cmd/ubyhost-web/main.go`, `registry.go` and every other `register_*.go`, the existing files of `go/internal/web/billing/` that brief 1341 created (`admin.go`, `analytics.go`, `bankimport.go`, `page.go`, `pyutil.go`, `admin_test.go`, `golden_test.go`, `testdata/`), `App/` (no Python file, no `App/tests/conftest.py`), `docs/context/*`, and every file not in §3. AGENTS.md rules that apply: 2 (privacy), 3 (no real data in tests), 4 (no new dependency: `go.mod` and `go.sum` stay as they are), 5 (SQL is plain PostgreSQL through pgx, taken from the Python), 8 (never push to `main`).

## 6. Commands

Exactly the commands of §4 (steps 1, 2, 4, 5). Test-map: no row exists for `go/internal/web/billing`; the coordinator adds one from the report (`go test ./internal/web/billing/... ./cmd/ubyhost-web/...`). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 9 files.
- [ ] Step 2 printed nothing.
- [ ] Step 4 printed three `ok` lines and each of the 7 named tests printed `--- PASS` (none `SKIP`, none `FAIL`).
- [ ] `git log --oneline --grep='^1555 step' | tail -5` lists at least the step 1 commit, and `git show --stat --format=%h <that hash> | tail -15` lists only paths of §3.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed.
- [ ] UI: not applicable in this brief (no template); the pages come in 1556 and 1560. The UX gate (rule 10) runs on staging before the owner adds the paths (brief 1412 is the pattern).

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

Write `docs/tasks/1555-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git log --oneline --grep='^1555 step' | tail -10`, then `git show --stat --format=%h --grep='^1555 step' HEAD~5..HEAD | tail -30` or one `git show --stat <hash>` per commit).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `routes.go`: `csrf` must run before `login` and must parse a multipart body before CSRF (the header token never reads the body); `login` must call `admingate.Require` for every operator route and only mask the method for routes with `gate{open: true}` (the `/predplatne` ones); `hostInvoicePDF` must compare the invoice owner with `h.Workspace.ID` (a host never gets another host's PDF); `pdfBytes` must refuse missing or changed bytes. `table.go` is the list of what is reachable. `i18n.json` is generated: do not review it by hand.

## Owner steps

None: nothing is switched on.
