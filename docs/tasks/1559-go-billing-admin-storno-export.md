# 1559: Go subscription billing, part 5: operator storno and the two zip exports

Status: review
Depends on: 1558 | Base commit: none (one big PR mode: the branch that is checked out) | Branch: the current one
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** The owner wants one big pull request for the whole Go port. You work on the branch that is checked out now. Never create a branch, never push, never open a PR. After each step that changes a file, commit with the message `1559 step k` (k is the step number) and nothing else in the first line; end the message with the two trailer lines from the session reminder if one is given. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1559 step'` and `git show --stat` on those commits.

## 1. Objective

Add the operator's storno of an unpaid invoice and the two zip downloads (the month's invoices with their PDFs, and the bulk CSV export) to `go/internal/web/billing`. The storno issues a negative document and voids the invoice, so its refusals and amounts are pinned with fixed numbers.

## 2. Context

Rules (AGENTS.md): 1 filing is not touched; 2 privacy: no new personal-data field and no outbound request; the exports contain the same columns Python exports; 3 test data is made up (`@example.test`, test-only secrets); 4 no new dependency; 5 plain PostgreSQL through pgx with the Python SQL; 6 light mode, forms work without JavaScript; 8 never push to `main`.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The exports contain the same columns as Python's, for an operator only.

