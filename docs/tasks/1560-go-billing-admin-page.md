# 1560: Go subscription billing, part 6: the operator's billing page GET /admin/fakturace and the route inventory

Status: todo
Depends on: 1559 | Base commit: none (one big PR mode: the branch that is checked out) | Branch: the current one
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** The owner wants one big pull request for the whole Go port. You work on the branch that is checked out now. Never create a branch, never push, never open a PR. After each step that changes a file, commit with the message `1560 step k` (k is the step number) and nothing else in the first line; end the message with the two trailer lines from the session reminder if one is given. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1560 step'` and `git show --stat` on those commits.

## 1. Objective

Add `GET /admin/fakturace` (the operator's billing page: unpaid invoices with mark-paid and storno forms, the month's invoices, the watch card and the collapsed reports) to `go/internal/web/billing` with its Go template, and close the area with the inventory of all 13 routes. After this brief every path of `billing.py` and `admin_billing.py` is served by Go for every method.

## 2. Context

Rules (AGENTS.md): 1 filing is not touched; 2 privacy: no new personal-data field and no outbound request; the page shows the same data as Python's, to an operator only; 3 test data is made up (`@example.test`, test-only secrets); 4 no new dependency; 5 plain PostgreSQL through pgx with the Python SQL; 6 light mode, forms work without JavaScript; 8 never push to `main`.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The page shows data Python already shows to the operator.

**All code is pre-written, compiled and tested.** Sidecars are `docs/tasks/1560-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Write nothing outside §3. Three of them (`table.go`, `routes_inventory_test.go`, `register_web_billing_test.go`) were created by brief 1555 and are replaced by the version that holds the routes of this stage; replace means the plain `cp` of step 1, there is nothing to merge.

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
| `adminPageHandler` | `routes/admin_billing.py` `billing_admin_page` 31-64 | operator only (403 for a host, login redirect for a visitor); `AdminPageData` (brief 1341, pinned to Python by its golden file) with `mesic`, `q`, `state` from the query (last value); the extra context values `posthog_url`, `signup_enabled`, `ads_export_days` |
| `buildAdminView` | the inline Jinja of `admin_billing.html` | the watch rows, the portfolio filter, the badges, the formatted amounts and dates |
| `templates/admin_billing.tmpl` | `admin_billing.html` | sections unpaid (with the mark-paid and storno forms), month (with the export link), watch card (above the reports when anything is listed, else below the accounts), the collapsed reports (portfolio, payments, statement upload, revenue, trend, movement, funnel, discounts, accounts, PostHog, ads export when signup is on) |
| `posthogURL` | `config.POSTHOG_APP_URL if analytics.enabled() else ""` | the key set, `POSTHOG_HOST` and `POSTHOG_ASSETS_HOST` https and not the US hosts |

**Money and date computations (the data comes from `AdminPageData`; these are the page's own):**

| What | Python | Go | Test and fixed numbers |
|---|---|---|---|
| amounts in haler | `_kc` 27-28: `int(haler) // 100`, thousands with a space | `Kc` (existing) | `TestAdminPage`: 119000 -> `1 190 Kč` |
| negative amount in the month table | `kc(x) if x >= 0 else '−' ~ kc(-x)` (U+2212) | `minusKc` | `TestMinusFormats`: 119000 -> `1 190`, -119000 -> `−1 190`; `TestAdminPage`: the storno row prints `−1 190 Kč` |
| MRR change | `(n ~ ' Kč') if n >= 0 else ('−' ~ (0 - n) ~ ' Kč')` | `minusWhole` | `TestMinusFormats`: 5 -> `5 Kč`, -7 -> `−7 Kč` |
| portfolio price and monthly | `c.net_czk`, `c.monthly_czk` printed as plain integers | `AdminPage.Cockpit` | `TestAdminPage`: 3 apartments Standard year: `3570 Kč` a year, `298 Kč` a month (297.5 rounds half to even) |
| overdue line in the watch card | `display_name ~ ' · ' ~ number ~ ' · ' ~ kc(total) ~ ' Kč · ' ~ days_late` | `buildAdminView` | `TestAdminPage`: `UBY-2026-0031 · 1 190 Kč · 8` (due 2026-11-05, today 2026-11-13) |
| dates | `fmt_date`, `[:10]` slices | `fmtDate`, `cut` | `TestAdminPage`: `05.11.2026` on the overdue badge |
| filter | `q \| lower in (name ~ ' ' ~ email ~ ' ' ~ username) \| lower`, `c.status == state` | `strings.ToLower`, same test | `TestAdminPage`: `?q=zzz` and `?state=paused` hide the row, `?state=active` and `?q=HOST1` show it |
| month default | `month_or_current` | `MonthOrCurrent` | `TestAdminPage`: `value="2026-11"` at the test clock 2026-11-13 |

