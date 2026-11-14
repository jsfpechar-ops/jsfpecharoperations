# 1570: Go cleaning host pages, part 1: the layout, the schedule page, the add and edit forms, the property list

Status: review
Depends on: none (brief 1310 and its fix are on this branch) | Base commit: current tip of the working branch | Branch: task/1570-go-cleaning-host-pages
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1570 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1570 step'` and `git show --stat <commit>`, never a fixed base commit.

## 1. Objective

Add the host layout plumbing for the cleaning area to `go/internal/web/cleaning` and four read-only pages of `App/app/routes/cleaning.py`: the schedule page (`GET /cleaning`), the add form (`GET /cleaning/new`), the edit form (`GET /cleaning/events/{id}/edit`) and the property list (`GET /cleaning/properties`). The code is dormant until the owner routes the paths; it is the base the briefs 1571 to 1573 build on.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (cleaning pages only); 2 privacy: no new personal-data field, no new retention line, no outbound request; 3 fixtures are made up (`@example.test`, test-only keys); 4 no new dependency (stdlib, pgx and packages already in `go.mod`); 5 plain PostgreSQL through `pgxpool`, the Python SQL with `$n` placeholders, no schema change; 6 light mode, the forms work without JavaScript; 11 Go first (this brief is the Go port; no file under `App/app/` changes).

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The pages read the host's own cleaning rows (the note is decrypted for the owner only, as Python does) and `reconcile` writes `cleaning_event` rows exactly as the Python page view does.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1570-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `251a5eced8ba6df29594b18f35ba1c10f4b3a33de41607b1918e9d519a002797` | `go/cmd/ubyhost-web/register_web_cleaning_host.go` | create | 21 |
| `9cdfaab4cc44007b12c57c39fb072803e1a21422918160ca3f66e1fdd8953b14` | `go/cmd/ubyhost-web/register_web_cleaning_host_test.go` | create | 24 |
| `a2c07de76c267ac7be92905393d216831f2156cf02a962dc76a31c15b24b7f33` | `go/internal/web/cleaning/host.go` | create | 347 |
| `a14d9b93fcdd8fb15a0ee31362ab2e0afcb1cc78179420358bcab8abea22c3cb` | `go/internal/web/cleaning/host_data.go` | create | 46 |
| `8e247056d3a490fa5a55e4ea34f6111234f607f4a5eeecd6a4c697992c08bd7e` | `go/internal/web/cleaning/host_test.go` | create | 292 |
| `46019efc2f28f964239a2edf72c5e27592b2372323bdb0012b8cdaf789ba5b79` | `go/internal/web/cleaning/hosttemplates/_calendar.tmpl` | create | 91 |
| `b2401a6ac181f465713c28f735fcde8057e3c6209406bc2b8527e5116763bbbd` | `go/internal/web/cleaning/hosttemplates/cleaning.tmpl` | create | 17 |
| `d460b2ec2eaa5f50a6fe27d8cb746f7b1e8dd0de3e06d4395f1a41394b5cfcc1` | `go/internal/web/cleaning/hosttemplates/cleaning_edit.tmpl` | create | 21 |
| `a534cb736a4b0889fcd9eb8b3bef33b0441ac8c86371696b2d9bbe950c793e8f` | `go/internal/web/cleaning/hosttemplates/cleaning_properties.tmpl` | create | 8 |

**How the code is built (for the reviewer; the executor reads no Go file, it only copies and runs).** The earlier cleaning brief (1310) ported the five routes that need no host layout (`go/internal/web/cleaning/handler.go`, `model.go`, `render.go`, registered in `register_web_cleaning.go`); those files are not changed. The host pages are new files of the same package. `host.go` has a route table (`hostAdd` called from an `init()` in each file, so the later briefs add routes without editing this file), `RegisterHost`, the login and CSRF helpers in FastAPI's order (CSRF dependency, then the integer path parameter, then `require_login`) and the page renderer, which wraps `hostweb/layout.Render` (nav `cleaning`, `V2`, the page templates in `hosttemplates/`, the page catalog is the calendar and status texts of `i18n.json` "host"). The schedule page reuses the existing `buildPayload` (it also gives the HTML of the cleaning table) and a host variant of the dashboard calendar (`_calendar.tmpl`, copied from the read-only one of the shared page with the host differences of `_dashboard_calendar.html`: `data-readonly="false"`, the add-type buttons, the stay form posting to `/reservations` with a CSRF token, the hint text). `go/cmd/ubyhost-web/register_web_cleaning_host.go` hands the table to `registerRoutes`. The existing test `register_web_cleaning_test.go` asserted that `GET /cleaning`, `GET /cleaning/shares` and `POST /cleaning/events` fall to the catch-all; step 2 removes those three rows (the new registration tests of this and the next briefs assert the new patterns).