**All code is pre-written, compiled and tested.** Sidecars are `docs/tasks/1559-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Write nothing outside §3. Three of them (`table.go`, `routes_inventory_test.go`, `register_web_billing_test.go`) were created by brief 1555 and are replaced by the version that holds the routes of this stage; replace means the plain `cp` of step 1, there is nothing to merge.

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
| `adminStorno` | `routes/admin_billing.py` `billing_admin_storno` 99-113 | operator; `reason` stripped and cut to 200 characters; empty: `err` `billing.admin.storno.reason_missing`; `billingjob.Invoicer.Storno` (existing: `billing_invoices.storno` 197-217): a refusal -> `err` `billing.admin.storno.refused_<code>` with the Python messages `not_an_invoice`, `already_voided`, `paid`, `workspace_deleted`, `buyer_missing`; success `msg` `billing.admin.storno.done`. Not mailed (Python's comment: the invoice mail asks for payment) |
| `adminExportAll` | `billing_admin_export_all` 127-134 | operator; `ExportAllZip` (existing, three CSV files, no PDF) as `application/zip`, `attachment; filename="ubyhost-billing-all.zip"` |
| `adminExport`, `ExportZip` | `billing_admin_export` 136-143, `billing_admin.export_zip` 103-110 | operator; `mesic` through `MonthOrCurrent` (a bad month is the current one); `faktury-<month>.csv` (existing `ExportCSV`) plus `pdf/<number>.pdf` for every document of the month, exactly as stored (hash-checked; a document with no stored PDF is a 500); `attachment; filename="ubyhost-faktury-<month>.zip"` |

**Money and date computations:**

| What | Python | Go | Test and fixed numbers |
|---|---|---|---|
| storno amounts | `-(gross_haler // 100)` per item, issue date today, due date = issue date | `Invoicer.Storno` (existing) | `TestStorno`: invoice of `119000` haler -> storno `-119000`, corrects the invoice, issued and due `2026-11-13`; the original is `voided = 1` |
| reason length | `strip()[:200]` | runes, 200 | `TestStorno`: 250 characters -> stored reason of 200 |
| month | `month_or_current` | `MonthOrCurrent` | `TestExports`: no `mesic` at the test clock 2026-11-13 -> `2026-11`; `2026-10` selects October; `nope` -> `2026-11` |
| CSV | `export_csv` (existing, golden-pinned by 1341) | `ExportCSV` | `TestExports`: BOM, header `Číslo;Druh;`, row `UBY-2026-0031;faktura;;2026-11-01;` |

**Audit rows:** the storno writes `platform_invoice_issued` (`<number> storno`, actor `system`, NULL user ids: finding F2). No other row.

**Outbound requests:** none.

**Verified by the brief writer** (fresh throwaway worktree of the branch head; briefs 1555 to 1559 copied in order exactly as their step 1 does): gofmt empty, `go build ./...` and `go vet ./internal/web/billing/... ./internal/mail/ ./cmd/...` silent, `go test ./internal/web/billing/... ./cmd/ubyhost-web/... ./internal/mail/` ok on PostgreSQL 16 with the 4 named tests PASS and none skipped. Not run: any Python test, any browser test (the pages are dormant).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/billing/admin_more.go` | create | `adminStorno`, `adminExportAll`, `adminExport`, `ExportZip` |
| `go/internal/web/billing/admin_more_test.go` | create | tests: storno with fixed numbers and every refusal, both exports |
| `go/internal/web/billing/table.go` | replace (created by 1555; this version holds the routes of this stage) | route table: adds storno and the two exports |
| `go/internal/web/billing/routes_inventory_test.go` | replace (created by 1555; this version holds the routes of this stage) | the table holds exactly the 12 routes of this stage |
| `go/cmd/ubyhost-web/register_web_billing_test.go` | replace (created by 1555; this version holds the routes of this stage) | the 12 routes reach their patterns |
| `docs/tasks/1559-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1559-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git log --oneline --grep='^1558 step' | tail -3` prints at least one line (brief 1558 is in this branch).
   - `ls go/internal/web/billing/routes.go go/internal/web/billing/table.go go/internal/web/billing/testenv_test.go 2>&1 | tail -3` lists the three files of brief 1555.
   - `ls go/internal/web/billing/admin_more.go 2>&1 | tail -1` says "No such file" (nothing of this brief is there yet).
   - `grep -cF "func (v *Invoicer) Storno(ctx context.Context, invoiceID int64, reason string, today time.Time) (int64, error) {" go/internal/billingjob/invoicer.go | tail -1` prints `1`.
   - `grep -cF "func ExportAllZip(ctx context.Context, q DB, today time.Time) ([]byte, error) {" go/internal/web/billing/analytics.go | tail -1` prints `1`.
   - `find docs/tasks/1559-files -name '*.txt' | wc -l | tail -1` prints `5`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1559-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   1633706c187a42af5f173988bd892b2a752274f626c08b8c8309334c464ce032  go/internal/web/billing/admin_more.go
   159765b0973f4a47a873e4b286a49d98779591006d206df88849d188feed2ec6  go/internal/web/billing/admin_more_test.go
   80d91f2bf07ef5bca88dd0f68c6e52932e01c13b6d8c9a321605cbd9c5050c12  go/internal/web/billing/table.go
   f2d07abc867a91139762a9aa8fc7eb8dd14a78ba11aba0ad873c9ebbc8632f45  go/internal/web/billing/routes_inventory_test.go
   7c851e0ecf706cfa478fe82689e39d657ee68643518c007670f9dbb493fd5801  go/cmd/ubyhost-web/register_web_billing_test.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1559 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/billing internal/mail cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/billing/... ./internal/mail/ ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). No commit (nothing changed).

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1559 && chown postgres /var/tmp/pg1559 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1559/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1559/data -o "-p 55505 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1559" -l /var/tmp/pg1559/log -w start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55505/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55505/postgres go test ./internal/web/billing/... ./cmd/ubyhost-web/... ./internal/mail/ -count=1 2>&1 | tail -30
   ```

   Expected: three lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/billing	<seconds>s`, `ok  ...go/cmd/ubyhost-web	<seconds>s` and `ok  ...go/internal/mail	<seconds>s`. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55505/postgres go test ./internal/web/billing/ ./cmd/ubyhost-web/ ./internal/mail/ -count=1 -v -run '^TestBillingRoutesRegistered$|^TestRoutesNeedNoPool$|^TestStorno$|^TestExports$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -40
   ```

   Expected: one `--- PASS` line for each of the 4 tests (TestBillingRoutesRegistered, TestRoutesNeedNoPool, TestStorno, TestExports), then three `ok` lines; no `--- SKIP`, no `--- FAIL`.

5. Stop and delete the throwaway server (skip if you used a server you did not start):

   ```bash
   su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1559/data -m fast stop' 2>&1 | tail -2; rm -rf /var/tmp/pg1559
   ```

   Expected: `server stopped`.

6. Write the report (§9), set `Status: review` and commit "1559 step 6".

## 5. Do not touch

`go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/internal/billingjob/`, `go/internal/pdf/`, `go/internal/billing/`, `go/cmd/ubyhost-web/main.go`, `registry.go` and every other `register_*.go`, the existing files of `go/internal/web/billing/` that brief 1341 created (`admin.go`, `analytics.go`, `bankimport.go`, `page.go`, `pyutil.go`, `admin_test.go`, `golden_test.go`, `testdata/`), `App/` (no Python file, no `App/tests/conftest.py`), `docs/context/*`, and every file not in §3. AGENTS.md rules that apply: 2 (privacy), 3 (no real data in tests), 4 (no new dependency: `go.mod` and `go.sum` stay as they are), 5 (SQL is plain PostgreSQL through pgx, taken from the Python), 8 (never push to `main`).

## 6. Commands

Exactly the commands of §4 (steps 1, 2, 4, 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 5 files.
- [ ] Step 2 printed nothing.
- [ ] Step 4 printed three `ok` lines and each of the 4 named tests printed `--- PASS` (none `SKIP`, none `FAIL`).
- [ ] `git log --oneline --grep='^1559 step' | tail -5` lists at least the step 1 commit, and `git show --stat --format=%h <that hash> | tail -20` lists only paths of §3.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed.
- [ ] UI: not applicable in this brief (no template). The storno form and the export links are in the page template of brief 1560.

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

Write `docs/tasks/1559-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git log --oneline --grep='^1559 step' | tail -10`, then `git show --stat --format=%h --grep='^1559 step' HEAD~5..HEAD | tail -30` or one `git show --stat <hash>` per commit).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `admin_more.go`: `adminStorno` must run CSRF, the integer check, then the operator gate; the refusal list must map each sentinel to the Python message; `ExportZip` must read the stored PDFs through `getInvoiceFile`/`pdfBytes` (never re-render) and close the zip before the bytes are used.

## Owner steps

None here (routes dormant).
