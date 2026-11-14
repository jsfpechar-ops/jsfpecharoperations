# 1581: Go stay fee host pages, part 1: the list page GET /stay-fees (and the shared page plumbing)

Status: todo
Depends on: 1240, 1240a, 1242, 1330, 1330-fix-1, 1380, 1381, 1543 | Base commit: current tip of the working branch | Branch: task/1581-go-stay-fees-list-page
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1581 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1581 step'` and `git show --stat <commit>`, never a fixed base commit.

## 1. Objective

Add the stay fee list page `GET /stay-fees` to `go/internal/web/stayfees`, drawn inside the Go host layout, together with the page plumbing that brief 1582 (the detail page) reuses: the page template set, the page text catalog, the compact month filter, the fee links and the QR helper. Dormant until the owner routes the path.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (the page only reads; the forms post to routes that already exist in Python or in brief 1330); 2 privacy: no new personal-data field, no new retention line, no outbound request (the pay QR is drawn in the process); 3 fixtures are made up (`@example.test`, test-only keys); 4 no new dependency (stdlib, pgx and packages already in `go.mod`); 5 plain PostgreSQL through `pgxpool`, the Python SQL with `$n` placeholders, no schema change; 6 light mode, every form works without JavaScript; 11 Go first (this brief is the Go port; no file under `App/` changes).

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The page shows the property name, the period figures and, for a sealed period, the council account and the pay QR (SPAYD built from the stored IBAN, variable symbol and total).

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1581-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `beafe135776a8fd100a4ed184a7218c700478d334e522257c7e0b2266a9d13ed` | `go/cmd/ubyhost-web/register_web_stayfees_pages.go` | create | 25 |
| `a7c4b03ea981a82c3fa5858eb63e4f888b4b4ee15a6007ba005aaaef7355a373` | `go/cmd/ubyhost-web/register_web_stayfees_pages_test.go` | create | 23 |
| `842a8a5e752b9cde4cacbc7752a296b9ea88d62afd200b0a99657c88739e6153` | `go/internal/web/stayfees/page_host.go` | create | 374 |
| `cd91fb7bc797cdec952e1dc77e5f8cc3ebeac6790b3598fc4e004dbfc49af81b` | `go/internal/web/stayfees/page_i18n.json` | create | 719 |
| `35e6f2f9e19de6da8d96e5a77694b2823a17f75e532afa96d040176c6426bb90` | `go/internal/web/stayfees/page_i18n_keys.txt` | create | 152 |
| `e4ff57bc5c53e6181b15829e092059d8f91d8fa9c324a554aca3e98ddbaabafc` | `go/internal/web/stayfees/page_list.go` | create | 276 |
| `ee3c483a0f7ce68b4e69de4717567a88505e5f1349ad0047e61ad9e26cea6984` | `go/internal/web/stayfees/page_list_test.go` | create | 360 |
| `f0bea2d8b8dc45002b0861badee5f67c0beb058e55ff414ff1220d471bd9aece` | `go/internal/web/stayfees/pagetemplates/_filter.tmpl` | create | 73 |
| `5c8dfca4d928e67705edfd078aae3df83356f0cd654f83eac4973b33d61f0777` | `go/internal/web/stayfees/pagetemplates/stay_fees.tmpl` | create | 231 |

**How the code is built.** `page_host.go` holds the shared plumbing: the page catalog (`page_i18n.json`, listed key by key in `page_i18n_keys.txt`; written from `App/app/host_i18n.py` by the rules of `App/scripts/go_host_i18n.py`, which cannot name a second catalog file in one package, so it was run once with the key list and the output stored), the template set (`layout.MustParseFuncs` over `pagetemplates/*.tmpl`), the route list that each page file extends in `init()` (`pageAdd`, `PageRoutes`), the fee links (`pgFeeSettingsURL`, `pgFeeOperatorURL`, `pgListReturn`), the compact month filter (`pgParseFilter`, `pgFilterContext`, partial `_filter.tmpl`), the owner periods query (`pgOwnerPeriods`) and the QR helper (`pgQrOf`, which calls `payments.QRDataURI`). `page_list.go` holds the list handler. All names of this part start with `pg` or `page` so the other stay fee briefs in the same package cannot collide with them. The stay fee arithmetic is not re-ported: the page calls `stayfee.PropertyPeriod`, `ReportGroup`, `ReportIssues`, `LoadIssueContext`, `UnsignedStays`, `PaymentDetails` and `FormatCZK` of `go/internal/stayfee`.

