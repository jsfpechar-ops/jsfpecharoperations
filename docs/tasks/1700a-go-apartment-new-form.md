# 1700a: Go property settings 1a: the new-property form page (GET /apartments/new)

Status: todo — exact-diff pass done 2026-11-17, ready for Haiku
Depends on: 1520-1524 on the branch (verified: `go/internal/web/properties` has `lists.go`, `entities.go`, `entity_editor.go`); 1525 is replaced by 1704, 1527 not required | Base commit: current tip of the working branch | Branch: task/1700a-go-apartment-new-form
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (this brief needs about 22)
Tier: B (Sonnet writes the exact-diff pass; the orchestrator reads the diff of the risk-listed files, see the end)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1700a step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1700a step'`, never a fixed base commit.

## 1. Objective

Port `apartment_new` and `_render_apartment_new` (`App/app/routes/admin.py` ~1457-1507; the template `apartment_form.html` create branch with `_property_create.html`, `_copy_settings_dialog.html`, `_property_identity_fields.html`, `_property_operator.html`, `_property_address_fields.html`) to `go/internal/web/properties`: `GET /apartments/new`, the short Add property page with the "copy settings from another property" dialog. The route is dormant: nothing is added to `UBYHOST_GO_PATHS`. The code exports one renderer, `RenderApartmentNew`, which brief 1700b (POST /apartments) calls again for a refused create with the typed values and the errors.

Split of the old brief 1700 (owner decision 2026-11-17): 1700a is this page; 1700b is `POST /apartments` (create, written later); the RUIAN suggest route `/apartments/ruian-suggest` is the RUIAN briefs (1700c, 1700d). This brief leaves the form's RUIAN script tag and its `data-ruian-*` attributes exactly as Python writes them.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (a read-only form; the police address fields are only drawn, saving is 1700b); 2 privacy: no new personal-data field, no retention line, no outbound request (the page reads the workspace's own operators and properties, as Python does; the RUIAN script tag is the one Python already has); 3 fixtures are made up (`@example.test`); 4 no new dependency (stdlib, pgx and packages already in `go.mod`); 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, every query scoped by `owner_user_id IS NOT DISTINCT FROM` the workspace, no schema change; 6 light mode, the form works without JavaScript (the create form carries the `_csrf` input, and "Check again" is a plain submit); 11 Go first: this brief is the Go port. The two files under `App/` are **go-first exception 1** (port plumbing: a golden script and its freshness test); no Python application file changes.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The page shows the host's own operators and property names and, after "Copy", the copied settings as hidden fields; nothing is written.

