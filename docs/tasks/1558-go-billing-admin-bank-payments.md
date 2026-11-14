# 1558: Go subscription billing, part 4: the operator's bank statement upload and mark paid

Status: todo
Depends on: 1557 | Base commit: none (one big PR mode: the branch that is checked out) | Branch: the current one
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** The owner wants one big pull request for the whole Go port. You work on the branch that is checked out now. Never create a branch, never push, never open a PR. After each step that changes a file, commit with the message `1558 step k` (k is the step number) and nothing else in the first line; end the message with the two trailer lines from the session reminder if one is given. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1558 step'` and `git show --stat` on those commits.

## 1. Objective

Add the write side of bank payments to `go/internal/web/billing` (statement import, matching, mark paid, settle the account, the payment confirmation mail) and the two operator routes `POST /admin/fakturace/vypis` and `POST /admin/fakturace/{id}/zaplaceno`. These change what a host owes and what the account state is, so every amount and date rule is pinned with fixed numbers.

## 2. Context

Rules (AGENTS.md): 1 filing is not touched; 2 privacy: no new personal-data field and no outbound request; `bank_payment` rows (counter account, message) are stored as Python stores them; the mail is queued in the existing outbox; 3 test data is made up (`@example.test`, test-only secrets); 4 no new dependency; 5 plain PostgreSQL through pgx with the Python SQL; 6 light mode, forms work without JavaScript; 8 never push to `main`.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The upload stores the same `bank_payment` columns Python stores, and the confirmation mail goes through the existing `email_outbox` queue (kind `billing_paid`).

