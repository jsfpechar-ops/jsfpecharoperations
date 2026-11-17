# 1701: Go property settings 2: property detail page (GET /apartments/{id})

Status: todo — exact-diff pass done 2026-11-17
Depends on: 1700a, 1700b2, 1700d merged (`ApartmentNewForm`, `apartmentNewQueryInt`, `notPorted`, `slug.go`, the `properties` test helpers), 1599 (`onboarding` setup state), 1446 (`ai.LeonStore`); verified present at step 0 | Base commit: current tip of the working branch | Branch: task/1701-go-apartment-detail-page
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (this brief needs about 16)
Tier: B (Sonnet wrote the exact-diff pass; the orchestrator reads the diff of the risk-listed files, see the end)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1701 step k` (`k` is the step number) and `git add` only the paths the step names (never `-A`, never `.`). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1701 step'`, never a fixed base commit.

## 1. Objective

Port the `GET /apartments/{apartment_id}` page of the host app (`apartment_detail` and `_render_apartment_detail`, `App/app/routes/admin.py` 1859-1873 and 2097-2240; template `App/app/templates/apartment_form.html`, edit branch, with `_property_editor.html`, `_property_calendars.html`, `_police_fields.html` and the small partials they include) to the existing Go package `go/internal/web/properties`, and register it in ubyhost-web. Owner decision of 2026-11-17: the page is ported **as it is today, no redesign**. Routes stay dormant: nothing is added to `UBYHOST_GO_PATHS` (brief 1705). The forms keep posting to the current Python actions.