**Parity notes (Python `App/app/routes/cleaning.py` unless named):**

| Route | Python | Go |
|---|---|---|
| `GET /cleaning` | `index` 128-144, `_period` 80-84, `_payload` 101-121, `_sections` 87-98, templates `cleaning.html`, `_cleaning_screen.html`, `_cleaning_calendar.html`, `_dashboard_calendar.html` | `(*hostServer).index`, `period`, `hosttemplates/cleaning.tmpl` and `_calendar.tmpl`; the data comes from the existing `buildPayload` |
| `GET /cleaning/new` | `new_event` 165-173, `_editor` 160-162, template `cleaning_edit.html` | `(*hostServer).newEvent`, `(*hostServer).editor`, `hosttemplates/cleaning_edit.tmpl` |
| `GET /cleaning/events/{id}/edit` | `edit_event` 204-213 (`reconcile`, `_event`, state must be `scheduled`, note decrypted) | `(*hostServer).editEvent`, `eventFor` |
| `GET /cleaning/properties` | `choose_property` 265-271, template `cleaning_properties.html` | `(*hostServer).chooseProperty`, `hosttemplates/cleaning_properties.tmpl` |

Details that are easy to get wrong and are tested: `from`, else `cal_date`, else today starts the window and `to` defaults to 30 days later; any bad date, range outside 1 to 370 days or non-numeric `property` answers `422 {"detail":"Invalid cleaning range"}`, a property that is not the host's (or archived) `404`; a `notice` query value is shown through `ct()` (an unknown key is its own text, escaped); the page is the host layout with `nav` cleaning, `body_kind` list, no page header (the h1 slot is empty, as Python blanks `page_title`); the editor of a cleaning that came from a booking shows the property read-only; a cleaning that is not `scheduled` or belongs to another host is `404`; `GET /cleaning/new` keeps `?date` and `?property` (present but empty stays empty).

**Known differences from Python, shared by every Go web area (not fixed here):** a missing or foreign record answers `404 {"detail":"Not Found"}` (and a non-integer id `422`), where Python shows the branded error page to a browser; `HEAD` is served by the `GET` pattern; a repeated query key reads the last value in the code written here (as Starlette does) but the older `buildPayload` reads the first. Python's `int()` also accepts `1_0` and a leading `+`; Go's parser accepts the sign only.

**Paths that become fully served by Go (Python methods all in Go):** `/cleaning` (GET), `/cleaning/new` (GET), `/cleaning/events/*/edit` (GET), `/cleaning/properties` (GET), plus the five paths brief 1310 already covered. **Not yet:** every path with a POST in Python (`/cleaning/events`, `/cleaning/events/*`, `/cleaning/properties/*`, `/cleaning/shares`) until the briefs 1571 to 1573 are merged. **Assumption:** no `/cleaning` path is in `UBYHOST_GO_PATHS` today (the 1310 note only proposed it). If the owner already added a prefix such as `/cleaning/events/*`, `GET /cleaning/events/*/edit` goes live the moment this deploys.

**Anchors that must exist verbatim** (step 0): the Python function lines and the Go function lines listed there.