**All code is pre-written, compiled and tested.** Sidecars are `docs/tasks/1558-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Write nothing outside §3. Three of them (`table.go`, `routes_inventory_test.go`, `register_web_billing_test.go`) were created by brief 1555 and are replaced by the version that holds the routes of this stage; replace means the plain `cp` of step 1, there is nothing to merge.

**The thread (briefs 1555 to 1560).** Port the two Python route files of subscription billing into the existing Go package `go/internal/web/billing` (package `billingweb`): `App/app/routes/billing.py` (6 routes, the host's plan page `/predplatne`) and `App/app/routes/admin_billing.py` (7 routes, the operator's `/admin/fakturace`). Briefs 1340 and 1341 already ported the engine (`go/internal/billing`: quote, status machine, `Place`, `Change`, `Cancel`, `Resume`) and the read side of the operator page (`AdminPageData`, statement parser, exports as functions); billing job thread ported `go/internal/billingjob` (`Invoicer`: issue, `Storno`, `Send`) and `go/internal/pdf`. This thread adds the handlers, templates, the ARES lookup, the bank-payment write side and the registration `go/cmd/ubyhost-web/register_web_billing.go`. Nothing routes to them until the owner adds the paths to `UBYHOST_GO_PATHS`.

| Brief | Routes (method path, Python function) |
|---|---|
| 1555 | `GET /predplatne/faktury/{id}.pdf` (plan_invoice_pdf), `POST /predplatne/zrusit` (plan_cancel), `POST /predplatne/obnovit` (plan_resume), `GET /admin/fakturace/{id}.pdf` (billing_admin_pdf); shared gate, catalog, test helpers |
| 1556 | `GET /predplatne` (plan_page) with its template |
| 1557 | `POST /predplatne` (plan_order, ARES fill), `POST /predplatne/zmena` (plan_change) |
| 1558 | `POST /admin/fakturace/vypis` (billing_admin_statement), `POST /admin/fakturace/{id}/zaplaceno` (billing_admin_mark_paid); bank-payment write side, `billing_paid` mail |
| 1559 | `POST /admin/fakturace/{id}/storno` (billing_admin_storno), `GET /admin/fakturace/export-vse`, `GET /admin/fakturace/export` |
| 1560 | `GET /admin/fakturace` (billing_admin_page) with its template; the full inventory of 13 routes |

Caddy routes by path only. Paths with two methods: `/predplatne` (GET 1556, POST 1557). `/admin/fakturace` is GET only. Every other path has one method. The paths become fully served by Go with these briefs: `/predplatne` after 1557, `/predplatne/zmena`, `/predplatne/zrusit`, `/predplatne/obnovit`, `/predplatne/faktury/{id}.pdf`, `/admin/fakturace` after 1560, `/admin/fakturace/vypis`, `/admin/fakturace/{id}/zaplaceno`, `/admin/fakturace/{id}/storno`, `/admin/fakturace/{id}.pdf`, `/admin/fakturace/export`, `/admin/fakturace/export-vse`. The writer could not read the server's `UBYHOST_GO_PATHS` and assumes neither `/predplatne` nor `/admin/fakturace` is in it; if one is, the routes of that prefix go live the moment the brief that adds them deploys.

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
| `adminStatement` | `routes/admin_billing.py` `billing_admin_statement` 66-81 | operator; the `statement` file part (last one with a file name; a url-encoded post or an empty name is "missing"): `err` `billing.admin.statement.missing`; over 5 MiB or a parser refusal (`StatementError`) `err` `...unreadable`; else import and `msg` `billing.admin.statement.done` with the six counts |
| `payer.importStatement` | `bank_import.import_statement` 214-226 | parse (brief 1341's `Parse`); a credit whose VS is not `20\d{6}` is `ignored`; the rest go to `record`; one `bank_statement_import` audit row (`matched=1 unmatched=0 partial=0 overpaid=0 seen=0 ignored=0`, actor = username, owner = the operator's own workspace) |
| `payer.record` | `bank_import.record` 187-211 | the open invoice with this VS (kind invoice or supplementary, not voided): amount equal -> `matched`, greater -> `overpaid`, smaller -> `partial` (the partial payment is linked to its invoice, which stays open), no invoice or already paid -> `unmatched`; insert `bank_payment` (`ON CONFLICT (bank_tx_id) DO NOTHING`: a repeat is `seen`); `matched` and `overpaid` mark the invoice paid on the statement date (`bank_auto`) and settle the owner |
| `payer.markPaid` | `billing_invoices.mark_paid` 220-240 | one `UPDATE ... WHERE paid_on IS NULL AND voided = 0 AND kind != 'storno'`; on a change audit `platform_invoice_paid` (`<number> <via>`) and queue the `billing_paid` mail |
| `payer.settle` | `billing_jobs.settle` 141-163 | an `overdue` or `paused` account with a plan goes back to `active` (status audit, actor `system`) when no invoice or supplementary invoice is unpaid and past due (`due_date < today`); a `paused` account also needs a paid, unvoided `invoice` with `period_to >= today` |
| `adminMarkPaid` | `billing_admin_mark_paid` 84-97 | operator; `paid_on` stripped and checked with `date.fromisoformat` (bad: `err` `billing.admin.paid.bad_date`); `markPaidManually` false: `err` `...not_open`; else `msg` `...done` |
| `paidMail` | `mail_notify.billing_paid` 3126-3156, `build_billing_paid` 3111-3123 | one copy to the buyer address (`billing_invoices.recipient`) and one to the account address (one when equal), key `billing-paid-<invoice>-<buyer|account>`, kind `billing_paid`, copy to the operator, payload `{text, html, lang: cs, reply_to}`; nothing while mail is off |

**Money and date computations (every one has a test with fixed numbers):**

| What | Python | Go | Test and fixed numbers |
|---|---|---|---|
| match by amount, in haler | `record` 190-196 | `payer.record` | `TestStatementUpload`: 119000 vs 119000 -> `matched`; 150000 vs 119000 -> `overpaid`; 10000 vs 50000 -> `partial`; no invoice -> `unmatched`; a VS that is not 8 digits -> `ignored` |
| paid date | `paid_on=row["received_on"]` | the same value | same test: `2026-11-12`, via `bank_auto` |
| overdue test in `settle` | `due_date < today.isoformat()` (text compare) | the same SQL | `TestSettle`: due 2026-11-12 with today 2026-11-13 blocks; due 2026-11-13 does not |
| mail amount | `f"{total_haler // 100:,}".replace(",", " ")` | `floorDiv` and `thousands` | `TestStatementUpload`: subject `Faktura UBY-2026-0031 je zaplacena`; `TestBuildBillingPaid`: 1190 -> `1 190 Kč`, date `13.11.2026` |
| manual paid date | `date.fromisoformat(paid_on)` accepts `YYYY-MM-DD`, `YYYYMMDD`, `YYYY-Www-D`, `YYYYWwwD`, `YYYY-Www`, `YYYYWww`, ASCII digits only, a real date or week | `pyISODate` | `TestPyISODate`: 24 inputs with the results Python 3.12 gives, among them `20261113` true, `2026-W53` true, `2025-W53` false, `2026-02-29` false, `0000-01-01` false; `TestMarkPaid`: ` 2026-11-13 ` (stripped) is accepted, `13.11.2026` is not, `20261113` is stored as typed |
| statement size | `STATEMENT_MAX_BYTES = 5 MiB`, read `+1` | `statementMaxBytes` | `TestStatementUploadRefusals`: 5 MiB + 1 byte -> unreadable |

**Audit rows:** `platform_invoice_paid` (actor = the operator's username, owner = the invoice owner, `actor_user_id` = the operator), `bank_statement_import`, `billing_status` `overdue->active` (actor `system`, `actor_user_id` set, as `db.audit` does inside a request). Every statement commits on its own, as in Python (no statement-wide transaction there either); a failure half way leaves the rows done so far, as in Python.

**Outbound requests:** none (mail is only queued in `email_outbox`; the existing outbox worker sends).

**Verified by the brief writer** (fresh throwaway worktree of the branch head; briefs 1555 to 1558 copied in order exactly as their step 1 does): gofmt empty, `go build ./...` and `go vet ./internal/web/billing/... ./internal/mail/ ./cmd/...` silent, `go test ./internal/web/billing/... ./cmd/ubyhost-web/... ./internal/mail/` ok on PostgreSQL 16 with the 8 named tests PASS and none skipped. The mail text is checked against `mail_notify.build_billing_paid`'s Czech strings. Not run: any Python test, any browser test (the pages are dormant).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/billing/payer.go` | create | `payer`: `record`, `importStatement`, `markPaid`, `markPaidManually`, `settle`, `paidMail`, `audit` (bank_import, billing_invoices.mark_paid, billing_jobs.settle, mail_notify.billing_paid) |
| `go/internal/web/billing/admin_actions.go` | create | `adminStatement`, `adminMarkPaid`, `pyISODate` (Python 3.12 `date.fromisoformat`) |
| `go/internal/web/billing/admin_actions_test.go` | create | tests: date rule, statement upload with fixed amounts, refusals, mark paid, settle |
| `go/internal/mail/billing_paid.go` | create | `BuildBillingPaid` (new file in the mail package; the mail thread owns the package, this is a new file only) |
| `go/internal/mail/billing_paid_test.go` | create | pins the mail text with fixed numbers |
| `go/internal/web/billing/table.go` | replace (created by 1555; this version holds the routes of this stage) | route table: adds the statement upload and mark paid |
| `go/internal/web/billing/routes_inventory_test.go` | replace (created by 1555; this version holds the routes of this stage) | the table holds exactly the 9 routes of this stage |
| `go/cmd/ubyhost-web/register_web_billing_test.go` | replace (created by 1555; this version holds the routes of this stage) | the 9 routes reach their patterns |
| `docs/tasks/1558-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1558-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git log --oneline --grep='^1557 step' | tail -3` prints at least one line (brief 1557 is in this branch).
   - `ls go/internal/web/billing/routes.go go/internal/web/billing/table.go go/internal/web/billing/testenv_test.go 2>&1 | tail -3` lists the three files of brief 1555.
   - `ls go/internal/web/billing/payer.go go/internal/mail/billing_paid.go 2>&1 | tail -1` says "No such file" (nothing of this brief is there yet).
   - `grep -cF "func Parse(data []byte) ([]Payment, error) {" go/internal/web/billing/bankimport.go | tail -1` prints `1`.
   - `grep -cF "func billingServiceContent(appBaseURL, publicBaseURL, supportEmail, subject, body, action string) Content {" go/internal/mail/billing_trial.go | tail -1` prints `1`.
   - `grep -cF "func EnqueueMail(ctx context.Context, pool *pgxpool.Pool, m OutboxMail) (int64, error) {" go/internal/ubyport/notify.go | tail -1` prints `1`.
   - `find docs/tasks/1558-files -name '*.txt' | wc -l | tail -1` prints `8`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1558-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   f352382f1711966624e5c1f432b22eabee030377a01791a90710afdfef72cf62  go/internal/web/billing/payer.go
   3aae89bbf4b2d652dc548c8c953da22afd8bc44934efb670d3880114d688e225  go/internal/web/billing/admin_actions.go
   f700ae34eb7710e34f1d9f780e2a468d20a4d8ceeeaaec3f0646d4ed8274bfc2  go/internal/web/billing/admin_actions_test.go
   dff4f0b3c8ad66117a8bb69e0eff70ffa9cc3f561a64cd53a6d6f09c0aabeee7  go/internal/mail/billing_paid.go
   f4428ead440052613344d95ede284d456b1bf2115e0d6f213b721ef57a452a23  go/internal/mail/billing_paid_test.go
   0fb329b061d7f51145e11915078ef8524252be577a47ccb5e9a7239e67470ba2  go/internal/web/billing/table.go
   84ca72409ea2389db5f61ee539f6d73dbd680f60562d43e6d2226e96b62311ee  go/internal/web/billing/routes_inventory_test.go
   e8dae7d40e7626127be0a4fb0cec23c404920281654a50cbc5831770e62b7a68  go/cmd/ubyhost-web/register_web_billing_test.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1558 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/billing internal/mail cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/billing/... ./internal/mail/ ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). No commit (nothing changed).

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1558 && chown postgres /var/tmp/pg1558 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1558/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1558/data -o "-p 55504 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1558" -l /var/tmp/pg1558/log -w start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55504/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55504/postgres go test ./internal/web/billing/... ./cmd/ubyhost-web/... ./internal/mail/ -count=1 2>&1 | tail -30
   ```

   Expected: three lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/billing	<seconds>s`, `ok  ...go/cmd/ubyhost-web	<seconds>s` and `ok  ...go/internal/mail	<seconds>s`. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55504/postgres go test ./internal/web/billing/ ./cmd/ubyhost-web/ ./internal/mail/ -count=1 -v -run '^TestBillingRoutesRegistered$|^TestRoutesNeedNoPool$|^TestPyISODate$|^TestStatementUpload$|^TestStatementUploadRefusals$|^TestMarkPaid$|^TestSettle$|^TestBuildBillingPaid$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -40
   ```

   Expected: one `--- PASS` line for each of the 8 tests (TestBillingRoutesRegistered, TestRoutesNeedNoPool, TestPyISODate, TestStatementUpload, TestStatementUploadRefusals, TestMarkPaid, TestSettle, TestBuildBillingPaid), then three `ok` lines; no `--- SKIP`, no `--- FAIL`.

5. Stop and delete the throwaway server (skip if you used a server you did not start):

   ```bash
   su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1558/data -m fast stop' 2>&1 | tail -2; rm -rf /var/tmp/pg1558
   ```

   Expected: `server stopped`.

6. Write the report (§9), set `Status: review` and commit "1558 step 6".

## 5. Do not touch

`go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/internal/billingjob/`, `go/internal/pdf/`, `go/internal/billing/`, `go/cmd/ubyhost-web/main.go`, `registry.go` and every other `register_*.go`, the existing files of `go/internal/web/billing/` that brief 1341 created (`admin.go`, `analytics.go`, `bankimport.go`, `page.go`, `pyutil.go`, `admin_test.go`, `golden_test.go`, `testdata/`), `App/` (no Python file, no `App/tests/conftest.py`), `docs/context/*`, and every file not in §3. AGENTS.md rules that apply: 2 (privacy), 3 (no real data in tests), 4 (no new dependency: `go.mod` and `go.sum` stay as they are), 5 (SQL is plain PostgreSQL through pgx, taken from the Python), 8 (never push to `main`).

## 6. Commands

Exactly the commands of §4 (steps 1, 2, 4, 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 8 files.
- [ ] Step 2 printed nothing.
- [ ] Step 4 printed three `ok` lines and each of the 8 named tests printed `--- PASS` (none `SKIP`, none `FAIL`).
- [ ] `git log --oneline --grep='^1558 step' | tail -5` lists at least the step 1 commit, and `git show --stat --format=%h <that hash> | tail -20` lists only paths of §3.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed.
- [ ] UI: not applicable in this brief (no template). The upload and mark-paid forms are in the page template of brief 1560.

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

Write `docs/tasks/1558-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git log --oneline --grep='^1558 step' | tail -10`, then `git show --stat --format=%h --grep='^1558 step' HEAD~5..HEAD | tail -30` or one `git show --stat <hash>` per commit).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `payer.go` (money and operator state: the amount comparison in `record`, that only `matched` and `overpaid` mark an invoice paid, that `partial` stays open, the `UPDATE` guard in `markPaid`, the `settle` conditions and the `paused` case, the mail recipients) and `admin_actions.go` (the operator gate, the 5 MiB read, `pyISODate`). `go/internal/mail/billing_paid.go` is a new file in another thread's package: check it is only the text builder.

## Owner steps

None here (routes dormant). Before the owner adds `/admin/fakturace` to `UBYHOST_GO_PATHS` (after brief 1560) the operator should try one real statement on staging against a copy of the data.
