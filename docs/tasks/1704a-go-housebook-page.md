# 1704a: Go house book page (GET /housebook)

Status: done (UX gate on Go pending until the path switch)
Depends on: none (brief 1608 exports, 1380/1381 host layout are on this branch; verified at 61ab554) | Base commit: current tip of the working branch | Branch: task/1704a-go-housebook-page
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: B (Sonnet wrote the exact-diff pass; the orchestrator reads the diff of the risk-listed files). Part of [1704](1704-go-settings-menu-pages.md).

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1704a step k` (`k` is the step number). Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1704a step'`, never a fixed base commit.

## 1. Objective

Port `housebook_view` (`App/app/routes/admin.py` 5228-5260, template `App/app/templates/housebook.html`, the macros `housebook_csv_menu` and `date_range` it calls, and `App/app/housebook.py` `period_presets`, `housebook_rows`, `housebook_archived_rows`) to a new Go package `go/internal/web/housebook`, and register `GET /housebook` in ubyhost-web. The route is dormant: nothing is added to `UBYHOST_GO_PATHS`. The CSV and ZIP routes (`/housebook.csv`, `/housebook/pdfs.zip`) and the guest routes the page links to stay as they are.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (a read-only register; the row reads are the existing `exports` ones); 2 privacy: no new personal-data field, no retention line, no outbound request (the page shows the guest data the CSV already exports, masked as Python masks it when an impersonating non-admin session may not see a guest); 3 fixtures are made up; 4 no new dependency; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, no schema change; 6 light mode, every form works without JavaScript (the Go forms carry `<input type="hidden" name="_csrf" value="{{csrf}}">`; Python's `csrf.js` adds it in the browser, this is the only intended markup difference); 11 Go first: this brief is the Go port, and per the owner decision of 2026-11-17 its tests are Go only with hand-written expected strings (no Python golden script, no `App/` file).

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1704a-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `5fce5c38d2ec35c8ec5045b48e8f584e424baa6742e73438e1327ff3e9361fd2` | `go/internal/web/exports/housebook_view.go` | create | 137 |
| `701fc739fa93d7d5f16c84489ed0454249db06c5f1d6ef554b38d124ca65d790` | `go/internal/web/exports/housebook_view_test.go` | create | 16 |
| `c5e5bdb5de885d0a59d09eaf2ca47d83cd63901ffb9fcefdc50e9cd9bd5faceb` | `go/internal/web/housebook/housebook.go` | create | 232 |
| `05f7bf13f0d0e4473761553d0eb517e750d75567fb3f3dbc8d7bd2838b90d847` | `go/internal/web/housebook/housebook_test.go` | create | 369 |
| `5359aed180e99fc39012826a03b92b8827c3b1a134106dc668f8173dabcf41e8` | `go/internal/web/housebook/templates/housebook.tmpl` | create | 237 |
| `73d828c2b2bc58de060789a1c528ab5ecc3be5b7a9058614b4bc6fc30b20037c` | `go/internal/web/housebook/i18n_keys.txt` | create | 31 |
| `fa2c6edf00d5799c1a2bf1579c0e22ea987abffdedb1000c6fbc474731bf6104` | `go/internal/web/housebook/i18n.json` | create | 269 |
| `6a8cbae383bebfdfc678b8c82268fb6aa7b10b2d21f36a39da2e1c2e6b2d8042` | `go/cmd/ubyhost-web/register_web_housebook.go` | create | 24 |
| `e4929c2a2564786aefd5007b2b1cb8c195878f233c1f5d12a965533d70f7e844` | `go/cmd/ubyhost-web/register_web_housebook_test.go` | create | 23 |

Full manifest: `docs/tasks/1704a-files/MANIFEST.sha256` (exact-diff backfill 2026-11-20 from `main`).

**How the code is built (for the reviewer; the executor reads no Go file, it only copies and runs).**

- `exports/housebook_view.go`: a new file in the existing `exports` package that only adds exported readers on top of the unexported CSV ones: `LoadHousebookPage` (reads `?apartment=`, `?from=`, `?to=` with the package's own `queryInt` and `queryDate`, then `housebookGuests` for the rows, `housebookRow` for the 17 CSV texts, `archivedHousebookSQL` for the archived guests, one new apartment list query), plus `DateCZ` and `PurposeLabelCS`, thin wrappers of the existing `dateCZ` and `purposeLabel`. No existing line of the package changes. The owner is `ownerID(h)` (`session.Host.Workspace.ID`); a missing owner is an error, never Python's "`? IS NULL OR`" that would read every host (same rule as `requireOwner` in the CSV route). Every query is scoped: guests and archived guests by `a.owner_user_id = $1`, apartments by `owner_user_id IS NOT DISTINCT FROM $1`. Doc and visa numbers go through `maskIdentifier` (`access.mask_identifier`) unless `identityVisible(h, &guestID)` (`access.identity_visible`).
- `housebook/housebook.go`: `Handler` is `require_login` (`hostweb.Login`; sets `Cache-Control: no-store, private` as the Python middleware does), then `layout.Render` with nav `housebook`, body_kind `list`, `V2`, how key `housebook` and an empty h1 slot (Python blanks `page_title` and draws its own head). `buildPage` computes what Jinja computed inline: the property label, `housebook_csv_params`, `period_presets` (Prague today through `deadlines.LocalNow`), the nationality, residence and purpose texts in the page language (`countries.Name`; the purpose tables for en and vi are the ones of `validation.PURPOSES` and `host_vi_i18n.PURPOSES`, cs comes from `exports`), and the reported pill. **Faithful quirk kept:** the green pill is only for the exact text `yes`, so a guest filed by hand ("yes - filed by hand in UbyPort") shows "Not yet sent", as in Python; a test pins it. Do not "fix" it here; it goes to known-issues in the report.
- `templates/housebook.tmpl`: the Go twin of `housebook.html`. The macros `housebook_csv_menu` (compact, PDF on) and `_date_range.html` `date_range` are written out inline because the layout does not have them. `property_identity`, `row_open`, `row_menu_begin/end`, `icon`, `csrf`, `t`, `kv` come from the layout funcs; `date_cz` is passed in.
- `i18n_keys.txt` / `i18n.json`: the page catalog, written by `App/scripts/go_host_i18n.py` (its glob finds the nested file). The layout catalog has `common.open`, `common.more_actions` already.
- `register_web_housebook.go`: an `init()` that adds `GET /housebook` through `registerRoutes`; it sits next to the existing `/housebook.csv` and `/housebook/pdfs.zip` routes, which keep their patterns (the test checks it).
- Tests (all Go, expected strings written by hand from the seed in `housebook_test.go`): signed-out redirect; the full English page for host 2 (rows, order, pills, popover facts, archived table and restore form, PDF dialog, presets, no `Foreign*` or demo guest, `_csrf` in every post form); filters (`apartment`, `from`, `to`, an invalid value ignored, the empty state); host 3 sees only its own rows and asking for host 2's property returns nothing; an admin previewing host 2; cs and vi titles and texts; presets across month, year and leap-year edges; the pill rule; the purpose labels; `maskIdentifier`.

**Accepted differences (only reachable with hand-made data or requests):** `HEAD /housebook` is served by the `GET` pattern; Python's 500 page for a browser is a plain 500 text here (same as the exports routes, until the Go error page exists); an owner-less session is a 500 instead of Python's all-hosts read (a safety change, not reachable through `require_login`); apartment names sort by the PostgreSQL collation, as Python's do.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/exports/housebook_view.go` | create | `LoadHousebookPage`, `DateCZ`, `PurposeLabelCS`, `maskIdentifier` |
| `go/internal/web/exports/housebook_view_test.go` | create | `maskIdentifier` test |
| `go/internal/web/housebook/housebook.go` | create | handler, page data, presets, texts |
| `go/internal/web/housebook/housebook_test.go` | create | Go tests with a seed and hand-written expectations |
| `go/internal/web/housebook/templates/housebook.tmpl` | create | Go twin of housebook.html |
| `go/internal/web/housebook/i18n_keys.txt` | create | page catalog keys |
| `go/internal/web/housebook/i18n.json` | create | page catalog (generated, checked in step 3) |
| `go/cmd/ubyhost-web/register_web_housebook.go` | create | registers `GET /housebook` |
| `go/cmd/ubyhost-web/register_web_housebook_test.go` | create | route registration test |
| `docs/tasks/1704a-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1704a-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `grep -cF '@router.get("/housebook")' App/app/routes/admin.py | tail -1` prints `1`.
   - `grep -cF 'func housebookGuests(ctx context.Context, d deps, owner any, apartment int64, from, to string) ([]row, error) {' go/internal/web/exports/housebook.go | tail -1` prints `1`.
   - `grep -cF 'func housebookRow(ctx context.Context, d deps, g row) ([]string, error) {' go/internal/web/exports/housebook.go | tail -1` prints `1`.
   - `grep -cF 'const archivedHousebookSQL = ' go/internal/web/exports/workspace.go | tail -1` prints `1`.
   - `grep -cF 'func dateCZ(v string) string {' go/internal/web/exports/archived.go | tail -1` prints `1`.
   - `grep -cF 'func ownerID(h *session.Host) any {' go/internal/web/exports/exports.go | tail -1` prints `1`.
   - `grep -cF 'func identityVisible(h *session.Host, guestID *int64) bool {' go/internal/web/exports/exports.go | tail -1` prints `1`.
   - `grep -cF 'func queryInt(r *http.Request, key string) int64 {' go/internal/web/exports/exports.go | tail -1` prints `1`.
   - `grep -cF 'func MustParseFuncs(cat hostweb.Catalog, funcs template.FuncMap, fsys fs.FS, patterns ...string) *Templates {' go/internal/hostweb/layout/pagefuncs.go | tail -1` prints `1`.
   - `grep -cF 'func registerRoutes(fn func(*http.ServeMux, *metrics, *pgxpool.Pool)) {' go/cmd/ubyhost-web/registry.go | tail -1` prints `1`.
   - `grep -rcF '"GET /housebook"' go/cmd/ubyhost-web | grep -v ':0$' | tail -3` prints nothing (the page route is not registered yet; the `.csv` and `.zip` routes have other patterns).
   - `ls go/internal/web/housebook go/internal/web/exports/housebook_view.go 2>&1 | tail -2` says "No such file" twice (nothing of this brief exists yet).
   - `find docs/tasks/1704a-files -name '*.txt' | wc -l | tail -1` prints `9`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1704a-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF2' 2>&1 | tail -10
   5fce5c38d2ec35c8ec5045b48e8f584e424baa6742e73438e1327ff3e9361fd2  go/internal/web/exports/housebook_view.go
   701fc739fa93d7d5f16c84489ed0454249db06c5f1d6ef554b38d124ca65d790  go/internal/web/exports/housebook_view_test.go
   c5e5bdb5de885d0a59d09eaf2ca47d83cd63901ffb9fcefdc50e9cd9bd5faceb  go/internal/web/housebook/housebook.go
   05f7bf13f0d0e4473761553d0eb517e750d75567fb3f3dbc8d7bd2838b90d847  go/internal/web/housebook/housebook_test.go
   5359aed180e99fc39012826a03b92b8827c3b1a134106dc668f8173dabcf41e8  go/internal/web/housebook/templates/housebook.tmpl
   73d828c2b2bc58de060789a1c528ab5ecc3be5b7a9058614b4bc6fc30b20037c  go/internal/web/housebook/i18n_keys.txt
   fa2c6edf00d5799c1a2bf1579c0e22ea987abffdedb1000c6fbc474731bf6104  go/internal/web/housebook/i18n.json
   6a8cbae383bebfdfc678b8c82268fb6aa7b10b2d21f36a39da2e1c2e6b2d8042  go/cmd/ubyhost-web/register_web_housebook.go
   e4929c2a2564786aefd5007b2b1cb8c195878f233c1f5d12a965533d70f7e844  go/cmd/ubyhost-web/register_web_housebook_test.go
   EOF2
   ```

   Every line must end with `: OK` (9 lines). Then commit "1704a step 1" (`git add go && git commit -m "1704a step 1" | tail -3`).

2. Format, build and vet (one call, repo root):

   ```bash
   cd go && gofmt -l internal/web/housebook internal/web/exports cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/housebook/... ./internal/web/exports/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). Nothing changed, so no commit.

3. Catalog check (repo root). If `App/.venv/bin/python` does not exist, write "Python checks: CI only (no App/.venv)" in the report and go to step 4. Else run (one call):

   ```bash
   cd App && .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -5; echo "i18n rc=${PIPESTATUS[0]}"; .venv/bin/python -m pytest tests/test_go_host_i18n.py -q --tb=short -rs 2>&1 | tail -5
   ```

   Expected: `i18n rc=0` with nothing before it, and a `passed` line with no `skipped`. Nothing changed, so no commit.

4. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if it is already running (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55704/data status' | head -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55704 && chown postgres /var/tmp/pg55704 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55704/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55704/data -o "-p 55704 -k /var/tmp/pg55704" -l /var/tmp/pg55704/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55704/postgres` in step 5. No PostgreSQL 16 binaries at that path: write "CI only" in the report and STOP before step 5.

5. Run the tests on PostgreSQL (one call, from the repo root):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55704/postgres go test ./internal/web/housebook/... ./internal/web/exports/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: three `ok` lines (`.../go/internal/web/housebook`, `.../go/internal/web/exports`, `.../go/cmd/ubyhost-web`). Then show the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55704/postgres go test ./internal/web/housebook/ ./internal/web/exports/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestPeriodPresets$|^TestReportedPill$|^TestPurposeLabel$|^TestHousebookPage|^TestMaskIdentifier$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of these 11 tests and three `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestPeriodPresets
   --- PASS: TestReportedPill
   --- PASS: TestPurposeLabel
   --- PASS: TestHousebookPageSignedOut
   --- PASS: TestHousebookPageEnglish
   --- PASS: TestHousebookPageFilters
   --- PASS: TestHousebookPageOtherHost
   --- PASS: TestHousebookPageAdminPreview
   --- PASS: TestHousebookPageLanguages
   --- PASS: TestMaskIdentifier
   --- PASS: TestHousebookPageRouteRegistered

   Then the skip count of the whole run: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55704/postgres go test ./internal/web/housebook/... ./internal/web/exports/... -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` must print `0` (the three probe tests of `cmd/ubyhost-web` skip without their own env vars; they are not part of this count).

6. UX gate (AGENTS.md rule 10, [workflow](../context/workflow.md#ux-gate)). The page is dormant: the Python browser tests and the shots tool cannot reach the Go service, so they cannot prove this page yet. Do what can run now, and write the rest into the report as pending (owner item, as for 1595):
   - Read `docs/design/pages/stays.md` section "Guest register" and tick `docs/design/design-system.md` section 5 in the report (the template keeps Python's classes and markup; the diff to Python is `_csrf` only).
   - If `App/.venv/bin/python` exists, run the Python baseline, which draws the same page from Jinja: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_housebook_presets_0889.py -q -x 2>&1 | tail -30`. Expected: a `passed` line, 0 skipped. Else write "UX baseline: CI only (no App/.venv)".
   - **Pending until the path is switched:** `/tmp/shots/layout-lint/housebook-{390,768,1280}.png` of the Go page, opened and described per width ("390: ...; 768: ...; 1280: ..."), with `test_layout_lint_browser.py` green on Go. Nothing to commit here.

7. Write the report (§9), set `Status: review` in this file and in the 1704 index row of 1704a, and commit "1704a step 7".

## 5. Do not touch

`App/` (no Python file changes; Python still serves `/housebook`), `UBYHOST_GO_PATHS`, `docs/ENVIRONMENT.md`, Caddy and compose files, every server file, every other file under `go/`: in particular the existing `go/internal/web/exports/*.go` files (the new `housebook_view.go` only adds), `go/internal/web/exports/housebook_zip.go`, the CSV route, `go/internal/hostweb/` and its `i18n.json`, `go/internal/web/properties/i18n.json`, the guest, archive and unarchive routes. Hard rules of AGENTS.md: no secret or guest datum in a file or a log (the seed is made up; no real guest, no real document number).

## 6. Commands

Exactly the commands of §4 (steps 2, 3, 5 and 6). Test-map row "Host pages, templates, CSS": `test_host_*.py` and `test_host_geometry.py` (0 skipped) run from CI for the Python side; the Go side has no row yet, the coordinator adds `go test ./internal/web/housebook/... ./internal/web/exports/...` (PostgreSQL) from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 9 files.
- [ ] The format, build and vet step printed nothing.
- [ ] Step 3: `i18n rc=0` and a `passed` line, or "CI only (no App/.venv)" in the report.
- [ ] Step 5: three `ok` lines, the 11 named tests `--- PASS`, SKIP count `0`.
- [ ] `git log --oneline --grep='^1704a step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1704a step') | tail -40` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python file changed; nothing was pushed to `main`.
- [ ] UI: dormant page. **The visual and UX gate (screenshots at 390, 768 and 1280, layout lint on Go) is pending** until the owner switches the path (Owner steps).

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

Write `docs/tasks/1704a-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git show --stat` as in §7).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left, and for known-issues: "the house book shows a guest filed by hand as Not yet sent (Python quirk, `housebook.html` `reported_pill` tests only the exact `yes`)".

## Risk list (for the reviewer)

Read the diff of `housebook_view.go` (every query scoped by the workspace owner; a nil owner is an error; archived rows filtered by the property in Go after the owner-scoped read; `maskIdentifier` applied unless `identityVisible`), `housebook.tmpl` (every post form has `_csrf`; values escaped by html/template; no `safe`; the `popover` and `data-href` attributes as Python), and `housebook.go` (`reportedPill` keeps the exact-`yes` rule; presets use Prague today).

## Owner steps

None now: nothing is switched on. Later, after the UX gate of §7 passed on Go (owner item), the path switch is:

1. On the server, open the env file that holds `UBYHOST_GO_PATHS` (see docs/ENVIRONMENT.md).
2. Add `/housebook` to the comma-separated list (exact path; `/housebook.csv` and `/housebook/pdfs.zip` have their own switches).
3. Run `scripts/caddy-validate.sh`, then `docker compose up -d caddy`.
4. Open `/housebook` signed in at 390, 768 and 1280 px; the register must look the same as before. Rollback: remove `/housebook` again and repeat step 3.