**Parity notes (Python `App/app/routes/stay_fees.py` unless named):**

| Python | Go |
|---|---|
| `stay_fees_list` 165-260, template `stay_fees.html` | `(deps).pgListPage`, `(*call).pgList`, `pagetemplates/stay_fees.tmpl` |
| `STAY_FEE_STATUSES` 96-101, `_row_status` 104-115 | `pgFeeStatuses`, `pgRowStatus` |
| `_default_month` 77-80 | `defaultMonth` (existing, helpers.go) |
| `_ui_period_label` 83-96 | `pgPeriodLabel` |
| `fee_copy_source` 62-74 | `feeCopySource` (existing, helpers.go), loop in `pgList` |
| `_list_return` 703-706, `_fee_links` 709-714 | `pgListReturn` |
| `fee_return_path`, `fee_settings_url` 683-690, `fee_operator_url` 692-700 | `feeReturnPath` (existing), `pgFeeSettingsURL`, `pgFeeOperatorURL` |
| `stay_fee.owner_periods` (App/app/stay_fee.py) | `(*call).pgOwnerPeriods` over `stayfee.ApartmentSelect`, `ScanApartment`, `PropertyPeriod` |
| `list_filter.parse` / `context`, `_list_filter.html` compact | `pgParseFilter`, `pgFilterContext`, `_filter.tmpl` |
| `stay_fee_auto.emails_enabled` | `(*call).pgEmailsEnabled` |
| `stay_fee.payment_details` + `payments.qr_data_uri` | `stayfee.PaymentDetails` + `pgQrOf` |
| `page_tabs()` for `nav == 'stay_fees'` (section tabs of Invoices, current one dropped) | `(*call).pgInvoiceTabs` |

Details that are easy to get wrong and are tested: the default month is the current Prague month; a `month` after the current month, before 2000 or malformed falls back to it; an `apartment` id that is not one of the host's live properties is ignored, as is a `status` outside the four values; a configured property is shown once per list (its figures come from the sealed filing when one covers the month, else live); a not yet set up property with a same-town sibling that has a fee (case and accents ignored) shows a copy card with that sibling's setup; the rows are sorted by name then id; the step is 1 until the period is sealed, 2 once sealed, 3 once marked paid; the status is `saved` for a sealed period, `waiting` only when the single issue is "period still running", `attention` for any other issue (the unsigned-stays issue is added for live periods only), `ready` otherwise; the bulk form needs more than one ready property and the zip link more than one saved; the pay QR is a `data:` URL (typed `template.URL` so `html/template` keeps it); `return_to` carries the list's own query without `lang`, percent-encoded like Python's `quote(safe="")`; a not signed in visitor is sent to `/login?next=/stay-fees`.