**All code is pre-written, compiled and tested** (in a throwaway copy of this branch, with PostgreSQL 16 and the real Python page). Sidecars: `docs/tasks/1700a-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. The golden file `go/internal/web/properties/testdata/apartment_new_form_golden.json` is not a sidecar: step 2 generates it from the real Python page.

| sha256 | file | action | lines |
|---|---|---|---|
| `277f4a8a60dfddcac685762a91d3962911eeff2c180cad81cc0fb72e1fb9990e` | `go/internal/web/properties/apartment_new.go` | create | 355 |
| `c798ed4b52a71528a049b3a795f321dd829e2635774b718a206a4e9469500be6` | `go/internal/web/properties/apartment_new_test.go` | create | 390 |
| `db0c7a7c33b3ffd30f6c33c9d961f3445b7debeb65de0f9688443a455103946b` | `go/internal/web/properties/apartmentnew/apartment_new.tmpl` | create | 145 |
| `4c12954c637973dddb402f7ce37b3d639ba3982d1fedbfad4bb333b7df1daaa3` | `go/internal/web/properties/apartmentnew/i18n_keys.txt` | create | 18 |
| `dce7e9babd11588313b499003cbea76ab33ac1deb6597065052a0ae8dc5be156` | `go/internal/web/properties/apartmentnew/i18n.json` | create | 212 |
| `7268ecee3cdfbad43ea5f3fd020f0157755c69d3d54a8ffbb7bd03e985c1387d` | `go/cmd/ubyhost-web/register_web_properties_apartment_new.go` | create | 24 |
| `0cb6d7b27e9f15c8b4d4a334db9b4b8f64b6b7c11de48662a33fd5dd7da85318` | `go/cmd/ubyhost-web/register_web_properties_apartment_new_test.go` | create | 22 |
| `1e9382a6ee83d9e8cbcbc541f66c8d774830fa97c21198b9e8827b1005c96090` | `App/scripts/go_apartment_new_form_golden.py` | create | 225 |
| `26bff49ac72e47da4a1cdd5f60edcb3bdc71c79a1be37b80a50b22b384d98a05` | `App/tests/test_go_apartment_new_form_golden.py` | create | 27 |

**How the code is built (for the reviewer; the executor reads no Go file, it only copies and runs).**

- `apartment_new.go`: `RegisterApartmentNew` mounts `GET /apartments/new` (same pattern as `RegisterLists`). The handler is `hostweb.Login` (a signed-out request gets Python's redirect), then reads the query like `admin_helpers.query_int` (`legal_entity_id`, `copy_from`: last value, stripped, `int()` rules incl. `+`, `-`, `_`; a value that is not a number counts as none; a non-ASCII digit string or one past 64 bits answers 501 with `X-Ubyhost-Not-Ported: 1` so Caddy re-sends it to Python), loads the host's live operators (by name) and live properties (by internal name), and, for `copy_from`, the one property of this workspace (archived ones too, as `access.apartment`): none found answers 404 `Not found.` like Python. The copied values are `_property_copy_values` (the 15 copy keys without empty ones: 0, NULL or blank text). The renderer `RenderApartmentNew` builds the same context as `_render_apartment_new` (operator selection rules of `_property_operator.html`, the alternate controller select, the hidden copy fields in the order of `_property_create.html`, `default_purpose` or `10`) and calls `layout.Render` with nav `apartments`, body_kind `form`, `V2`, how_key `property`, back link `/apartments` labelled "Properties", an empty h1 slot (Python blanks `page_title`; the h1 is in the page head) and `Page.Status` (0 is 200).
- `apartmentnew/apartment_new.tmpl`: the Go twin of the six Jinja files, with `help_tip`, `field_label` and `icon` from the layout funcs. The seven address inputs are drawn by one `define` from a field table built in Go (names, label and hint keys, maxlength, inputmode, autocapitalize, placeholder as in `_property_address_fields.html`). The script tag `/static/ruian_suggest.js?v=20261111-1103b` and `data-ruian-suggest/-loading/-none` are copied unchanged.
- `apartmentnew/i18n_keys.txt` / `i18n.json`: the page catalog, written by `App/scripts/go_host_i18n.py` (its glob finds nested `i18n_keys.txt`). The shared `properties/i18n.json` is not touched.
- `register_web_properties_apartment_new.go`: an `init()` through `registerRoutes`, next to `register_web_properties.go` (unchanged).
- `App/scripts/go_apartment_new_form_golden.py` seeds a throwaway SQLite database (5 hosts: nothing; one operator; two operators plus an archived one with properties that carry copyable settings, a stay fee, an archived property and one on the archived operator; another host's property as a foreign copy source; an admin previewing a workspace), renders `GET /apartments/new` with 21 queries (operator chosen, padded `+42`, foreign or non-numeric operator, `copy=choose`, `copy_from` with and without a stay fee, `4_1`, archived source, source on an archived operator, operator override, foreign id, missing id, non-numeric id, zero) in en, cs and vi through the real FastAPI app, and keeps the `<title>` text and `visible_lines()` of the page area. `TestApartmentNewMatchesPython` seeds PostgreSQL from the same file and compares status, redirect, title and every line (no line is left out: Python's create form already has the `_csrf` input).

**Exported renderer for brief 1700b:**

```go
func RenderApartmentNew(w http.ResponseWriter, r *http.Request, env layout.Env, host *session.Host, form ApartmentNewForm) error
```

`ApartmentNewForm` holds `Entities`, `Peers` (fill both with `loadApartmentNewChoices(ctx, pool, workspaceID)`), `SelectedEntityID`, `CopyFromID`, `CopiedFromName`, `CopyOpen`, `Prefill` (a refusal puts every submitted copy key in it, an empty one too), `PrefillEntityID`, `PrefillControllerID`, `Draft` (`internal_name`, `city_en`, `addr_*`), `DraftEntityID`, `DraftControllerID`, `OperatorError` (an i18n key), `NameError`, `AddressErrors` (field to message text, already in the host's language: there is no Go port of `validation_i18n.localize` yet, 1700b must bring it or stop) and `Status` (400 for a refusal). The catalog of this page has `apartment.form.operator.*` and `flash.error.no_such_controller`; 1700b adds new keys only in its own catalog.

**Accepted differences (only reachable with hand-made requests):** `HEAD /apartments/new` is served by the `GET` pattern; the 404 body `Not found.` has a sniffed `text/plain` content type where Python sends none; a non-ASCII or oversized number in `legal_entity_id` or `copy_from` is answered `501` plus the Caddy fallback header (Python then serves it); Python's 500 page for a browser is a plain 500 text here (same as brief 1290, until the Go error page exists). The `_csrf` input is not a difference here (the Python create form renders it).

**Verified by the brief writer** (in a throwaway copy of this branch at the base commit, sidecars copied as step 1 does, Python venv from `App/requirements.txt`, PostgreSQL 16): `gofmt -l` printed nothing, `go build ./...` and `go vet ./internal/web/properties/... ./cmd/...` were silent, `go test ./internal/web/properties/... ./cmd/ubyhost-web/... -count=1` passed (the 3 SKIPs of `./cmd/ubyhost-web/...` are the existing probe tests; `./internal/web/properties/...` has 0), the 7 named tests of step 6 printed `--- PASS`, the golden has 21 cases (18 x 200, 1 x 303, 2 x 404), `go_host_i18n.py --check` printed nothing, `tests/test_go_apartment_new_form_golden.py` and `tests/test_go_host_i18n.py` passed (3 passed, 0 skipped).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/apartment_new.go` | create | route, handler, `RenderApartmentNew`, form types |
| `go/internal/web/properties/apartment_new_test.go` | create | golden parity, refusal render, query int, catalog keys |
| `go/internal/web/properties/apartmentnew/apartment_new.tmpl` | create | Go twin of the six Jinja files |
| `go/internal/web/properties/apartmentnew/i18n_keys.txt` | create | page catalog keys |
| `go/internal/web/properties/apartmentnew/i18n.json` | create | page catalog (generated, checked in step 4) |
| `go/internal/web/properties/testdata/apartment_new_form_golden.json` | create | golden written by the Python script (step 2) |
| `go/cmd/ubyhost-web/register_web_properties_apartment_new.go` | create | registers `GET /apartments/new` |
| `go/cmd/ubyhost-web/register_web_properties_apartment_new_test.go` | create | route registration test |
| `App/scripts/go_apartment_new_form_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_apartment_new_form_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1700a-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1700a-report.md` | create | the report (§9) |