**Verified by the brief writer** (in a throwaway worktree of this branch, with the steps of briefs 1570 to 1570 applied exactly and in order, sidecars copied as step 1 does): `gofmt -l` printed nothing, `go build ./...` and `go vet ./internal/web/cleaning/... ./cmd/...` were silent, and `go test ./internal/web/cleaning/... ./cmd/ubyhost-web/... -count=1` passed on PostgreSQL 16, with the golden test of brief 1310 still green and the named tests PASS. The tests cover: the schedule page (calendar attributes, add-type buttons, `/reservations` form with a CSRF token, the list HTML, another owner's and an archived property absent, `notice` shown and escaped, `cal_date` and the 30-day default, Czech from the language cookie), its errors (foreign, archived, text, malformed and impossible dates, empty and too long range, signed out), the add form (`date` and `property` kept, no revision field), the edit form (a booking-based cleaning with the property read-only and the decrypted note, a hand-made one with the select, a foreign, missing, text, dismissed and archived-property id, signed out), the property list, every template key in all three languages, and the registration patterns.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_cleaning_host.go` | create | hands the host routes to `registerRoutes` |
| `go/cmd/ubyhost-web/register_web_cleaning_host_test.go` | create | route registration test |
| `go/internal/web/cleaning/host.go` | create | route table, `RegisterHost`, login/CSRF helpers, page renderer, schedule page, add and edit forms, property list |
| `go/internal/web/cleaning/host_data.go` | create | `eventFor`, `homeFor` (owner scope) |
| `go/internal/web/cleaning/host_test.go` | create | route tests, shared test helpers, template key test |
| `go/internal/web/cleaning/hosttemplates/_calendar.tmpl` | create | host variant of the dashboard calendar |
| `go/internal/web/cleaning/hosttemplates/cleaning.tmpl` | create | Go twin of cleaning.html |
| `go/internal/web/cleaning/hosttemplates/cleaning_edit.tmpl` | create | Go twin of cleaning_edit.html |
| `go/internal/web/cleaning/hosttemplates/cleaning_properties.tmpl` | create | Go twin of cleaning_properties.html |
| `go/cmd/ubyhost-web/register_web_cleaning_test.go` | edit | remove 3 rows (step 2) |
| `docs/tasks/1570-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1570-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `grep -cF "def index(request: Request):" App/app/routes/cleaning.py | tail -1` prints `1`.
   - `grep -cF "def new_event(request: Request):" App/app/routes/cleaning.py | tail -1` prints `1`.
   - `grep -cF "def edit_event(request: Request, event_id: int):" App/app/routes/cleaning.py | tail -1` prints `1`.
   - `grep -cF "def choose_property(request: Request):" App/app/routes/cleaning.py | tail -1` prints `1`.
   - `grep -cF "func buildPayload(" go/internal/web/cleaning/handler.go | tail -1` prints `1`.
   - `grep -cF "func parseLimitedForm(" go/internal/web/cleaning/handler.go | tail -1` prints `1`.
   - `grep -cF "func properties(" go/internal/web/cleaning/model.go | tail -1` prints `1`.
   - `grep -cF "func reconcile(" go/internal/web/cleaning/model.go | tail -1` prints `1`.
   - `grep -cF "func registerWebCleaning(" go/cmd/ubyhost-web/register_web_cleaning.go | tail -1` prints `1`.
   - `grep -cF '{http.MethodGet, "/cleaning", "/"},' go/cmd/ubyhost-web/register_web_cleaning_test.go | tail -1` prints `1`; the same for `'{http.MethodGet, "/cleaning/shares", "/"},'` and `'{http.MethodPost, "/cleaning/events", "/"},'`.
   - `ls go/internal/web/cleaning/host.go 2>&1 | tail -1` says "No such file" (nothing of this brief exists yet).
   - `find docs/tasks/1570-files -name '*.txt' | wc -l | tail -1` prints `9`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1570-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   251a5eced8ba6df29594b18f35ba1c10f4b3a33de41607b1918e9d519a002797  go/cmd/ubyhost-web/register_web_cleaning_host.go
   9cdfaab4cc44007b12c57c39fb072803e1a21422918160ca3f66e1fdd8953b14  go/cmd/ubyhost-web/register_web_cleaning_host_test.go
   a2c07de76c267ac7be92905393d216831f2156cf02a962dc76a31c15b24b7f33  go/internal/web/cleaning/host.go
   a14d9b93fcdd8fb15a0ee31362ab2e0afcb1cc78179420358bcab8abea22c3cb  go/internal/web/cleaning/host_data.go
   8e247056d3a490fa5a55e4ea34f6111234f607f4a5eeecd6a4c697992c08bd7e  go/internal/web/cleaning/host_test.go
   46019efc2f28f964239a2edf72c5e27592b2372323bdb0012b8cdaf789ba5b79  go/internal/web/cleaning/hosttemplates/_calendar.tmpl
   b2401a6ac181f465713c28f735fcde8057e3c6209406bc2b8527e5116763bbbd  go/internal/web/cleaning/hosttemplates/cleaning.tmpl
   d460b2ec2eaa5f50a6fe27d8cb746f7b1e8dd0de3e06d4395f1a41394b5cfcc1  go/internal/web/cleaning/hosttemplates/cleaning_edit.tmpl
   a534cb736a4b0889fcd9eb8b3bef33b0441ac8c86371696b2d9bbe950c793e8f  go/internal/web/cleaning/hosttemplates/cleaning_properties.tmpl
   EOF
   ```

   Every line must end with `: OK`. Then commit "1570 step 1".

2. Remove three rows from the existing registration test (one call, repo root). The script stops with an assertion error if a row is not found exactly once:

   ```bash
   python3 - <<'EOF'
   p = 'go/cmd/ubyhost-web/register_web_cleaning_test.go'
   s = open(p).read()
   for line in ['\t\t{http.MethodGet, "/cleaning", "/"},\n', '\t\t{http.MethodGet, "/cleaning/shares", "/"},\n', '\t\t{http.MethodPost, "/cleaning/events", "/"},\n']:
       assert s.count(line) == 1, line
       s = s.replace(line, '')
   open(p, 'w').write(s)
   EOF
   git diff --stat | tail -3
   ```

   Expected: `go/cmd/ubyhost-web/register_web_cleaning_test.go | 3 ---` and `1 file changed, 3 deletions(-)`. Commit "1570 step 2".

3. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/cleaning cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/cleaning/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all (gofmt lists nothing, build and vet are silent). Anything printed: STOP (§8). Nothing changed, so no commit.

4. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if an earlier brief of this series left it running (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55570/data status' | tail -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55570 && chown postgres /var/tmp/pg55570 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55570/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55570/data -o "-p 55570 -k /var/tmp/pg55570" -l /var/tmp/pg55570/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55570/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 5.

5. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55570/postgres go test ./internal/web/cleaning/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: two lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/cleaning	<seconds>s` and `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	<seconds>s`. The golden test of brief 1310 (`TestCleaningMatchesPython`) is part of the first package and must stay green. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55570/postgres go test ./internal/web/cleaning/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestHostIndexPage$|^TestHostIndexErrors$|^TestHostNewEvent$|^TestHostEditEvent$|^TestHostChooseProperty$|^TestPyHelpers$|^TestHostTemplatesUseKnownKeys$|^TestCleaningRoutesRegistered$|^TestCleaningHostRoutesRegistered$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of 9 tests (times differ) and two final `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestHostIndexPage (0.NNs)
   --- PASS: TestHostIndexErrors (0.NNs)
   --- PASS: TestHostNewEvent (0.NNs)
   --- PASS: TestHostEditEvent (0.NNs)
   --- PASS: TestHostChooseProperty (0.NNs)
   --- PASS: TestPyHelpers (0.NNs)
   --- PASS: TestHostTemplatesUseKnownKeys (0.NNs)
   --- PASS: TestCleaningRoutesRegistered (0.NNs)
   --- PASS: TestCleaningHostRoutesRegistered (0.NNs)

6. Write the report (§9), set `Status: review` in this file and commit "1570 step 6". Do not open a PR (one big PR mode); the owner or the orchestrator opens it with the PR text of §2.

## 5. Do not touch

`App/` (no Python file changes; the Python routes stay the live ones), `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, every other file under `go/` (live code: `go/internal/hostweb/`, `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, and in this package `handler.go`, `model.go`, `render.go`, `i18n.go`, `i18n.json`, `templates/`, the golden test and its data). Hard rules of AGENTS.md: no secret or guest datum in a file or a log (the test data is made up), nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 3 and 5). No test-map row exists yet for `go/internal/web/cleaning` host pages; the coordinator adds one from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 9 files.
- [ ] Step 2 changed only `go/cmd/ubyhost-web/register_web_cleaning_test.go` (3 deletions).
- [ ] The format, build and vet step printed nothing.
- [ ] The test step printed `ok` for both packages, and each of the 9 named tests printed `--- PASS` (none `SKIP`, none `FAIL`) on PostgreSQL.
- [ ] `git log --oneline --grep='^1570 step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1570 step') | tail -40` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed to `main`.
- [ ] UI: not applicable in this PR (rules 7 and 10): the pages are dormant (no path routes to them) and the Python-side browser tests cannot reach the Go service. The UX gate of rule 10 (`test_layout_lint_browser.py`, the 390, 768 and 1280 px screenshots of each page, a line per page in the PR) runs on staging before the owner adds the paths; see Owner steps.

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

Write `docs/tasks/1570-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git diff --stat` as in §7).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of: `host.go` (`index`: error mapping and that nothing is shown to another owner; `editEvent`: owner scope through `eventFor`, the `scheduled` check, the decrypted note; `RegisterHost`), `host_data.go` (`eventFor` and `homeFor` both scope by `owner_user_id IS NOT DISTINCT FROM` and the active, not archived rule), `hosttemplates/_calendar.tmpl` (the form posts to `/reservations`, as Python; the CSRF value is `{{csrf}}`), `hosttemplates/cleaning_edit.tmpl` (every form has `_csrf`). In the existing file `register_web_cleaning_test.go` only three rows are removed.

## Owner steps

None: nothing is switched on. The path switch for the whole area is described in the owner steps of brief 1573 and must wait for it.