**Known differences from Python (not fixed here):** there is no Python golden for this page: the Python app cannot be started where this brief was written (no FastAPI), so the tests check the texts, forms, links and counts the Jinja template produces, with made-up rows; `HEAD` is served by the `GET` pattern; the unsigned-stays count of the live period uses the guest rows read by `stayfee.PropertyPeriod` (as Python's `unsigned_stays` does when it is given the period); the schedule day is the UTC date (as `stayfeemail`).

**Paths that become fully served by Go:** none. `GET /stay-fees` is the only route this brief adds; `/stay-fees/*` also holds routes that are not in Go yet (`finalize`, `confirm-ready`, `adjustment`, `pdf`, `pdfs.zip`, `guest-pay-preview`). The owner switch for `/stay-fees` must wait for those briefs. **Goes live on deploy if** `/stay-fees` is already routed to Go (assumed not).

**Anchors that must exist verbatim** (step 0): the Python function lines and the Go function lines listed there.

**Verified by the brief writer** (in a throwaway copy of the working branch tip, with the steps of this brief applied exactly and in order, sidecars copied as step 1 does): `gofmt -l` printed nothing, `go build ./...` and `go vet ./internal/web/stayfees/... ./cmd/...` were silent, and `go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1` passed on PostgreSQL 16 with 0 skipped tests; the golden test `TestActionsMatchPython` of brief 1330 in the same package stayed green and the five named tests PASS. The tests cover: October (ready, waiting, blocked and unset properties, the copy card, the bulk confirm form, the filter markup, the head tabs), September (step 2 with the QR, account and variable symbol copy fields, step 3, the zip link and the saved pills), the apartment, status, future-month and foreign-id filters, the empty states, another host's list, a host with nothing set up (setup-only table), the signed out redirect, `pgListReturn`, `pgRowStatus`, and the registration of the route next to the routes of brief 1330.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_stayfees_pages.go` | create | registers the page routes |
| `go/cmd/ubyhost-web/register_web_stayfees_pages_test.go` | create | route registration test (brief 1582 replaces it) |
| `go/internal/web/stayfees/page_host.go` | create | shared plumbing of the two pages |
| `go/internal/web/stayfees/page_i18n.json` | create | page texts (en, cs, vi) |
| `go/internal/web/stayfees/page_i18n_keys.txt` | create | the keys of the catalog |
| `go/internal/web/stayfees/page_list.go` | create | the list handler |
| `go/internal/web/stayfees/page_list_test.go` | create | route tests and the made-up fixtures (brief 1582 reuses them) |
| `go/internal/web/stayfees/pagetemplates/_filter.tmpl` | create | Go twin of the compact `_list_filter.html` |
| `go/internal/web/stayfees/pagetemplates/stay_fees.tmpl` | create | Go twin of stay_fees.html |
| `docs/tasks/1581-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1581-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `grep -cF "def stay_fees_list(request: Request):" App/app/routes/stay_fees.py | tail -1` prints `1`.
   - `grep -cF "def _row_status(row: dict) -> str:" App/app/routes/stay_fees.py | tail -1` prints `1`.
   - `grep -cF "def fee_copy_source(apartment, candidates):" App/app/routes/stay_fees.py | tail -1` prints `1`.
   - `grep -cF "def _ui_period_label(request: Request, cadence: str, month: date) -> str:" App/app/routes/stay_fees.py | tail -1` prints `1`.
   - `grep -cF "def _list_return(request: Request) -> str:" App/app/routes/stay_fees.py | tail -1` prints `1`.
   - `grep -cF "def owner_periods(owner_user_id, month: date) -> List[Dict[str, Any]]:" App/app/stay_fee.py | tail -1` prints `1`.
   - `grep -cF "func Routes(pool *pgxpool.Pool" go/internal/web/stayfees/handlers.go | tail -1` prints `1`.
   - `grep -cF "func (d deps) enter(" go/internal/web/stayfees/handlers.go | tail -1` prints `1`.
   - `grep -cF "func feeCopySource(" go/internal/web/stayfees/helpers.go | tail -1` prints `1`.
   - `grep -cF "func feeReturnPath(" go/internal/web/stayfees/helpers.go | tail -1` prints `1`.
   - `grep -cF "func MustParseFuncs(" go/internal/hostweb/layout/pagefuncs.go | tail -1` prints `1`.
   - `grep -cF "func PropertyPeriod(" go/internal/stayfee/loader.go | tail -1` prints `1`.
   - `grep -cF "func LoadIssueContext(" go/internal/stayfee/loader.go | tail -1` prints `1`.
   - `grep -cF "func QRDataURI(" go/internal/payments/qrdatauri.go | tail -1` prints `1`.
   - `ls go/internal/web/stayfees/page_host.go 2>&1 | tail -1` says "No such file" (nothing of this brief exists yet).
   - `find docs/tasks/1581-files -name '*.txt' | wc -l | tail -1` prints `9`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1581-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -9
   beafe135776a8fd100a4ed184a7218c700478d334e522257c7e0b2266a9d13ed  go/cmd/ubyhost-web/register_web_stayfees_pages.go
   a7c4b03ea981a82c3fa5858eb63e4f888b4b4ee15a6007ba005aaaef7355a373  go/cmd/ubyhost-web/register_web_stayfees_pages_test.go
   842a8a5e752b9cde4cacbc7752a296b9ea88d62afd200b0a99657c88739e6153  go/internal/web/stayfees/page_host.go
   cd91fb7bc797cdec952e1dc77e5f8cc3ebeac6790b3598fc4e004dbfc49af81b  go/internal/web/stayfees/page_i18n.json
   35e6f2f9e19de6da8d96e5a77694b2823a17f75e532afa96d040176c6426bb90  go/internal/web/stayfees/page_i18n_keys.txt
   e4ff57bc5c53e6181b15829e092059d8f91d8fa9c324a554aca3e98ddbaabafc  go/internal/web/stayfees/page_list.go
   ee3c483a0f7ce68b4e69de4717567a88505e5f1349ad0047e61ad9e26cea6984  go/internal/web/stayfees/page_list_test.go
   f0bea2d8b8dc45002b0861badee5f67c0beb058e55ff414ff1220d471bd9aece  go/internal/web/stayfees/pagetemplates/_filter.tmpl
   5c8dfca4d928e67705edfd078aae3df83356f0cd654f83eac4973b33d61f0777  go/internal/web/stayfees/pagetemplates/stay_fees.tmpl
   EOF
   ```

   Every line must end with `: OK`. Then commit "1581 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/stayfees cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/stayfees/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all (gofmt lists nothing, build and vet are silent). Anything printed: STOP (§8). Nothing changed, so no commit.

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if it is already running (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55581/data status' | tail -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55581 && chown postgres /var/tmp/pg55581 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55581/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55581/data -o "-p 55581 -k /var/tmp/pg55581" -l /var/tmp/pg55581/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55581/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55581/postgres go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
   ```

   Expected: two lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stayfees	<seconds>s` and `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	<seconds>s`. The golden test of brief 1330 (`TestActionsMatchPython`) is part of the first package and must stay green. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55581/postgres go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestPageListPage$|^TestPageListReturnKeepsFilters$|^TestPageRowStatus$|^TestPageHelpers$|^TestStayFeesListPageRegistered$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of 5 tests (times differ) and two final `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestPageListPage (0.NNs)
   --- PASS: TestPageListReturnKeepsFilters (0.NNs)
   --- PASS: TestPageRowStatus (0.NNs)
   --- PASS: TestPageHelpers (0.NNs)
   --- PASS: TestStayFeesListPageRegistered (0.NNs)

   Report the number of `--- SKIP` lines of the whole two packages: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55581/postgres go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` must print `0`.

5. Write the report (§9), set `Status: review` in this file and commit "1581 step 5". Do not open a PR (one big PR mode); the owner or the orchestrator opens it with the PR text of §2.

## 5. Do not touch

`App/` (no Python file changes; the Python routes stay the live ones), `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, `go/internal/web/stayfees/handlers.go`, `i18n.json`, `helpers.go`, `go/cmd/ubyhost-web/register_web_stayfees.go` and every other existing file. Hard rules of AGENTS.md: no secret or guest datum in a file or a log (the test data is made up), nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 2 and 4). No test-map row exists yet for `go/internal/web/stayfees` host pages; the coordinator adds one from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 9 files.
- [ ] The format, build and vet step printed nothing.
- [ ] The test step printed `ok` for both packages, each of the 5 named tests printed `--- PASS` (none `SKIP`, none `FAIL`) on PostgreSQL, and the SKIP count is 0.
- [ ] `git log --oneline --grep='^1581 step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1581 step') | tail -40` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed to `main`.
- [ ] UI: not applicable in this PR (rules 7 and 10): the page is dormant (no path routes to it) and the Python-side browser tests cannot reach the Go service. The UX gate of rule 10 (`test_layout_lint_browser.py`, the 390, 768 and 1280 px screenshots of the page, a line per page in the PR) runs on staging before the owner adds the path; see Owner steps.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor, a hash or a file count of step 0 or step 1 is not as stated;
- a test fails twice (read the last 30 lines, fix nothing in the sidecar files yourself: report);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1581-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git diff --stat` as in §7).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of: `page_list.go` (the apartment query is scoped by `owner_user_id`; the rows of other hosts never reach the template; `pgFilterContext` only offers the host's own properties), `page_host.go` (`pgOwnerPeriods` is scoped by owner; `pgQrOf` draws the QR from a stored IBAN only), the two templates (every form has `_csrf`; the pay QR `src` is a `template.URL` built by the handler, never from the request).

## Owner steps

None: nothing is switched on. When the whole `/stay-fees` area is in Go (briefs 1581, 1582 and the ones for `pdf`, `pdfs.zip`, `finalize`, `confirm-ready`, `adjustment`, `guest-pay-preview`), the owner adds `/stay-fees` to `UBYHOST_GO_PATHS` after the UX gate ran on staging.