No other file may change. `docs/tasks/1700b` (create) runs after this brief and reuses `RenderApartmentNew`; the RUIAN briefs do not touch these files.

## 4. Steps

0. Checks (repo root, one call per bullet group). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `grep -cF '@router.get("/apartments/new")' App/app/routes/admin.py | tail -1` prints `1`.
   - `grep -cF 'def _property_copy_form_context(' App/app/routes/admin.py | tail -1` prints `1`.
   - `grep -cF '{% include "_property_create.html" %}' App/app/templates/apartment_form.html | tail -1` prints `1`.
   - `grep -cF 'ruian_suggest.js?v=20261111-1103b' App/app/templates/_ruian_suggest.html | tail -1` prints `1`.
   - `grep -cF 'func RegisterLists(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) {' go/internal/web/properties/lists.go | tail -1` prints `1`.
   - `grep -cF 'func queryLast(r *http.Request, key string) string {' go/internal/web/properties/lists.go | tail -1` prints `1`.
   - `grep -cF 'func notPorted(w http.ResponseWriter, what string) {' go/internal/web/properties/lists.go | tail -1` prints `1`.
   - `grep -cF 'func pyStrip(s string) string {' go/internal/web/properties/localpath.go | tail -1` prints `1`.
   - `grep -cF 'func fail(w http.ResponseWriter, err error) {' go/internal/web/properties/properties.go | tail -1` prints `1`.
   - `grep -cF 'func testPool(t *testing.T) *pgxpool.Pool {' go/internal/web/properties/properties_test.go | tail -1` prints `1`.
   - `grep -cF 'func sqlValue(v any) any {' go/internal/web/properties/properties_test.go | tail -1` prints `1`.
   - `grep -cF 'func testClock() time.Time { return testNow }' go/internal/web/properties/properties_test.go | tail -1` prints `1`.
   - `grep -cF 'func noWrap(_ string, h http.HandlerFunc) http.Handler {' go/internal/web/properties/more_helpers_test.go | tail -1` prints `1`.
   - `grep -cF 'func registerRoutes(fn func(*http.ServeMux, *metrics, *pgxpool.Pool)) {' go/cmd/ubyhost-web/registry.go | tail -1` prints `1`.
   - `grep -cF 'func Render(w http.ResponseWriter, r *http.Request, env Env, host *session.Host, p Page, tpl *Templates, name string, data any) error {' go/internal/hostweb/layout/layout.go | tail -1` prints `1`.
   - `grep -rcF 'apartments/new' go/internal/web/properties --include=*.go | grep -v ':0' | tail -3` prints nothing (no Go route for the path exists yet).
   - `ls go/internal/web/properties/apartment_new.go go/internal/web/properties/apartment_new_test.go go/internal/web/properties/apartmentnew go/internal/web/properties/testdata/apartment_new_form_golden.json go/cmd/ubyhost-web/register_web_properties_apartment_new.go go/cmd/ubyhost-web/register_web_properties_apartment_new_test.go App/scripts/go_apartment_new_form_golden.py App/tests/test_go_apartment_new_form_golden.py 2>&1 | grep -c 'No such file' | tail -1` prints `8` (nothing of this brief exists yet).
   - `find docs/tasks/1700a-files -type f -name '*.txt' | wc -l | tail -1` prints `9`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1700a-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOT' 2>&1 | tail -10
   277f4a8a60dfddcac685762a91d3962911eeff2c180cad81cc0fb72e1fb9990e  go/internal/web/properties/apartment_new.go
   c798ed4b52a71528a049b3a795f321dd829e2635774b718a206a4e9469500be6  go/internal/web/properties/apartment_new_test.go
   db0c7a7c33b3ffd30f6c33c9d961f3445b7debeb65de0f9688443a455103946b  go/internal/web/properties/apartmentnew/apartment_new.tmpl
   4c12954c637973dddb402f7ce37b3d639ba3982d1fedbfad4bb333b7df1daaa3  go/internal/web/properties/apartmentnew/i18n_keys.txt
   dce7e9babd11588313b499003cbea76ab33ac1deb6597065052a0ae8dc5be156  go/internal/web/properties/apartmentnew/i18n.json
   7268ecee3cdfbad43ea5f3fd020f0157755c69d3d54a8ffbb7bd03e985c1387d  go/cmd/ubyhost-web/register_web_properties_apartment_new.go
   0cb6d7b27e9f15c8b4d4a334db9b4b8f64b6b7c11de48662a33fd5dd7da85318  go/cmd/ubyhost-web/register_web_properties_apartment_new_test.go
   1e9382a6ee83d9e8cbcbc541f66c8d774830fa97c21198b9e8827b1005c96090  App/scripts/go_apartment_new_form_golden.py
   26bff49ac72e47da4a1cdd5f60edcb3bdc71c79a1be37b80a50b22b384d98a05  App/tests/test_go_apartment_new_form_golden.py
   EOT
   ```

   Every line must end with `: OK` (9 lines). Then commit "1700a step 1" (`git add -A && git commit -m "1700a step 1"`).

2. Generate the golden from the real Python page (one call, repo root). `App/.venv` is ignored by git. Without it, create it first (this needs the package index; if it fails: STOP, the Go tests cannot run without the golden):

   ```bash
   cd App && (test -x .venv/bin/python || (python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt 2>&1 | tail -3)); .venv/bin/python scripts/go_apartment_new_form_golden.py 2>&1 | tail -2; .venv/bin/python scripts/go_apartment_new_form_golden.py --check 2>&1 | tail -2; echo "check rc=$?"; python3 -c "import json;g=json.load(open('../go/internal/web/properties/testdata/apartment_new_form_golden.json'));print(len(g['cases']),sorted(set(c['status'] for c in g['cases'])))"
   ```

   Expected: a line `wrote .../apartment_new_form_golden.json`, then `check rc=0` with nothing before it, then `21 [200, 303, 404]`. Then `git status --short | tail -5` shows only the golden file (`?? go/internal/web/properties/testdata/apartment_new_form_golden.json`). A different case or status count: STOP. Commit "1700a step 2" (`git add -A && git commit -m "1700a step 2"`).

3. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/properties cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/properties/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). Nothing changed, so no commit.

4. Python checks (repo root, one call):

   ```bash
   cd App && .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -5; echo "i18n rc=$?"; .venv/bin/python -m pytest tests/test_go_apartment_new_form_golden.py tests/test_go_host_i18n.py -q --tb=short -rs 2>&1 | tail -5
   ```

   Expected: `i18n rc=0` with nothing before it, and `3 passed` with no `skipped`. Nothing changed, so no commit.

5. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if it is already running (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55700/data status' | head -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55700 && chown postgres /var/tmp/pg55700 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55700/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55700/data -o "-p 55700 -k /var/tmp/pg55700" -l /var/tmp/pg55700/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55700/postgres` in step 6. No PostgreSQL 16 binaries at that path: write "CI only" in the report and STOP before step 6.

