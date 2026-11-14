# 1556: Go subscription billing, part 2: the host's plan page GET /predplatne

Status: todo
Depends on: 1555 | Base commit: none (one big PR mode: the branch that is checked out) | Branch: the current one
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** The owner wants one big pull request for the whole Go port. You work on the branch that is checked out now. Never create a branch, never push, never open a PR. After each step that changes a file, commit with the message `1556 step k` (k is the step number) and nothing else in the first line; end the message with the two trailer lines from the session reminder if one is given. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1556 step'` and `git show --stat` on those commits.

## 1. Objective

Add `GET /predplatne` (the host's plan page: order form, current plan, change forms, cancel or resume form, invoice list) to `go/internal/web/billing` with its Go template, the form-value and invoice reads and the upgrade-card prices. `POST /predplatne` follows in 1557, so the path is not yet switchable.

## 2. Context

Rules (AGENTS.md): 1 filing is not touched; 2 privacy: no new personal-data field, no outbound request; the page reads the host's own `billing_account`, `legal_entity`, `user_account` and `platform_invoice` rows as Python does; 3 test data is made up (`@example.test`, test-only secrets); 4 no new dependency; 5 plain PostgreSQL through pgx with the Python SQL; 6 light mode, forms work without JavaScript; 8 never push to `main`.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The page reads data Python already reads for the same host.

**All code is pre-written, compiled and tested.** Sidecars are `docs/tasks/1556-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Write nothing outside §3. Three of them (`table.go`, `routes_inventory_test.go`, `register_web_billing_test.go`) were created by brief 1555 and are replaced by the version that holds the routes of this stage; replace means the plain `cp` of step 1, there is nothing to merge.

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
| `hostPlanPage` | `routes/billing.py` `plan_page` 73-84 | login (a paused host may open it); billing off: 303 `/settings`; else render `billing_plan.html` with `form_values(owner, {plan, interval} from the query, last value wins)` |
| `renderPlan`, `buildPlanView` | `_page` 35-66 | account, order form values, errors, note, preview, quote, apartments (`max(1, active count)`), `orderable`, formatted trial end and period end, the invoices, the upgrade card; `Page{Nav: settings, BodyKind: settings, V2}`, the title is `t('billing.plan.title') + " · UbyHost"`, the h1 slot is empty and the back header is written in the body |
| `FormValues` | `billing_order.form_values` 25-59 | saved order, else signup preferences (an unordered account only), else the first legal entity, else the login address; a non-empty query value beats a preference, an invalid one then falls to the default |
| `ForOwner` | `billing_invoices.for_owner` 248-257 | the host's documents, newest first, no PDF bytes |
| `UpgradeFor` | `_page` 44-60 | the other plan's price, the yearly saving, the lock add-on price |
| `templates/billing_plan.tmpl` | `billing_plan.html` | four states: no billing row (explanation only), orderable (order form), ordered (facts, change forms, cancel or resume form), invoices table. `ui_section` call blocks are written out with `sec_head`; the change forms with `change_open`; facts, badges and card lists are built in Go |

**Money and date computations (every one has a test with fixed numbers):**

| What | Python | Go | Test and fixed numbers |
|---|---|---|---|
| whole-crown amount, thousands with a space | `_kc` billing.py 31-32 | `kcWhole` | `TestKcWhole`: 0 -> `0`, 1190 -> `1 190`, 1234567 -> `1 234 567`, -1234 -> `-1 234` |
| invoice row amount | `'{:,}'.format(total_haler // 100).replace(',', ' ')` in `billing_plan.html` | `Kc(haler)` (floor, then grouping) | `TestPlanPage`: 119000 -> `1 190 Kč`, -119000 -> `-1 190 Kč` |
| order quote total | `billing_order.quote` 92-97 (apartments `max(1, n)`, whitelabel from the account, no discount) | `billing.Quote(count, plan, interval, ttlock, white, 0).Total` | `TestPlanPage`: trial host, no apartment (counts as 1), `?plan=max&interval=month` -> `208 Kč` (149 + 59) |
| apartments billed | `billing_order.apartments` 20-22 | `billing.Apartments` | `TestUpgradeFor`: 3 active apartments |
| upgrade price | `_page` 50-53 | `UpgradeFor` | `TestUpgradeFor`: 3 apartments Standard month -> Max `624`; year -> `5 280`; Max with the lock add-on -> Standard `594` (447 + 147) |
| yearly saving | `round(100 * (12 * month - year) / (12 * month)) if month else 0`, line 56 (true division, half to even) | `savePct` with `math.RoundToEven` | `TestSavePct`: (447, 3570) -> 33, (149, 1190) -> 33, (2, 21) -> 12 (12.5 rounds to even; half up would say 13), (2, 15) -> 38, (0, 0) -> 0 |
| lock add-on price | `billing.TTLOCK["month"]` | constant `ttlockMonthly` 49 | `TestUpgradeFor` pins it to `billing.Quote(1, standard, month, lock)` |
| dates | `validation.fmt_date` (first 10 characters, `DD.MM.YYYY`, unparseable input unchanged) | `fmtDate` | `TestFmtDate`: `2026-11-20T10:00:00+00:00` -> `20.11.2026`, `soon` -> `soon`, `2026-13-40` unchanged; `TestPlanPage`: period end `2026-12-31` -> `31.12.2026` |
| invoice date cell | `issue_date \| string \| truncate(10, true, '')` | `cut(.., 10)` | `TestPlanPage` |

**Known smaller differences:** the Jinja `t()` fallback for a missing key is the key itself, as the Go catalog does; `ui_facts` values are `| safe` in Jinja (not escaped) and escaped by the Go helper unless marked, which only changes `'` into `&#39;`, the same character in HTML.

**Verified by the brief writer** (fresh throwaway worktree of the branch head; briefs 1555 to 1556 copied in order exactly as their step 1 does): gofmt empty, `go build ./...` and `go vet ./internal/web/billing/... ./internal/mail/ ./cmd/...` silent, `go test ./internal/web/billing/... ./cmd/ubyhost-web/... ./internal/mail/` ok on PostgreSQL 16 with the 8 named tests PASS and none skipped. Not run: any Python test, any browser test (the pages are dormant).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/billing/host.go` | create | `FormValues` (billing_order.form_values), `signupSelection`, `ForOwner` (billing_invoices.for_owner), `UpgradeFor` and `savePct` (the upgrade card), `fmtDate`, `kcWhole` |
| `go/internal/web/billing/plan_page.go` | create | page view model, template funcs (`sec_head`, `card_head`, `change_open`, `sec_head_raw`), `renderPlan` (the Python `_page`, also used by 1557) and the GET handler |
| `go/internal/web/billing/templates/billing_plan.tmpl` | create | Go twin of `billing_plan.html` |
| `go/internal/web/billing/plan_page_test.go` | create | tests: money and date pins, form values, upgrade card, the rendered page in each state |
| `go/internal/web/billing/table.go` | replace (created by 1555; this version holds the routes of this stage) | route table: adds `GET /predplatne` |
| `go/internal/web/billing/routes_inventory_test.go` | replace (created by 1555; this version holds the routes of this stage) | the table holds exactly the 5 routes of this stage |
| `go/cmd/ubyhost-web/register_web_billing_test.go` | replace (created by 1555; this version holds the routes of this stage) | the 5 routes reach their patterns |
| `docs/tasks/1556-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1556-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git log --oneline --grep='^1555 step' | tail -3` prints at least one line (brief 1555 is in this branch).
   - `ls go/internal/web/billing/routes.go go/internal/web/billing/table.go go/internal/web/billing/testenv_test.go 2>&1 | tail -3` lists the three files of brief 1555.
   - `ls go/internal/web/billing/host.go go/internal/web/billing/plan_page.go 2>&1 | tail -1` says "No such file" (nothing of this brief is there yet).
   - `grep -cF "func CleanSelection(params url.Values) map[string]string {" go/internal/signup/signup.go | tail -1` prints `1`.
   - `grep -cF "func ParseISODate(s string) (time.Time, bool) {" go/internal/validation/validation.go | tail -1` prints `1`.
   - `find docs/tasks/1556-files -name '*.txt' | wc -l | tail -1` prints `7`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1556-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   ca67a946376b77e5d2999ce0f6443908149e0625add2f9f5a61a10f09d77254c  go/internal/web/billing/host.go
   c8224214ae6bc193e07ad53859a0e7ecbc71e09f877d5182f3bed8bf706c7736  go/internal/web/billing/plan_page.go
   901d1a9181a97bf39f2484ac1d825761eb56c99595b62d0f37b8f4d53670155e  go/internal/web/billing/templates/billing_plan.tmpl
   12fde8e04642a08f153da61dd19d7017661ef3c1aead9aa8d50e55156c9d201b  go/internal/web/billing/plan_page_test.go
   d8cad6c25bcef66b8be7691e48da28967cc1f685abf53290921c0df637e4bed1  go/internal/web/billing/table.go
   a75f6e7fc10aae081d0cc8d2e38d3998fc037cb310fe02ad03321723685986e1  go/internal/web/billing/routes_inventory_test.go
   1b8b5256b79e13471b240639c689bd3d1b0f47644b5ae713cb77cc476fd0aede  go/cmd/ubyhost-web/register_web_billing_test.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1556 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/billing internal/mail cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/billing/... ./internal/mail/ ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). No commit (nothing changed).

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1556 && chown postgres /var/tmp/pg1556 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1556/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1556/data -o "-p 55502 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1556" -l /var/tmp/pg1556/log -w start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55502/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55502/postgres go test ./internal/web/billing/... ./cmd/ubyhost-web/... ./internal/mail/ -count=1 2>&1 | tail -30
   ```

   Expected: three lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/billing	<seconds>s`, `ok  ...go/cmd/ubyhost-web	<seconds>s` and `ok  ...go/internal/mail	<seconds>s`. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55502/postgres go test ./internal/web/billing/ ./cmd/ubyhost-web/ ./internal/mail/ -count=1 -v -run '^TestBillingRoutesRegistered$|^TestSavePct$|^TestKcWhole$|^TestFmtDate$|^TestUpgradeFor$|^TestFormValues$|^TestPlanPage$|^TestRoutesNeedNoPool$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -40
   ```

   Expected: one `--- PASS` line for each of the 8 tests (TestBillingRoutesRegistered, TestSavePct, TestKcWhole, TestFmtDate, TestUpgradeFor, TestFormValues, TestPlanPage, TestRoutesNeedNoPool), then three `ok` lines; no `--- SKIP`, no `--- FAIL`.

5. Stop and delete the throwaway server (skip if you used a server you did not start):

   ```bash
   su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1556/data -m fast stop' 2>&1 | tail -2; rm -rf /var/tmp/pg1556
   ```

   Expected: `server stopped`.

6. Write the report (§9), set `Status: review` and commit "1556 step 6".

## 5. Do not touch

`go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/internal/billingjob/`, `go/internal/pdf/`, `go/internal/billing/`, `go/cmd/ubyhost-web/main.go`, `registry.go` and every other `register_*.go`, the existing files of `go/internal/web/billing/` that brief 1341 created (`admin.go`, `analytics.go`, `bankimport.go`, `page.go`, `pyutil.go`, `admin_test.go`, `golden_test.go`, `testdata/`), `App/` (no Python file, no `App/tests/conftest.py`), `docs/context/*`, and every file not in §3. AGENTS.md rules that apply: 2 (privacy), 3 (no real data in tests), 4 (no new dependency: `go.mod` and `go.sum` stay as they are), 5 (SQL is plain PostgreSQL through pgx, taken from the Python), 8 (never push to `main`).

## 6. Commands

Exactly the commands of §4 (steps 1, 2, 4, 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 7 files.
- [ ] Step 2 printed nothing.
- [ ] Step 4 printed three `ok` lines and each of the 8 named tests printed `--- PASS` (none `SKIP`, none `FAIL`).
- [ ] `git log --oneline --grep='^1556 step' | tail -5` lists at least the step 1 commit, and `git show --stat --format=%h <that hash> | tail -20` lists only paths of §3.
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

Write `docs/tasks/1556-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git log --oneline --grep='^1556 step' | tail -10`, then `git show --stat --format=%h --grep='^1556 step' HEAD~5..HEAD | tail -30` or one `git show --stat <hash>` per commit).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `host.go` (`FormValues`: a non-empty query value must beat the stored preference even when invalid; the account's own order must win once a plan is ordered; `UpgradeFor`: `lock && other != "max"` and the half-to-even `savePct`) and the money rows of `plan_page.go` (`Kc` for invoices, `kcWhole` for quotes). The template is content, not money, but check that the cancel form posts to `/predplatne/zrusit`, resume to `/predplatne/obnovit` and every change form to `/predplatne/zmena` with the `_csrf` field.

## Owner steps

None here: the page is dormant. Before the owner adds `/predplatne` to `UBYHOST_GO_PATHS` (after brief 1557) the UX gate of rule 10 must run on staging: `test_layout_lint_browser.py`, the 390/768/1280 screenshots of the page in each of its four states, and the design-system checklist.