**This brief ports the whole page except one section.** The exact-diff pass found the page too large for one brief (about 3000 lines of Jinja and helpers), so the Stay fee section (`sec-fee`: `_stay_fee_fields.html`, `_fee_signature_fields.html`, the guest-pay QR preview, the fee copy dropdown) is **brief 1701b** and is marked in the template by the anchor `1701b-fee`. The page works without it (the pill and the nav dot of "Stay fee" still show, the section body is missing). The route must not be switched on before 1701b is done.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (a read page; the one write is the PIN backfill Python also does); 2 privacy: no new personal-data field, no retention line, no outbound request (the page reads the host's own rows; the QR of the guest link is drawn locally); 3 fixtures are made up (`@example.test`); 4 no new dependency (`golang.org/x/text/unicode/norm` is already in go.mod); 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, no schema change; 6 light mode, every Go form carries `<input type="hidden" name="_csrf" value="{{csrf}}">` so it works without JavaScript; 11 Go first, per the owner decision of 2026-11-17 the tests are Go only with hand-written expected strings (no Python golden script, no `App/` file).

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1701-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `c7a90ed8d4f4c1de24756b34c8ee01b9cd087d7378e93d29a25cf934f031fc52` | `go/internal/web/properties/apartment_detail.go` | create | 709 |
| `3623b0a36537693cfcac555fe611a31a25530f625c61c7b4346d5a788e64df10` | `go/internal/web/properties/apartment_detail_data.go` | create | 1010 |
| `e62847afd9f038ca84b8e07511a06e22befb48c2ca221476e843d6d9428b965c` | `go/internal/web/properties/apartment_detail_police.go` | create | 85 |
| `1f9e7b4c011871b6df2abb7b5ca0ca76b21955f107e1bceb9f5eaa0bb837d1e5` | `go/internal/web/properties/apartment_detail_test.go` | create | 600 |
| `70e231195134191bcbde02b7b4ff954de566558212a6d1790b40660885c25a22` | `go/internal/web/properties/apartmentdetail/apartment_detail.tmpl` | create | 755 |
| `7b4ce5ec57e24d338b18187c6d0fbdd929afd94630d693c0b31238a6839f4270` | `go/internal/web/properties/apartmentdetail/i18n_keys.txt` | create | 225 |
| `998381ab0949698865e61b0c5c9211c18430ca5e9063f104d227d9f3fd8d55e8` | `go/internal/web/properties/apartmentdetail/i18n.json` | create | 1040 |
| `a6fd7db04c643f89e597d58f842bd4733f237e79c4b77955f2762da46b629f80` | `go/cmd/ubyhost-web/register_web_properties_apartment_detail.go` | create | 24 |
| `eae02393ca3b751335962ca3ca1db8b112bea552b2bf729bf7d119b1c5858214` | `go/cmd/ubyhost-web/register_web_properties_apartment_detail_test.go` | create | 25 |
| `6a31c09edd4aeff732ab2f5b882f32bf70f74b65289e9c4083ec88c1aab96ebd` | `go/internal/palette/slug_export.go` | create | 12 |

**How the code is built (for the reviewer; the executor reads no Go file, it only copies and runs).**

- `apartment_detail.go`: `RegisterApartmentDetail` adds `GET /apartments/{id}`. `apartmentDetail` is the Python route in its order: the int path parameter (`parseID`), then `hostweb.Login` (`require_login`), then the workspace-scoped load, the PIN backfill, the copy dialog and `copy_from`, then `detailBuild` (= `_render_apartment_detail`) and `layout.Render` with nav `apartments`, body kind `detail`, `V2`, how key `property`. `detailView` is the template context; `derive` computes what the Jinja `{% set %}` lines compute (address text, the six pills, the missing lists, which sections start open, the section header texts, the selected operator, the address boxes through the existing `ApartmentNewForm.view`). `detailLeonCard` reuses `ai.LeonStore` (`Offered`, `Facts`, `LeonHostState`). Methods `HourSelected`, `Window`, `FacilityHelp`, `ReachbackDays` carry the small Jinja expressions.
- `apartment_detail_data.go`: one function per Python helper, named after it in its comment: `detailLoad` (`access.apartment`, `owner_user_id IS NOT DISTINCT FROM $2`), `detailEnsurePIN`, `detailApplyCopy` (`_apply_property_copy`), `detailEntities`, `detailControllerComplete` (`guest.controller_complete`), `detailFeeds` (`_feed_display`), `detailIssues` and `detailReadinessOf` (`_apartment_issues`, `_readiness`, through `validation.ValidateApartment`), `detailHealth` (`property_health.checks`), `detailDoorContext` (`_door_code_context`, `ttlock.allowed_for`), `detailLinkKey` (`guest_slug.link_key`, through `palette.EnsureGuestSlug`; no second slug generator), `detailNextStay` (`workflow.next_stay_window`), `detailGuideBundle`, `detailSetupState` and `detailSetupProgress` (`_setup_guide_bundle`, `_setup_state`, `_setup_progress`, on top of the exported `onboarding` setup functions), `detailPurposes` (`codelists.purpose_options("en")`).
- `apartment_detail_police.go`: `police_check.findings_for` for a GET (the local findings and `first_filing`; the letter findings exist only on a POST re-render).
- `apartmentdetail/apartment_detail.tmpl`: the Go twin of the Jinja files named in its first comment. No `safe` anywhere; every value is escaped by `html/template`; the only markup built in Go is `FacilityHelp` (escaped texts plus the fixed example line, as Jinja's `{% set facility_help %}` block). The macros `section_notice`, `sec_state`, `section_missing`, `police_box`, `address_input`, the door-code window and the smart-lock panel are `{{define}}` blocks. The anchor `1701b-fee` marks where the Stay fee section goes.
- `i18n_keys.txt` / `i18n.json`: the page catalog, written by `App/scripts/go_host_i18n.py` (its glob finds the nested file). The layout catalog is separate; keys used here are repeated in the page catalog so `detailT` can read them in Go.
- `register_web_properties_apartment_detail.go`: an `init()` that adds `GET /apartments/{id}` through `registerRoutes`; the test checks that `/apartments/new`, `/apartments`, `/apartments/{id}/leon/setup` and `POST /apartments/{id}/archive` keep their own patterns.
- Tests (all Go, expected strings written by hand from the Python page): access and owner scope (signed out, another host, unknown and non-numeric ids, admin previewing, archived property, `copy_from` of another host); the whole English page of a complete property; a bare property (missing lists, PIN backfill, no operator); archived; the query flags (`view`, `section`, `sec`, `err`, `msg`, `saved`, `return_to`, `add_calendar`, `created`); cs and vi; first setup, hidden and finished guide; the ready card shown once; copy-from merge; health pills from alerts and calendar errors; door-code states and the arrival/departure window incl. the midnight wrap, the lock lists, the plan gate; the Leon card gates; the police findings; helper unit tests.

**What the page shows beyond the Python GET context** is nothing: every `{% if %}` that Python fills only on a POST re-render (`save_errors`, `operator_error`, `letter_*`, `feed_draft`, `feed_errors`, `shared_time_error`, `lock_times_error`, `setup_guide`) is left out; the fields render with the stored values.

**Accepted differences (only reachable with hand-made data or requests, or by design):**

- Whitespace and indentation of the markup differ from Jinja's output; elements, classes, ids, attributes and their order are the same.
- A path id that is not a number, a property that is not in the workspace, and a `copy_from` made of non-ASCII digits answer **501 with `X-Ubyhost-Not-Ported: 1`**, so Caddy re-sends the GET to Python, which draws its branded 404 page (the Go error page does not exist yet). A `copy_from` that names no property of the workspace answers plain text `Not found.` with 404, as Python does.
- The Stay fee section is missing until 1701b (see §1).
- The `sync_calendars_button` form (layout macro) has no `_csrf` input, as Python's macro has none; `csrf.js` adds it in the browser.
- `police_check._fold` uses NFKD plus lower case (and `ß` as `ss`) where Python uses `casefold`; the two differ only for exotic scripts.
- The controller entity is read with the owner scope here; Python reads it by id alone (a foreign id on a property cannot be made by the app).
- `HEAD` is served by the `GET` pattern.
- The TTLock lock list is the stored `locks_json`, as in Python; no TTLock call is made on a GET.

**Where brief 1702 (POST /apartments/{id}, door codes) and 1703 (the small POSTs) extend this page** (also named in the report):

- `detailView` in `apartment_detail.go`: add the POST-only context fields next to `Status` (the comment above the type lists them) and call `detailBuild` then `layout.Render(..., "apartmentdetail", view)` for a refused save with `Status` 400, the way `apartmentDetail` does.
- `apartment_detail.tmpl`: the settings form `<form method="post" action="{{.Base}}" ... id="property-settings-form">` (1702: its fields, the `save_errors` banner above the savebar, the hour selects with `lock_checkin_hour` and `lock_checkout_hour`, `door_code_section`); the form `lock-state-form` with `action="/apartments/{{$a.ID}}/door-codes"` (1702); the blocks `{{define "apartmentdetail.calendars"}}` (1703: the add-feed form, `feed_draft` and `feed_errors` on the four inputs), `<form id="police-letter-form" ... /police-letter>` and the `formaction=".../test-connection"` button (1703), the two forms `action="/apartments/{{$a.ID}}/setup"` of the continue card (1703), and the `/smart-locks/setup`, `/smart-locks/refresh`, `/smart-locks/remove` forms in `{{define "apartmentdetail.locks"}}`.
- `apartment_detail_data.go`: `detailIssues`, `detailReadinessOf` and `detailHealth` are what 1702 calls after a save to build the "missing" flash.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/apartment_detail.go` | create | handler, view, derive |
| `go/internal/web/properties/apartment_detail_data.go` | create | the Python helpers as Go reads |
| `go/internal/web/properties/apartment_detail_police.go` | create | police_check findings for a GET |
| `go/internal/web/properties/apartment_detail_test.go` | create | Go tests with hand-written expectations |
| `go/internal/web/properties/apartmentdetail/apartment_detail.tmpl` | create | Go twin of the Jinja page |
| `go/internal/web/properties/apartmentdetail/i18n_keys.txt` | create | page catalog keys |
| `go/internal/web/properties/apartmentdetail/i18n.json` | create | page catalog (generated, checked in step 3) |
| `go/cmd/ubyhost-web/register_web_properties_apartment_detail.go` | create | registers `GET /apartments/{id}` |
| `go/cmd/ubyhost-web/register_web_properties_apartment_detail_test.go` | create | route registration test |
| `go/internal/palette/slug_export.go` | create | exported `EnsureGuestSlug`, a wrapper of the existing `ensure` |
| `docs/tasks/1701-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1701-report.md` | create | the report (§9) |

No other file may change. Briefs 1702, 1703 and 1701b extend these files and must run after this one.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `ls go/internal/web/properties/apartment_detail.go go/internal/web/properties/apartmentdetail 2>&1 | tail -2` says "No such file" twice (nothing of this brief exists yet).
   - `grep -rnF '"GET /apartments/{id}"' go/cmd go/internal | tail -3` prints nothing (the page route is not registered yet).
   - `find docs/tasks/1701-files -name '*.txt' | wc -l | tail -1` prints `10`.
   - Each of the following prints `1` (one call per line, `grep -cF '<text>' <file> | tail -1`):
     - `go/internal/web/properties/properties.go`: `func parseID(raw string) (int64, bool) {` and ``	aptPINSQL          = `UPDATE apartment SET permalink_pin = $1 WHERE id = $2` ``
     - `go/internal/web/properties/lists.go`: `func notPorted(w http.ResponseWriter, what string) {` and `func queryLast(r *http.Request, key string) string {`
     - `go/internal/web/properties/apartment_new.go`: `func apartmentNewQueryInt(r *http.Request, key string) (n int64, ok bool) {`, `func (f ApartmentNewForm) view(title string) apartmentNewView {` and `type apartmentNewAddr struct {`
     - `go/internal/web/properties/localpath.go`: `func safeLocalPath(value, def string) string {` and `func pyStrip(s string) string {`
     - `go/internal/web/properties/slug.go`: `func generatedReadable(name string) string {`, `func randomString(n int) (string, error) {`, `func newPermalinkPIN() (string, error) {`, ``	slugLockSQL    = `SELECT pg_advisory_xact_lock(hashtext($1), $2)` ``, ``	slugTakenSQL   = `SELECT 1 FROM apartment_slug WHERE slug = $1` `` and `	codeLength       = 6`
     - `go/internal/hostweb/layout/pagefuncs.go`: `func MustParseFuncs(cat hostweb.Catalog, funcs template.FuncMap, fsys fs.FS, patterns ...string) *Templates {`
     - `go/internal/web/onboarding/setup.go`: `func Load(ctx context.Context, s Settings, apartmentID int64) (*State, error) {`, `func Finish(ctx context.Context, s Settings, apartmentID int64) error {`, `func CelebrateOnce(ctx context.Context, s Settings, apartmentID int64) (bool, error) {`, `func Current(apt Apartment, state *State, f Facts, lockAvailable bool) *Guide {`, `func SectionDone(section string, apt Apartment, facts Facts, state *State) bool {`, `func OpenSection(apt Apartment, facts Facts, state *State) string {`, `func SetupComplete(apt Apartment, facts Facts, state *State) bool {`, `func IsFirstSetup(state *State) bool {`, `func DoneCount(state *State, apt Apartment, facts Facts, lockAvailable bool) int {`, `func LegacyState() *State {`, `var SectionMinutes = map[string]int{` and `func PoolSettings(pool *pgxpool.Pool) Settings { return poolSettings{pool: pool} }`
     - `go/internal/palette/slug.go`: `func ensure(ctx context.Context, pool pgxPool, a apartment) (string, error) {`
   - `go/internal/web/ai/leon_facts.go`: `func (s LeonStore) Offered(ctx context.Context, a LeonApartment) (bool, error) {` and `func LeonHostState(a LeonApartment, live bool) string {`; `go/internal/web/ai/havel_store.go`: `func HavelAIOn(env HavelEnv, feature, email string) bool {`
     - `go/internal/web/exports/housebook_view.go`: `func DateCZ(v string) string { return dateCZ(v) }`
     - `go/internal/payments/qrdatauri.go`: `func QRDataURI(payload string) (string, error) {`; `go/internal/ttlock/api.go`: `func ParseLocks(raw []byte) ([]Lock, error) {`; `go/internal/secure/datakeys.go`: `func LoadDataKeys(getenv func(string) string) (*MultiFernet, error) {`; `go/internal/validationi18n/localize.go`: `func Localize(message, lang string) string {`
     - `go/internal/validation/ws_user.go`: `func MarkFromWSUser(user string) string {`; `go/internal/validation/validation.go`: `func ValidateApartment(ap map[string]string) []Issue {` and `func ErrorsOnly(issues []Issue) []Issue {`
     - `go/cmd/ubyhost-web/registry.go`: `func registerRoutes(fn func(*http.ServeMux, *metrics, *pgxpool.Pool)) {`
     - the test helpers the new test uses: `go/internal/web/properties/apartment_new_test.go`: `func apartmentNewSignIn(req *http.Request, user, workspace int64, lang string) {` and `func apartmentNewGetenv(k string) string {`; `go/internal/web/properties/properties_test.go`: `func testPool(t *testing.T) *pgxpool.Pool {`; `go/internal/web/properties/more_helpers_test.go`: `func seedHosts(t *testing.T, pool *pgxpool.Pool) {`, `func mustExec(t *testing.T, pool *pgxpool.Pool, sql string, args ...any) {` and `func noWrap(_ string, h http.HandlerFunc) http.Handler { return h }`

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1701-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF2' 2>&1 | tail -10
   c7a90ed8d4f4c1de24756b34c8ee01b9cd087d7378e93d29a25cf934f031fc52  go/internal/web/properties/apartment_detail.go
   3623b0a36537693cfcac555fe611a31a25530f625c61c7b4346d5a788e64df10  go/internal/web/properties/apartment_detail_data.go
   e62847afd9f038ca84b8e07511a06e22befb48c2ca221476e843d6d9428b965c  go/internal/web/properties/apartment_detail_police.go
   1f9e7b4c011871b6df2abb7b5ca0ca76b21955f107e1bceb9f5eaa0bb837d1e5  go/internal/web/properties/apartment_detail_test.go
   70e231195134191bcbde02b7b4ff954de566558212a6d1790b40660885c25a22  go/internal/web/properties/apartmentdetail/apartment_detail.tmpl
   7b4ce5ec57e24d338b18187c6d0fbdd929afd94630d693c0b31238a6839f4270  go/internal/web/properties/apartmentdetail/i18n_keys.txt
   998381ab0949698865e61b0c5c9211c18430ca5e9063f104d227d9f3fd8d55e8  go/internal/web/properties/apartmentdetail/i18n.json
   a6fd7db04c643f89e597d58f842bd4733f237e79c4b77955f2762da46b629f80  go/cmd/ubyhost-web/register_web_properties_apartment_detail.go
   eae02393ca3b751335962ca3ca1db8b112bea552b2bf729bf7d119b1c5858214  go/cmd/ubyhost-web/register_web_properties_apartment_detail_test.go
   6a31c09edd4aeff732ab2f5b882f32bf70f74b65289e9c4083ec88c1aab96ebd  go/internal/palette/slug_export.go
   EOF2
   ```

   Every line must end with `: OK` (10 lines). Then commit "1701 step 1" (`git add go && git commit -m "1701 step 1" | tail -3`).

2. Format, build and vet (one call, repo root):

   ```bash
   cd go && gofmt -l internal/web/properties cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/properties/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). Nothing changed, so no commit.

3. Catalog check (repo root). If `App/.venv/bin/python` does not exist, write "Python checks: CI only (no App/.venv)" in the report and go to step 4. Else run (one call):

   ```bash
   cd App && .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -5; echo "i18n rc=${PIPESTATUS[0]}"; .venv/bin/python -m pytest tests/test_go_host_i18n.py -q --tb=short -rs 2>&1 | tail -5
   ```

   Expected: `i18n rc=0` with nothing before it, and a `passed` line with no `skipped`. Nothing changed, so no commit.

4. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if it is already running (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55701/data status' | head -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55701 && chown postgres /var/tmp/pg55701 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55701/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55701/data -o "-p 55701 -k /var/tmp/pg55701" -l /var/tmp/pg55701/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55701/postgres` in step 5. No PostgreSQL 16 binaries at that path: write "CI only" in the report and STOP before step 5.

5. Run the Go tests on PostgreSQL (one call, from the repo root):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55701/postgres go test ./internal/web/properties/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: two `ok` lines (`.../go/internal/web/properties`, `.../go/cmd/ubyhost-web`). Then show the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55701/postgres go test ./internal/web/properties/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestApartmentDetail|^TestDetailHelpers$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of these 15 tests (any order) and two `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestApartmentDetailAccess
   --- PASS: TestApartmentDetailPage
   --- PASS: TestApartmentDetailBare
   --- PASS: TestApartmentDetailArchived
   --- PASS: TestApartmentDetailQuery
   --- PASS: TestApartmentDetailLanguages
   --- PASS: TestApartmentDetailSetup
   --- PASS: TestApartmentDetailReadyCard
   --- PASS: TestApartmentDetailCopy
   --- PASS: TestApartmentDetailHealth
   --- PASS: TestApartmentDetailDoor
   --- PASS: TestApartmentDetailLeon
   --- PASS: TestApartmentDetailPoliceFindings
   --- PASS: TestDetailHelpers
   --- PASS: TestApartmentDetailRouteRegistered

   Then the skip count of the properties package: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55701/postgres go test ./internal/web/properties/... -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` must print `0`.

6. UX gate (AGENTS.md rule 10, [workflow](../context/workflow.md#ux-gate)). The page is dormant: the Python browser tests and the shots tool cannot reach the Go service, so they cannot prove this page yet. Do what can run now, and write the rest into the report as pending (owner item, as for 1595 and 1704a):
   - Read `docs/design/pages/properties.md` and tick `docs/design/design-system.md` section 5 in the report (the template keeps Python's classes and markup; the diff to Python is `_csrf` only on the Go forms).
   - If `App/.venv/bin/python` exists, run the Python baseline, which draws the same page from Jinja: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30`. Expected: a `passed` line, 0 skipped. Else write "UX baseline: CI only (no App/.venv)".
   - **Pending until the path is switched and 1701b is in:** `/tmp/shots/layout-lint/apartment-detail-{390,768,1280}.png` of the Go page, opened and described per width ("390: ...; 768: ...; 1280: ..."), with `test_layout_lint_browser.py` green on Go. Nothing to commit here.

7. Write the report (§9), set `Status: review` in this file, and commit "1701 step 7".

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `App/` (no Python file changes; Python still serves the page); `docs/ENVIRONMENT.md`, Caddy and compose files; every other file under `go/`: in particular `go/internal/web/properties/i18n.json` and the other `apartmentnew/` and `apartmentcreate/` catalogs, `go/internal/web/onboarding/`, `go/internal/hostweb/`, `go/internal/web/ai/`; the existing POST routes of `properties.go` (archive, unarchive, regenerate-pin, regenerate-link, feed delete) and `apartment_create.go`. Hard rules of AGENTS.md: no secret or guest datum in a file or a log (the seed is made up; no real document number or e-mail).

## 6. Commands

Exactly the commands of §4 (steps 2, 3, 5 and 6). Test-map row "Host pages, templates, CSS": the Python side is run by CI; the Go side has no row yet, the coordinator adds `go test ./internal/web/properties/... ./cmd/ubyhost-web/...` (PostgreSQL) from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 10 files.
- [ ] The format, build and vet step printed nothing.
- [ ] Step 3: `i18n rc=0` and a `passed` line, or "CI only (no App/.venv)" in the report.
- [ ] Step 5: two `ok` lines, the 15 named tests `--- PASS`, SKIP count `0`.
- [ ] `git log --oneline --grep='^1701 step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1701 step') | tail -40` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python file changed; nothing was pushed to `main`.
- [ ] UI: dormant page. **The visual and UX gate (screenshots at 390, 768 and 1280, layout lint on Go) is pending** until 1701b is in and the owner switches the path (Owner steps).

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

Write `docs/tasks/1701-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git show --stat` as in §7).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left, and "1701b (Stay fee section) is the next brief; the route must not be switched on before it".

## Risk list (for the reviewer)

Read `apartment_detail_data.go` (every read starts from `detailLoad`, which is scoped by `owner_user_id IS NOT DISTINCT FROM $2` with `session.Host.Workspace.ID`; the child reads of feeds, alerts, reservations, submissions and slugs start from that checked id; the two writes are the PIN backfill and the slug insert, done by `palette.ensure` under the advisory lock; the password is decrypted only to feed `ValidateApartment` and never rendered; `detailLockAllowed` copies the plan test of the wizard), `apartment_detail.go` (the order parse id, login, load; the `notPorted` fallbacks; `copy_from` reaches only the workspace's own rows; the query values `msg`, `err`, `sec`, `return_to` are escaped or pass `safeLocalPath` and the fee-return test; `ReadyQR` is the one `template.URL`, built from the QR of the guest link), and `apartment_detail.tmpl` (every `method="post"` form has `_csrf`, the test checks it; no `safe`; `FacilityHelp` is the only HTML built in Go).

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1705, after 1701b, 1702 and 1703.
- **Rollback:** Revert the PR.

## Owner steps

None now: nothing is switched on. Later, after 1701b to 1703 are in and the UX gate of §7 passed on Go (owner item), the path switch is brief 1705.
