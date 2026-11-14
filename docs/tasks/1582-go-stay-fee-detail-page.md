# 1582: Go stay fee host pages, part 2: the property detail page GET /stay-fees/{apartment_id}

Status: review
Depends on: 1581, 1240, 1240a, 1242, 1330, 1330-fix-1, 1380, 1381, 1543 | Base commit: current tip of the working branch | Branch: task/1582-go-stay-fee-detail-page
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1582 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1582 step'` and `git show --stat <commit>`, never a fixed base commit.

## 1. Objective

Add the stay fee detail page `GET /stay-fees/{apartment_id}` (one property, one month: figures, blockers, send panel, payment panel with the QR, guest lines with the exempt decisions, corrections) to `go/internal/web/stayfees`, inside the Go host layout. It reuses the plumbing of brief 1581. Dormant until the owner routes the path.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (the page only reads; its forms post to routes that exist in Python or in brief 1330); 2 privacy: no new personal-data field, no new retention line, no outbound request; the guest's birth date and age are shown for display only and are not stored; 3 fixtures are made up (`@example.test`, test-only keys); 4 no new dependency; 5 plain PostgreSQL through `pgxpool`, no schema change; 6 light mode, every form works without JavaScript; 11 Go first (this brief is the Go port; no file under `App/` changes).

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The birth date shows only where the Python page shows it: for an admin, for a host in their own workspace, and for a guest the admin revealed while impersonating (`access.identity_visible`).

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1582-files/<repo path>.txt`. Step 1 copies them (one of them replaces a file of brief 1581); never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `f6a232af905af6f90c5f9c347b1920848b0942ab4aeaf946b75bdc1a7a870a42` | `go/cmd/ubyhost-web/register_web_stayfees_pages_test.go` | replace (brief 1581 made it) | 40 |
| `5b596f06f49133ae0ca80485528f65b53f208b35e439e8641664f6c4e54c3f4e` | `go/internal/web/stayfees/page_detail.go` | create | 510 |
| `1b3cabdaf39b145851ff935d3eb9600ba273f5ee4983fedd288acf1202ea209f` | `go/internal/web/stayfees/page_detail_test.go` | create | 158 |
| `e52336ede2514dc1e16b958992569d3720cdc094f233c5f153ca916192a8a427` | `go/internal/web/stayfees/pagetemplates/stay_fee_detail.tmpl` | create | 308 |

**How the code is built.** `page_detail.go` registers its route in `init()` through `pageAdd` of brief 1581 (so `PageRoutes` now returns both pages). The handler follows `stay_fee_detail` line by line: the path id is checked first (422 for text, before the login, as FastAPI does), then the login; a month after the current one redirects (303) to the default month; a foreign or missing property answers `404 {"detail":"Not Found"}`; a property with no fee and no sealed filing goes back to the list with the "no such apartment" error; `?correct=1` with a sealed filing recomputes the live period at the sealed cadence and rate (`stayfee.CorrectionRate`); a sealed, not corrected period is shown frozen. The figures, the issues and the payment details come from `go/internal/stayfee` (`PropertyPeriod`, `ReportGroup`, `ReportIssues`, `LoadIssueContext`, `UnsignedStays`, `PaymentDetails`, `Covering`, `CorrectionRate`, `LoadEntity`). The template defines the page body plus the slots `.back_label`, `.toolbar` (the compact month filter of brief 1581) and `.primary` (the header buttons).

**Parity notes (Python `App/app/routes/stay_fees.py` unless named):**

| Python | Go |
|---|---|
| `stay_fee_detail` 775-848, template `stay_fee_detail.html` | `(deps).pgDetailPage`, `(*call).pgDetail`, `pagetemplates/stay_fee_detail.tmpl` |
| `_operator_line` 849-859 | `pgOperatorLine` |
| `_send_panel_context` 861-878 | `(*call).pgSendPanelFor` |
| `_guest_lines` 880-935 | `(*call).pgGuestLines`, `pgFactsFor`, `pgResidence` |
| `validation.parse_birth_date`, `display_birth_date`, `age_on` | `pgParseBirthDate`, `pgDisplayBirthDate`, `stayfee.AgeOn` |
| `access.identity_visible(request, guest_id)` | `pgGuestIdentityVisible` |
| `_detail_filter` 117-130 | `pgFilterContext` (brief 1581) with no properties and no statuses |
| `validation.country_name` | `countries.Name` |
| `stay_fee_adjustment.active` rows with `filing_id` | `period.Adjustments` plus `(*call).pgAdjustmentViews` (marks the ones a filing took: no undo button) |

Details that are easy to get wrong and are tested: the `<title>` and heading are "Name (period)" in the host's language; the header shows the saved badge with the CSV, PDF and "correct" buttons for a sealed period, the save form (with `confirm_collected` and one `collected_<guest id>` per line, and `correct=1` while correcting) when there is no blocker, and a disabled button otherwise; each blocker has its fix link (settings for no VS or no authority, the business or the property operator choice for no payer) and the scope ruling form appears only for the scope ruling blocker; the send panel exists for a sealed period only (recipient `Authority (databox)`, the Czech subject `Ohlášení poplatku z pobytu – <period> – <property>`, the Czech body with the operator line, the period and `Částka k úhradě: <amount>. Podrobnosti v příloze.`); the payment panel shows the account, IBAN and variable symbol copy fields and the QR only for a sealed period with a council IBAN; a guest line shows birth date (only when visible), age at check-in, nationality in the host's language, a local-resident hint (Czech guest from the property's town with a host decision) or the automatic-resident help tip, and a decision form unless the line is `not_subject`; the reason select is `required` for an automatic minor and for a local-resident hint; the adjustment form and list are shown for a live period only and an adjustment that a filing took has no undo button.

**Known differences from Python (not fixed here):** there is no Python golden for this page (the Python app cannot be started where this brief was written, no FastAPI), so the tests check the texts, forms, links and counts of made-up rows; a missing or foreign property answers `404 {"detail":"Not Found"}` where Python shows the branded error page to a browser (the same difference as every Go web area); a sealed line whose payload has no residence keys makes Go read the guest row (Python reads it when the key `res_country` is absent; Go cannot tell an absent key from an empty value, so a sealed line with both empty also reads the row, which gives the same result unless the guest changed since); `HEAD` is served by the `GET` pattern; the schedule day is the UTC date (as `stayfeemail`).

**Paths that become fully served by Go:** none (see brief 1581). `GET /stay-fees/{id}` and `GET /stay-fees` are both in Go after this brief, but `pdf`, `pdfs.zip`, `finalize`, `confirm-ready`, `adjustment` (POST) and `guest-pay-preview` are not yet. The mux keeps `GET /stay-fees/pdfs.zip` away from the detail pattern: the test registers a stand-in for it next to the pages and checks it wins. **Goes live on deploy if** `/stay-fees/*` is already routed to Go (assumed not).

**Anchors that must exist verbatim** (step 0): the Python function lines and the Go function lines listed there.

**Verified by the brief writer** (in a throwaway copy of the working branch tip with the steps of briefs 1581 and 1582 applied exactly and in order, sidecars copied as step 1 does): `gofmt -l` printed nothing, `go build ./...` and `go vet ./internal/web/stayfees/... ./cmd/...` were silent, and `go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1` passed on PostgreSQL 16 with 0 skipped tests; the golden test `TestActionsMatchPython` of brief 1330 stayed green and the five named tests PASS. The tests cover: a live period ready to save (metrics, save form with collected amounts, guest facts, decisions, the required reason for the minor and the local resident, the adjustment form, the open correction with its undo and the sealed one without), a blocked property (every fix link, the scope ruling form, the disabled button), a running quarter, a sealed period (download links, send panel, payment panel with the QR and SPAYD text, records forms, the sealed line with facts read from the guest row), the corrected sealed period, and every refusal (foreign, missing, huge and text ids, signed out, future month, bad month, no fee and no filing), plus the identity rule and the birth date helpers.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_stayfees_pages_test.go` | replace | registration test of both pages and the `pdfs.zip` check |
| `go/internal/web/stayfees/page_detail.go` | create | the detail handler and its helpers |
| `go/internal/web/stayfees/page_detail_test.go` | create | route tests (the fixtures are in `page_list_test.go` of brief 1581) |
| `go/internal/web/stayfees/pagetemplates/stay_fee_detail.tmpl` | create | Go twin of stay_fee_detail.html |
| `docs/tasks/1582-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1582-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `git log --oneline --grep='^1581 step' | wc -l | tail -1` prints a number of 1 or more (brief 1581 is on this branch).
   - `sha256sum go/internal/web/stayfees/page_host.go | cut -c1-64 | tail -1` prints `842a8a5e752b9cde4cacbc7752a296b9ea88d62afd200b0a99657c88739e6153` (the file of brief 1581, unchanged).
   - `sha256sum go/internal/web/stayfees/page_list_test.go | cut -c1-64 | tail -1` prints `ee3c483a0f7ce68b4e69de4717567a88505e5f1349ad0047e61ad9e26cea6984`.
   - `grep -cF "def stay_fee_detail(apartment_id: int, request: Request):" App/app/routes/stay_fees.py | tail -1` prints `1`.
   - `grep -cF "def _operator_line(apartment) -> str:" App/app/routes/stay_fees.py | tail -1` prints `1`.
   - `grep -cF "def _send_panel_context(apartment, period, group, filing_row: dict) -> dict:" App/app/routes/stay_fees.py | tail -1` prints `1`.
   - `grep -cF "def _guest_lines(apartment, period):" App/app/routes/stay_fees.py | tail -1` prints `1`.
   - `grep -cF "func CorrectionRate(" go/internal/stayfee/filing.go | tail -1` prints `1`.
   - `grep -cF "func Covering(" go/internal/stayfee/filing.go | tail -1` prints `1`.
   - `grep -cF "func LoadEntity(" go/internal/stayfee/loader.go | tail -1` prints `1`.
   - `grep -cF "func Name(" go/internal/countries/countries.go | tail -1` prints `1`.
   - `grep -cF "func (c *call) noSuchApartment() {" go/internal/web/stayfees/handlers.go | tail -1` prints `1`.
   - `grep -cF "func pageAdd(" go/internal/web/stayfees/page_host.go | tail -1` prints `1`.
   - `ls go/internal/web/stayfees/page_detail.go 2>&1 | tail -1` says "No such file" (nothing of this brief exists yet).
   - `find docs/tasks/1582-files -name '*.txt' | wc -l | tail -1` prints `4`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1582-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -4
   f6a232af905af6f90c5f9c347b1920848b0942ab4aeaf946b75bdc1a7a870a42  go/cmd/ubyhost-web/register_web_stayfees_pages_test.go
   5b596f06f49133ae0ca80485528f65b53f208b35e439e8641664f6c4e54c3f4e  go/internal/web/stayfees/page_detail.go
   1b3cabdaf39b145851ff935d3eb9600ba273f5ee4983fedd288acf1202ea209f  go/internal/web/stayfees/page_detail_test.go
   e52336ede2514dc1e16b958992569d3720cdc094f233c5f153ca916192a8a427  go/internal/web/stayfees/pagetemplates/stay_fee_detail.tmpl
   EOF
   ```

   Every line must end with `: OK`. Then commit "1582 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/stayfees cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/stayfees/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all (gofmt lists nothing, build and vet are silent). Anything printed: STOP (§8). Nothing changed, so no commit.

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if an earlier brief of this series left it running (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55581/data status' | tail -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55581 && chown postgres /var/tmp/pg55581 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55581/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55581/data -o "-p 55581 -k /var/tmp/pg55581" -l /var/tmp/pg55581/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55581/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55581/postgres go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
   ```

   Expected: two lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stayfees	<seconds>s` and `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	<seconds>s`. The tests of brief 1581 and the golden test of brief 1330 are part of the first package and must stay green. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55581/postgres go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestPageDetailPage$|^TestPageDetailRefusals$|^TestPageGuestIdentityVisible$|^TestPageDetailHelpers$|^TestStayFeesPagesRegistered$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of 5 tests (times differ) and two final `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestPageDetailPage (0.NNs)
   --- PASS: TestPageDetailRefusals (0.NNs)
   --- PASS: TestPageGuestIdentityVisible (0.NNs)
   --- PASS: TestPageDetailHelpers (0.NNs)
   --- PASS: TestStayFeesPagesRegistered (0.NNs)

   Report the number of `--- SKIP` lines of the whole two packages: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55581/postgres go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` must print `0`.

5. Write the report (§9), set `Status: review` in this file and commit "1582 step 5". Do not open a PR (one big PR mode); the owner or the orchestrator opens it with the PR text of §2.

## 5. Do not touch

`App/` (no Python file changes; the Python routes stay the live ones), `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, every file of brief 1581 other than the one test file this brief replaces, `go/internal/web/stayfees/handlers.go`, `i18n.json`, `helpers.go`, `go/cmd/ubyhost-web/register_web_stayfees.go` and every other existing file. Hard rules of AGENTS.md: no secret or guest datum in a file or a log (the test data is made up), nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 2 and 4). No test-map row exists yet for `go/internal/web/stayfees` host pages; the coordinator adds one from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 4 files.
- [ ] The format, build and vet step printed nothing.
- [ ] The test step printed `ok` for both packages, each of the 5 named tests printed `--- PASS` (none `SKIP`, none `FAIL`) on PostgreSQL, and the SKIP count is 0.
- [ ] `git log --oneline --grep='^1582 step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1582 step') | tail -40` lists only the paths of §3 and the sidecars.
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

Write `docs/tasks/1582-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git diff --stat` as in §7).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of: `page_detail.go` (`pgDetail`: the 404 for a foreign property comes before any other read of the property; `pgFactsFor` reads only the ids of the lines of this property; the birth date is shown only through `pgGuestIdentityVisible`; nothing is written), `stay_fee_detail.tmpl` (every form has `_csrf`; the decision, scope ruling, finalize, adjustment and record forms post to routes that already exist), `pgSendPanelFor` (the texts are built from the stored operator and property names, escaped by `html/template`).

## Owner steps

None: nothing is switched on. The switch for the whole `/stay-fees` area is described in the owner steps of brief 1581 and must wait for the briefs that port the other `/stay-fees` routes.
