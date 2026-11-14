# 1595: Go onboarding part 2: the checklist page (GET /onboarding)

Status: todo
Depends on: none (brief 1290 and the host layout 1380/1381 are on this branch; verified on go-wave3 at 859d114d5) | Base commit: current tip of the working branch | Branch: task/1595-go-onboarding-checklist-page
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (exact files; fresh Fable review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1595 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1595 step'` and `git show --stat <commit>`, never a fixed base commit.

## 1. Objective

Port `onboarding_view` (`App/app/routes/onboarding.py` 47-53, template `onboarding.html`, the `_components.html` macros `onboarding_welcome` and `onboarding_finish`, and the part of `onboarding.progress` in `App/app/onboarding.py` 125-251 the page reads) to the existing Go package `go/internal/web/onboarding`, and register `GET /onboarding` in ubyhost-web. The route is dormant: nothing is added to `UBYHOST_GO_PATHS`.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (a read-only checklist page; the UbyPort check is the existing `validation.ValidateApartment` port); 2 privacy: no new personal-data field, no retention line, no outbound request; 3 fixtures are made up (`@example.test`, test-only keys); 4 no new dependency (stdlib, pgx and packages already in `go.mod`); 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, no schema change; 6 light mode, every form works without JavaScript (see "CSRF field" below); 11 Go first: this brief is the Go port. The two files under `App/` are **go-first exception 1** (port plumbing: a golden script and its parity test); no Python application file changes.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The page reads the workspace's own entities, properties, feeds and stays, as Python does. The one write is Python's too: a finished single property without a guest-link slug gets one (`guest_slug.ensure`, already ported in `go/internal/palette`).

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1595-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `61e98a73225129d15b23416420626524d43ceec89dfb2307257a446809ed58e0` | `go/internal/palette/linkkey.go` | create | 15 |
| `7210470ddc6cf2b6cf5be33d3e3ecb77b49eb4de7dad1c98f4428dc8d61fb484` | `go/internal/web/onboarding/onboarding_page.go` | create | 324 |
| `d41c37bdef5b3fc29a490d9f3dc2f6a412b839d2d5da013ff1303c69d41df97a` | `go/internal/web/onboarding/onboarding_page_test.go` | create | 356 |
| `9d40f2e8fb056a5e34266b67bfc4d2473035906bf4eb04f839ec5261d71c9340` | `go/internal/web/onboarding/onboardingpage/onboarding.tmpl` | create | 100 |
| `4df45e9993e82c85978031f89d12109ad55405036fd67112b7805ebe28bee572` | `go/internal/web/onboarding/onboardingpage/i18n_keys.txt` | create | 11 |
| `0615c58b2b61356620a36416c639a29dfd1299abd35364b72ed328a5da479504` | `go/internal/web/onboarding/onboardingpage/i18n.json` | create | 209 |
| `58be1f6b3f75dddb35ecdcc33c5fc0627814eb6b3e23c0e1cabba6705b89991d` | `go/internal/web/onboarding/testdata/onboarding_page_golden.json` | create | 2051 |
| `fad243804f84f44b21d81b1d885747537b4626456c2ba5f7c203e3eaceb8188b` | `go/cmd/ubyhost-web/register_web_onboarding_page.go` | create | 24 |
| `fd2170b88340e8a920490c2243f0b09b33515c8f5ef2667c3a42a4648fe36419` | `go/cmd/ubyhost-web/register_web_onboarding_page_test.go` | create | 23 |
| `a320f3d0244af41a23a32d7f0fa0f69014081346e79baef594bf4dc513f258cd` | `App/scripts/go_onboarding_page_golden.py` | create | 238 |
| `9d69854f544b7d30381d21c3b3049d5529bc965ec7f42f747f3afdaed93fdd51` | `App/tests/test_go_onboarding_page_golden.py` | create | 27 |

**How the code is built (for the reviewer; the executor reads no Go file, it only copies and runs).**

- `onboarding_page.go`: `OnboardingPageHandler` is `require_login` (`hostweb.Login`; a GET needs no CSRF) and then `layout.Render` with nav `dashboard`, body_kind `form`, `V2`, title `onboarding.welcome_title` and an empty h1 slot (Python blanks `page_title`). `loadOnboardingPageProgress` is `onboarding.progress` for the values the template reads: the entity count and the "ready" entity count (name, seat, ICO, contact e-mail all non-blank), the non-archived properties of the workspace in id order with their active feed count and current slug, the manual active stays, `validation.ErrorsOnly(validation.ValidateApartment(...))` per property with the web-service password decrypted as `db.decrypt_secret` does (empty for an empty token, a token no data key opens, or a non-UTF-8 plain text; the data keys are loaded only when a token exists), the five steps with Python's URLs, `current`, `completed`, `finished`, the finish card (only for exactly one property; link `PUBLIC_BASE_URL/l/<slug or link_key>`, PIN, passport policy, communication URL) and `dismissed` (`onboarding_dismissed_<workspace>` = "1"). The owner is `session.Host.Workspace.ID` (an admin previewing a workspace sees that workspace, as `access.owner_id`). `demo_available` is `config.UBYPORT_ENV == "mock"`: only an unset `UBYHOST_UBYPORT_ENV` is mock, a set value is lower-cased (so `MOCK` is mock and `""` is not), read through `os.LookupEnv`. Every new name is prefixed `onboardingPage` so it cannot clash with the setup wizard briefs (1599-1604) in the same package; `setup.go` and `routes.go` are not changed (the handler reuses `serverError` of routes.go).
- `onboardingpage/onboarding.tmpl`: the Go twin of the two macros as `onboarding.html` calls them (`v2=true`, `compact=false`, `show_toggle=False`): the help tips, copy buttons and icon come from the layout funcs. **CSRF field:** Python's forms carry no `_csrf` input (its `csrf.js` adds one in the browser); the Go forms carry `<input type="hidden" name="_csrf" value="{{csrf}}">`, so they also work without JavaScript (rule 6). This is the only intended difference in the page area.
- `onboardingpage/i18n_keys.txt` / `i18n.json`: the page catalog, written by `App/scripts/go_host_i18n.py` (its glob finds nested `i18n_keys.txt`). It also lists the `flash.demo.*` and `flash.error.demo_*` keys brief 1596 uses, so 1596 does not edit this brief's files.
- `go/internal/palette/linkkey.go`: a new file in a live package that only exports the existing `linkKey` (`guest_slug.link_key`: the current slug, created by the ported `ensure` if missing, else the permanent token). No existing palette line changes.
- `register_web_onboarding_page.go`: an `init()` that adds `GET /onboarding` through `registerRoutes`, next to the 1290 file `register_web_onboarding.go` (unchanged).
- `App/scripts/go_onboarding_page_golden.py` seeds a throwaway SQLite database (9 accounts covering: empty, entity without ICO and skipped, property without house number plus an archived one, one finished property with a slug, two finished properties, a password no key opens, a finished property without token or PIN, only an iCal stay and a cancelled manual stay), renders `GET /onboarding` through the real FastAPI app in en, cs and vi, with the demo card on and off and with an admin previewing a workspace, and keeps `visible_lines()` of the page area (text plus id, href, action, method, name, value, type, class, aria-label, aria-controls, data-copy, target). `TestOnboardingPageMatchesPython` seeds PostgreSQL from the same file and compares line by line (the Go `_csrf` lines are taken out first and counted: one per form).

**Accepted differences (only reachable with hand-made data or requests):** a property column that holds a non-text value in SQLite is read as text in PostgreSQL; `HEAD /onboarding` is served by the `GET` pattern; Python's 500 page for a browser is a plain 500 text here (same as brief 1290, until the Go error page exists).

**Verified by the brief writer** (in a throwaway copy of go-wave3 at 859d114d5, with the steps of brief 1595 applied exactly as written, sidecars copied as step 1 does): `sha256sum -c` all OK, `gofmt -l` printed nothing, `go build ./...` and `go vet ./internal/web/onboarding/... ./internal/palette/... ./cmd/...` were silent, `go test ./internal/web/onboarding/... ./internal/palette/... ./cmd/ubyhost-web/... -count=1` passed on PostgreSQL 16 with no test skipped (the 1290 tests of the package stay green), and the 5 named tests of step 5 printed `--- PASS`. With `App/.venv`: `tests/test_go_onboarding_page_golden.py`, `tests/test_go_host_i18n.py` and `tests/test_go_onboarding_setup.py` passed (5 passed, 0 skipped).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/palette/linkkey.go` | create | exported `LinkKey` (wraps `linkKey`) |
| `go/internal/web/onboarding/onboarding_page.go` | create | progress port, handler, page render |
| `go/internal/web/onboarding/onboarding_page_test.go` | create | golden parity, slug creation, template keys, seed helpers (1596 reuses them) |
| `go/internal/web/onboarding/onboardingpage/onboarding.tmpl` | create | Go twin of onboarding.html and its two macros |
| `go/internal/web/onboarding/onboardingpage/i18n_keys.txt` | create | page catalog keys |
| `go/internal/web/onboarding/onboardingpage/i18n.json` | create | page catalog (generated, checked in step 3) |
| `go/internal/web/onboarding/testdata/onboarding_page_golden.json` | create | golden written by the Python script |
| `go/cmd/ubyhost-web/register_web_onboarding_page.go` | create | registers `GET /onboarding` |
| `go/cmd/ubyhost-web/register_web_onboarding_page_test.go` | create | route registration test |
| `App/scripts/go_onboarding_page_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_onboarding_page_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1595-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1595-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `grep -cF '@router.get("/onboarding")' App/app/routes/onboarding.py | tail -1` prints `1`.
   - `grep -cF "def progress(owner_user_id: int) -> Dict[str, Any]:" App/app/onboarding.py | tail -1` prints `1`.
   - `grep -cF "{% macro onboarding_welcome(onboarding, compact=False, v2=False) %}" App/app/templates/_components.html | tail -1` prints `1`.
   - `grep -cF "func linkKey(ctx context.Context, pool pgxPool, a apartment) (string, error) {" go/internal/palette/db.go | tail -1` prints `1`.
   - `grep -cF "func ValidateApartment(ap map[string]string) []Issue {" go/internal/validation/validation.go | tail -1` prints `1`.
   - `grep -cF "func serverError(w http.ResponseWriter, err error) {" go/internal/web/onboarding/routes.go | tail -1` prints `1`.
   - `grep -cF "func testPool(t *testing.T) *pgxpool.Pool {" go/internal/web/onboarding/routes_test.go | tail -1` prints `1`.
   - `grep -cF "func registerWebOnboarding(" go/cmd/ubyhost-web/register_web_onboarding.go | tail -1` prints `1`.
   - `ls go/internal/web/onboarding/onboarding_page.go go/internal/web/onboarding/onboardingpage 2>&1 | tail -2` says "No such file" twice (nothing of this brief exists yet).
   - `find docs/tasks/1595-files -name '*.txt' | wc -l | tail -1` prints `11`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1595-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   61e98a73225129d15b23416420626524d43ceec89dfb2307257a446809ed58e0  go/internal/palette/linkkey.go
   7210470ddc6cf2b6cf5be33d3e3ecb77b49eb4de7dad1c98f4428dc8d61fb484  go/internal/web/onboarding/onboarding_page.go
   d41c37bdef5b3fc29a490d9f3dc2f6a412b839d2d5da013ff1303c69d41df97a  go/internal/web/onboarding/onboarding_page_test.go
   9d40f2e8fb056a5e34266b67bfc4d2473035906bf4eb04f839ec5261d71c9340  go/internal/web/onboarding/onboardingpage/onboarding.tmpl
   4df45e9993e82c85978031f89d12109ad55405036fd67112b7805ebe28bee572  go/internal/web/onboarding/onboardingpage/i18n_keys.txt
   0615c58b2b61356620a36416c639a29dfd1299abd35364b72ed328a5da479504  go/internal/web/onboarding/onboardingpage/i18n.json
   58be1f6b3f75dddb35ecdcc33c5fc0627814eb6b3e23c0e1cabba6705b89991d  go/internal/web/onboarding/testdata/onboarding_page_golden.json
   fad243804f84f44b21d81b1d885747537b4626456c2ba5f7c203e3eaceb8188b  go/cmd/ubyhost-web/register_web_onboarding_page.go
   fd2170b88340e8a920490c2243f0b09b33515c8f5ef2667c3a42a4648fe36419  go/cmd/ubyhost-web/register_web_onboarding_page_test.go
   a320f3d0244af41a23a32d7f0fa0f69014081346e79baef594bf4dc513f258cd  App/scripts/go_onboarding_page_golden.py
   9d69854f544b7d30381d21c3b3049d5529bc965ec7f42f747f3afdaed93fdd51  App/tests/test_go_onboarding_page_golden.py
   EOF
   ```

   Every line must end with `: OK` (11 lines). Then commit "1595 step 1" (`git add -A && git commit -m "1595 step 1"`).

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/onboarding internal/palette cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/onboarding/... ./internal/palette/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). Nothing changed, so no commit.

3. Python checks (repo root). If `App/.venv/bin/python` does not exist, write "Python checks: CI only (no App/.venv)" in the report and go to step 4. Else run (one call):

   ```bash
   cd App && .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -5; echo "i18n rc=$?"; .venv/bin/python -m pytest tests/test_go_onboarding_page_golden.py tests/test_go_host_i18n.py tests/test_go_onboarding_setup.py -q --tb=short -rs 2>&1 | tail -5
   ```

   Expected: `i18n rc=0` with nothing before it, and `5 passed` with no `skipped`. Nothing changed, so no commit.

4. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if it is already running (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55595/data status' | tail -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55595 && chown postgres /var/tmp/pg55595 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55595/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55595/data -o "-p 55595 -k /var/tmp/pg55595" -l /var/tmp/pg55595/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55595/postgres` in step 5. No PostgreSQL 16 binaries at that path: write "CI only" in the report and STOP before step 5.

5. Run the tests on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55595/postgres go test ./internal/web/onboarding/... ./internal/palette/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: three `ok` lines (`.../go/internal/web/onboarding`, `.../go/internal/palette`, `.../go/cmd/ubyhost-web`). Then show the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55595/postgres go test ./internal/web/onboarding/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestOnboardingPageVisibleLines$|^TestOnboardingPageMatchesPython$|^TestOnboardingPageCreatesSlug$|^TestOnboardingPageTemplateKeys$|^TestOnboardingPageRouteRegistered$|^TestOnboardingRoutes$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of these 6 tests and two `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestOnboardingPageVisibleLines
   --- PASS: TestOnboardingPageMatchesPython
   --- PASS: TestOnboardingPageCreatesSlug
   --- PASS: TestOnboardingPageTemplateKeys
   --- PASS: TestOnboardingRoutes
   --- PASS: TestOnboardingPageRouteRegistered

   Then the skip count of the whole run: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55595/postgres go test ./internal/web/onboarding/... ./internal/palette/... ./cmd/ubyhost-web/... -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` must print `0`.

6. Write the report (§9), set `Status: review` in this file and commit "1595 step 6".

## 5. Do not touch

`App/app/` (no Python application file changes; Python still serves `/onboarding`), `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, every other file under `go/`: in particular `go/internal/web/onboarding/setup.go`, `routes.go`, `setup_test.go`, `routes_test.go`, `testdata/setup_golden.json`, any `wizard*.go` file or setup-wizard template folder (briefs 1599-1604), `go/cmd/ubyhost-web/register_web_onboarding.go`, the existing palette files, `go/internal/hostweb/`, `go/internal/session/`. Hard rules of AGENTS.md: no secret or guest datum in a file or a log (the test data is made up), nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 2, 3 and 5). Test-map row: none yet for `go/internal/web/onboarding`; the coordinator adds `go test ./internal/web/onboarding/...` (PostgreSQL) plus `App/tests/test_go_onboarding_page_golden.py` from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 11 files.
- [ ] The format, build and vet step printed nothing.
- [ ] Step 3: `i18n rc=0` and `5 passed`, or "CI only (no App/.venv)" in the report.
- [ ] Step 5: three `ok` lines, the 6 named tests `--- PASS`, SKIP count `0`.
- [ ] `git log --oneline --grep='^1595 step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1595 step') | tail -40` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed to `main`.
- [ ] UI: the page is dormant (no path routes to it) and the Python browser tests cannot reach the Go service, so rules 7 and 10 do not run here. **The visual and UX gate is pending** (owner item: Go pages have had no visual check): `test_layout_lint_browser.py` and the 390, 768 and 1280 px screenshots of `/onboarding` on Go must pass before the owner switches the path (Owner steps).

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

Write `docs/tasks/1595-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git show --stat` as in §7).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `onboarding_page.go` (every query scopes by `owner_user_id IS NOT DISTINCT FROM` the workspace id; `archived_at IS NULL`; the decryption never logs or shows the password, only its emptiness counts; the finish card only for exactly one property; the only write is `palette.LinkKey`'s slug insert), `onboarding.tmpl` (every form has `_csrf`; values are escaped by html/template; no `safe`), and `linkkey.go` (one wrapper, no palette behaviour change).

## Owner steps

None now: nothing is switched on. Later, after the UX gate of §7 passed on Go (owner item 7), the path switch is:

1. On the server, open the env file that holds `UBYHOST_GO_PATHS` (see docs/ENVIRONMENT.md).
2. Add `/onboarding` to the comma-separated list (exact path; do not add `/onboarding/*`, the 1290 POST routes have their own switch).
3. Run `scripts/caddy-validate.sh`, then `docker compose up -d caddy`.
4. Open `/onboarding` signed in; the checklist must look the same as before. Rollback: remove `/onboarding` again and repeat step 3.