A missing display name prints `None`, as Jinja does for a NULL column. `lower` of Python and Go differ only for rare special-casing letters.

**Outbound requests:** none. The PostHog link is a plain `href` the operator may click.

**The full inventory.** With this brief `table.go` holds the 13 routes of the two Python files, and `routes_inventory_test.go` and `register_web_billing_test.go` list exactly them:

| Path | Methods | Brief |
|---|---|---|
| `/predplatne` | GET, POST | 1556, 1557 |
| `/predplatne/zmena`, `/predplatne/zrusit`, `/predplatne/obnovit` | POST | 1557, 1555, 1555 |
| `/predplatne/faktury/{id}.pdf` | GET | 1555 |
| `/admin/fakturace` | GET | 1560 |
| `/admin/fakturace/vypis`, `/admin/fakturace/{id}/zaplaceno` | POST | 1558 |
| `/admin/fakturace/{id}/storno` | POST | 1559 |
| `/admin/fakturace/{id}.pdf`, `/admin/fakturace/export`, `/admin/fakturace/export-vse` | GET | 1555, 1559 |

There is no path collision in this area: Go serves every method Python serves on each path.

**Verified by the brief writer** (fresh throwaway worktree of the branch head; briefs 1555 to 1560 copied in order exactly as their step 1 does): gofmt empty, `go build ./...` and `go vet ./internal/web/billing/... ./internal/mail/ ./cmd/...` silent, `go test ./internal/web/billing/... ./cmd/ubyhost-web/... ./internal/mail/` ok on PostgreSQL 16 with the 5 named tests PASS and none skipped. The page data is the existing `AdminPageData`, pinned to Python by brief 1341's golden file. Not run: any Python test, any browser test (the pages are dormant).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/billing/admin_page.go` | create | `buildAdminView` (rows, filters, facts), `posthogURL`, `adminTabs`, `minusKc`, `minusWhole`, the GET handler |
| `go/internal/web/billing/templates/admin_billing.tmpl` | create | Go twin of `admin_billing.html` |
| `go/internal/web/billing/admin_page_test.go` | create | tests: config helpers, minus formats, the rendered page with fixed numbers, filters, watch card position, access |
| `go/internal/web/billing/table.go` | replace (created by 1555; this version holds the routes of this stage) | route table: adds `GET /admin/fakturace`; the final table of 13 routes |
| `go/internal/web/billing/routes_inventory_test.go` | replace (created by 1555; this version holds the routes of this stage) | the table holds exactly the 13 Python routes |
| `go/cmd/ubyhost-web/register_web_billing_test.go` | replace (created by 1555; this version holds the routes of this stage) | all 13 routes reach their patterns |
| `docs/tasks/1560-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1560-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git log --oneline --grep='^1559 step' | tail -3` prints at least one line (brief 1559 is in this branch).
   - `ls go/internal/web/billing/routes.go go/internal/web/billing/table.go go/internal/web/billing/testenv_test.go 2>&1 | tail -3` lists the three files of brief 1555.
   - `ls go/internal/web/billing/admin_page.go go/internal/web/billing/templates/admin_billing.tmpl 2>&1 | tail -1` says "No such file" (nothing of this brief is there yet).
   - `grep -cF "func AdminPageData(ctx context.Context, q DB, month, qstr, state string, today time.Time) (AdminPage, error) {" go/internal/web/billing/page.go | tail -1` prints `1`.
   - `find docs/tasks/1560-files -name '*.txt' | wc -l | tail -1` prints `6`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1560-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   e21d7c760c05c6b6ac2ccd00279b6286ba0e0b88a4d0c05ccea01f5fe16a8427  go/internal/web/billing/admin_page.go
   8943abf96da546c5eeca0656b54f963e67d3eeb4a2d94ca441196c08e06dd476  go/internal/web/billing/templates/admin_billing.tmpl
   794777f73449c470ea8bdbd9807ffa2ae0e19d6fd6de44569f6c856076ea4f78  go/internal/web/billing/admin_page_test.go
   fd6b654241f9482b38efdb5bb4dfc6232d8f4ebb101d4c6bb4ef0f72944a2475  go/internal/web/billing/table.go
   90c1d59a94432fdf1cee6df98b10b866bbc9dbd75b7418fda50680a271dc7387  go/internal/web/billing/routes_inventory_test.go
   7231969d6bedfabba10da65943b3b06f959624518f09a0bc2068beff8d3d6b3a  go/cmd/ubyhost-web/register_web_billing_test.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1560 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/billing internal/mail cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/billing/... ./internal/mail/ ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). No commit (nothing changed).

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1560 && chown postgres /var/tmp/pg1560 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1560/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1560/data -o "-p 55506 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1560" -l /var/tmp/pg1560/log -w start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55506/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55506/postgres go test ./internal/web/billing/... ./cmd/ubyhost-web/... ./internal/mail/ -count=1 2>&1 | tail -30
   ```

   Expected: three lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/billing	<seconds>s`, `ok  ...go/cmd/ubyhost-web	<seconds>s` and `ok  ...go/internal/mail	<seconds>s`. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55506/postgres go test ./internal/web/billing/ ./cmd/ubyhost-web/ ./internal/mail/ -count=1 -v -run '^TestBillingRoutesRegistered$|^TestRoutesNeedNoPool$|^TestPosthogURL$|^TestMinusFormats$|^TestAdminPage$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -40
   ```

   Expected: one `--- PASS` line for each of the 5 tests (TestBillingRoutesRegistered, TestRoutesNeedNoPool, TestPosthogURL, TestMinusFormats, TestAdminPage), then three `ok` lines; no `--- SKIP`, no `--- FAIL`.

5. Stop and delete the throwaway server (skip if you used a server you did not start):

   ```bash
   su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1560/data -m fast stop' 2>&1 | tail -2; rm -rf /var/tmp/pg1560
   ```

   Expected: `server stopped`.

6. Write the report (§9), set `Status: review` and commit "1560 step 6".

## 5. Do not touch

`go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/internal/billingjob/`, `go/internal/pdf/`, `go/internal/billing/`, `go/cmd/ubyhost-web/main.go`, `registry.go` and every other `register_*.go`, the existing files of `go/internal/web/billing/` that brief 1341 created (`admin.go`, `analytics.go`, `bankimport.go`, `page.go`, `pyutil.go`, `admin_test.go`, `golden_test.go`, `testdata/`), `App/` (no Python file, no `App/tests/conftest.py`), `docs/context/*`, and every file not in §3. AGENTS.md rules that apply: 2 (privacy), 3 (no real data in tests), 4 (no new dependency: `go.mod` and `go.sum` stay as they are), 5 (SQL is plain PostgreSQL through pgx, taken from the Python), 8 (never push to `main`).

## 6. Commands

Exactly the commands of §4 (steps 1, 2, 4, 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 6 files.
- [ ] Step 2 printed nothing.
- [ ] Step 4 printed three `ok` lines and each of the 5 named tests printed `--- PASS` (none `SKIP`, none `FAIL`).
- [ ] `git log --oneline --grep='^1560 step' | tail -5` lists at least the step 1 commit, and `git show --stat --format=%h <that hash> | tail -20` lists only paths of §3.
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

Write `docs/tasks/1560-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git log --oneline --grep='^1560 step' | tail -10`, then `git show --stat --format=%h --grep='^1560 step' HEAD~5..HEAD | tail -30` or one `git show --stat <hash>` per commit).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `admin_page.go` (the filter and the formatted amounts: `minusKc`, `minusWhole`, the overdue line; `adminPageHandler` must use `gate{admin: true}`) and the forms in `templates/admin_billing.tmpl`: mark paid posts to `/admin/fakturace/{id}/zaplaceno`, storno to `/admin/fakturace/{id}/storno` and the statement upload to `/admin/fakturace/vypis` with `enctype="multipart/form-data"`, each with the `_csrf` field. `table.go` and the inventory test are the list of what is reachable.

## Owner steps

1. After the whole big PR is merged and deployed, run the UX gate of rule 10 on staging for the two pages (brief 1412 is the pattern): `test_layout_lint_browser.py` green, the 390, 768 and 1280 px screenshots of `/predplatne` (four states) and `/admin/fakturace`, and the design-system checklist.
2. Only then, in the server's `.env`, add the two paths to `UBYHOST_GO_PATHS`: `/predplatne` and `/admin/fakturace` (open the file with `nano /srv/ubyhost/.env`, as in docs/LIGHTSAIL.md; add them to the comma-separated list), then reload Caddy as that document says. Together they switch the 13 routes of this area as whole paths. Nothing else is needed: the routes are registered already.
3. To go back, remove the two names and reload Caddy.