6. Run the tests on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55700/postgres go test ./internal/web/properties/... ./cmd/ubyhost-web/... -count=1 2>&1 | grep -E '^(ok|FAIL|---|panic)' | tail -30
   ```

   Expected: two `ok` lines (`.../go/internal/web/properties`, `.../go/cmd/ubyhost-web`), no `FAIL`. Then show the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55700/postgres go test ./internal/web/properties/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestApartmentNew' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of these 7 tests and two `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestApartmentNewVisibleLines
   --- PASS: TestApartmentNewMatchesPython
   --- PASS: TestApartmentNewRenderRefusal
   --- PASS: TestApartmentNewQueryInt
   --- PASS: TestApartmentNewTemplateKeys
   --- PASS: TestApartmentNewRegisterDoesNotTouchThePool
   --- PASS: TestApartmentNewRouteRegistered

   Then the skip count of the properties package: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55700/postgres go test ./internal/web/properties/... -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` must print `0`. (`./cmd/ubyhost-web/...` has 3 existing SKIPs: `TestJobRunProbe`, `TestRouteProbe`, `TestJobProbe`; they are probe tests that need their own variables and are not part of this brief.)

7. Write the report (§9), set `Status: review` in this file and commit "1700a step 7".

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file (Caddy, compose);any existing file of `go/internal/web/properties`, in particular `lists.go`, `properties.go`, `pages.go`, `i18n.json`, `i18n_keys.txt` (add new catalog files instead) and their tests; `go/cmd/ubyhost-web/register_web_properties.go`; anything under `App/app/` or `App/migrations_pg/` (Python still serves the page; no schema change); the other test files under `App/tests/`; filing code (`go/internal/ubyport`, `App/app/reporting.py`); the RUIAN suggest route and its script (`/apartments/ruian-suggest`, `static/ruian_suggest.js`: briefs 1700c and 1700d); the create route (`POST /apartments`: brief 1700b). Hard rules of AGENTS.md: no secret or guest datum in a file or a log (the test data is made up), nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 2, 3, 4 and 6). Test-map row: the coordinator adds `go test ./internal/web/properties/...` (PostgreSQL) plus `App/tests/test_go_apartment_new_form_golden.py` from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

UX gate (hard rule 10) for this host page: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots` `.venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30` green with 0 skipped, plus one 390, 768 and 1280 px screenshot of the new-property page in the report. **This gate is deferred to the path switch (owner item, as in brief 1595):** the Go page is dormant, the Python browser tests cannot reach the Go service, and `/apartments/new` is not in the page list of `test_layout_lint_browser.py`. The golden proves the Go page has the same text, ids, classes and attributes as the Python page, which the owner already uses. Before the switch the orchestrator runs the lint and the three screenshots against the Go service (rule 10, steps in [workflow](../context/workflow.md#ux-gate)) and writes per page what it saw in the PR.

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 9 files.
- [ ] Step 2: `check rc=0` and `21 [200, 303, 404]`; the golden is committed.
- [ ] The format, build and vet step printed nothing.
- [ ] Step 4: `i18n rc=0` and `3 passed`.
- [ ] Step 6: two `ok` lines, the 7 named tests `--- PASS`, properties SKIP count `0`.
- [ ] `git log --oneline --grep='^1700a step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1700a step') | tail -40` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env, migration or Python application file changed; nothing was pushed to `main`.
- [ ] UI: the page is dormant. The UX gate of §6 is pending (owner item) and is named in the report.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor, a hash, a file count or a golden count of step 0, 1 or 2 is not as stated;
- a test fails twice (read the last 30 lines, fix nothing in the sidecar files yourself: report);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency, a new column, a retention line or a new outbound request seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1700a-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git show --stat` as in §7).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. §7 ticked.
4. Deviations (including the deferred UX gate).
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `apartment_new.go` (every query scopes by `owner_user_id IS NOT DISTINCT FROM` the workspace id, also the `copy_from` source: another host's property must answer 404, the golden case "copy from another host" proves it; the signed-out redirect comes from `hostweb.Login`; no write; the query parser never panics on a hand-made number), `apartmentnew/apartment_new.tmpl` (the create form has `_csrf`; every value is escaped by `html/template`; no `safe`; the RUIAN script tag and `data-ruian-*` attributes are unchanged), and `register_web_properties_apartment_new.go` (one route, no pool use while building). The exported `RenderApartmentNew` and `ApartmentNewForm` are the contract with brief 1700b.

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1705, after 1700b ships `POST /apartments` (the Go form posts to it) and the UX gate of §6 passed on Go.
- **Rollback:** Revert the PR; the route was never switched.

## Owner steps

None now: nothing is switched on. Later, with brief 1705 (after 1700b and the UX gate), the path switch is:

1. On the server, open the env file that holds `UBYHOST_GO_PATHS` (see docs/ENVIRONMENT.md).
2. Add `/apartments/new` to the comma-separated list (exact path; `POST /apartments` has its own switch).
3. Run `scripts/caddy-validate.sh`, then `docker compose up -d caddy`.
4. Open `/apartments/new` signed in; the form must look the same as before. Rollback: remove `/apartments/new` again and repeat step 3.
