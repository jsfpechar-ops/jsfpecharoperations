# 1700d: Go RUIAN suggest route on the local table

Status: done
Depends on: 1700c merged (table `ruian_address`, `ruian.Fold`, `ruian.SearchText`, `ruian.Attribution`; verified present at step 0), 1520 to 1524 (`ares.go` rate helpers, `lists.go` `queryLast`) | Base commit: current tip of the working branch | Branch: task/1700d-go-ruian-suggest
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (this brief needs about 14)
Tier: B (Sonnet wrote the exact-diff pass; the orchestrator reads the diff of the risk-listed files, see the end)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1700d step k` (`k` is the step number) and `git add` only the paths the step names (never `-A`, never `.`). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1700d step'`.

## 1. Objective

Serve `GET /apartments/ruian-suggest` from Go, querying the local `ruian_address` table with `pg_trgm`, with the same JSON shape and the same signed-out, disabled, short-query and rate-limit behaviour as Python's `apartments_ruian_suggest` (`App/app/routes/admin.py` ~1334). Replaces the live ČÚZK call (plan: [ruian-local](../plans/ruian-local.md) §3). The route stays dormant: nothing is added to `UBYHOST_GO_PATHS`.

## 2. Context

Rules (AGENTS.md): 1 filing correctness first (suggest only pre-fills form fields the host can still edit); 2 privacy first (nothing typed leaves the server, no outbound request, the typed text is never logged, no new personal-data field, no retention line); 3 no real data in tests (made-up rows); 4 no new dependency; 5 SQL with `$n` placeholders only, Postgres-only like the rest of `go/`, no schema change (the table comes from 1700c); 6 forms work without JavaScript (this is an enhancement endpoint, `[]` is always safe); 11 Go first.

**All code is pre-written, compiled and tested** (in a throwaway copy of this branch, with PostgreSQL 16). Sidecars: `docs/tasks/1700d-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. There is no golden file and no Python script (the Python route needs the network).

| sha256 | file | action | lines |
|---|---|---|---|
| `ccad292e13049156f9e67e0ef00f4c5bf958017bf4b5390a2006ac20f5819b27` | `go/internal/web/properties/ruian_suggest.go` | create | 244 |
| `b24664ed59403cb2507bfcf9ae0fa751e2096a112e6a88ca512eeb9def2cfd0d` | `go/internal/web/properties/ruian_suggest_test.go` | create | 257 |
| `0fa62ac22884d276d56f864b711228e1d0c14af1508c2e5334a8441735a3aba2` | `go/cmd/ubyhost-web/register_web_properties_ruian.go` | create | 24 |
| `1d92eef5368efd1bce902e590c5dfcf43c391f2553882581cbbc3947021aaac3` | `go/cmd/ubyhost-web/register_web_properties_ruian_test.go` | create | 23 |

**How the code is built (for the reviewer; the executor reads no Go file, it only copies and runs).**

- `ruian_suggest.go`: `RegisterRuianSuggest` mounts `GET /apartments/ruian-suggest` (same `Pages` struct and `wrap` as `RegisterApartmentNew`). The handler is the Python order: `session.Load` (no redirect: signed out is `401` body `[]`, as Python's `owner is None`), then the `UBYHOST_RUIAN_ENABLED` switch (`0`, `false`, `no`, `off` turn it off), then `usable_query` (white space collapsed, at least 3 characters), then `rateBlocked` (scope `ruian`, key the workspace id as text, 60 per 3600 s, the same `rate_limit_event` rows Python writes), then `rateRecord`, then the lookup. Every non-401 refusal is `200 []`; a database error is `200 []` and one log line `ruian suggest: lookup failed: <pg error>` without the typed text.
- The lookup folds the query with `ruian.Fold`, splits it into tokens (at most 8; Go-only cap), and builds `WHERE search LIKE $2 AND search LIKE $3 ...` with each token escaped (`\`, `%`, `_`) and wrapped in `%...%`, `ORDER BY similarity(search, $1::text) DESC, code LIMIT 6`. Every user value is a bind parameter; only the placeholder numbers are concatenated.
- Mapping (plan §3, Python's `_resolve` rules): `addr_street`, `addr_house_no` (also for a `č.ev.` row), `addr_orient_no` (letter included, from 1700c), `addr_zip`, `addr_obec`, `addr_obec_cast` only when the part differs from the obec, `addr_okres` from the bundled okres column (owner Q1 (b), filled by 1700c); empty values are omitted. Label `street no/orient, part, zip district-or-obec`; a village without a street reads `part no, zip obec`; an evidence number reads `č.ev. 12`. The JSON is compact UTF-8 (no `<` escapes), `[]` for nothing, `Content-Type: application/json`.
- `register_web_properties_ruian.go`: an `init()` through `registerRoutes`, next to the other `register_web_*.go` files (no existing file changes).
- `ruian_suggest_test.go` (Go only, expected bodies written by hand) seeds PostgreSQL with `seedHosts` and 14 made-up `ruian_address` rows: two Václavské rows, a village row, a `č.ev.` row, a part-equals-town row and eight "Capova" rows for the cap of six. It proves: diacritics and capitals fold, the letter after the orient number, six-result cap, `[]` and not `null`, `%`, `_` and `\` are literals, signed out is `401 []` and records nothing, every disabled spelling, short queries are not recorded (`a  b` counts as three characters), the 60/hour limit (59 events: the 60th lookup answers and is recorded, the 61st is `[]` and not recorded; host B has its own count; an admin previewing host B counts under host B; events older than an hour are pruned), a dropped table gives `200 []` and a log without the typed text, no outbound HTTP code and no copy of the credit line in the new file.
- `register_web_properties_ruian_test.go`: the route resolves to its own pattern and `GET /apartments` keeps its pattern. The mux matches the literal path before any `/apartments/{id}` pattern, so the Python trap (0884) cannot happen.

**Accepted differences:** `label` is built from our table, not the ČÚZK geocoder (same shape `street cp[/co], part, zip district`, not byte-equal); at most 8 query words are used; results come from the monthly RÚIAN copy, not the live geocoder; `HEAD` is served by the `GET` pattern.

**Verified by the brief writer** (in a throwaway worktree of the branch tip, sidecars copied as step 1 does, PostgreSQL 16 on port 55700, Go 1.24): `gofmt -l` printed nothing, `go build ./...` and `go vet ./internal/web/properties/... ./cmd/...` were silent, two `ok` lines in step 4, the 10 named tests `--- PASS`, properties SKIP count `0`, `go test -race` of the new tests green.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/ruian_suggest.go` | create | route, handler, query, mapping, JSON |
| `go/internal/web/properties/ruian_suggest_test.go` | create | tests with made-up rows inserted into `ruian_address` |
| `go/cmd/ubyhost-web/register_web_properties_ruian.go` | create | registers the route (`init()` through `registerRoutes`) |
| `go/cmd/ubyhost-web/register_web_properties_ruian_test.go` | create | route registration test |
| `docs/tasks/1700d-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1700d-report.md` | create | the report (§9) |

No other file may change. In particular none of the 1700b2 files (`go/internal/web/properties/apartment_create*.go`, `go/internal/validation/apartment_form*.go`, `go/cmd/ubyhost-web/register_web_properties_apartment_create*.go`) and no file of `go/internal/ruian/`.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `grep -cF 'func Fold(s string) string {' go/internal/ruian/fold.go | tail -1` prints `1`.
   - `grep -cF 'func SearchText(street, houseNo, orientNo, part, obec, zip string) string {' go/internal/ruian/fold.go | tail -1` prints `1`.
   - `grep -cF 'const Attribution = ' go/internal/ruian/attribution.go | tail -1` prints `1`.
   - `grep -cF 'CREATE UNLOGGED TABLE IF NOT EXISTS ruian_address (' App/migrations_pg/00021_ruian_address.sql | tail -1` prints `1`.
   - `grep -cF '@router.get("/apartments/ruian-suggest")' App/app/routes/admin.py | tail -1` prints `1`.
   - `grep -cF 'func rateBlocked(ctx context.Context, pool *pgxpool.Pool, scope, key string, max int64, window int64, at time.Time) (bool, error) {' go/internal/web/properties/ares.go | tail -1` prints `1`.
   - `grep -cF 'func rateRecord(ctx context.Context, pool *pgxpool.Pool, scope, key string, at time.Time) error {' go/internal/web/properties/ares.go | tail -1` prints `1`.
   - `grep -cF 'func queryLast(r *http.Request, key string) string {' go/internal/web/properties/lists.go | tail -1` prints `1`.
   - `grep -cF 'func itoa64(n int64) string {' go/internal/web/properties/entity_editor.go | tail -1` prints `1`.
   - `grep -cF 'type Pages struct {' go/internal/web/properties/pages.go | tail -1` prints `1`.
   - `grep -cF 'type Wrap func(route string, h http.HandlerFunc) http.Handler' go/internal/web/properties/properties.go | tail -1` prints `1`.
   - `grep -cF 'func Cookie(r *http.Request, name string) string {' go/internal/hostweb/hostweb.go | tail -1` prints `1`.
   - `grep -cF 'func Load(ctx context.Context, db *pgxpool.Pool, token string, now time.Time, getenv func(string) string) (*Host, error) {' go/internal/session/session.go | tail -1` prints `1`.
   - `grep -cF 'func testPool(t *testing.T) *pgxpool.Pool {' go/internal/web/properties/properties_test.go | tail -1` prints `1`.
   - `grep -cF 'func seedHosts(t *testing.T, pool *pgxpool.Pool) {' go/internal/web/properties/more_helpers_test.go | tail -1` prints `1`.
   - `grep -cF 'func getAs(t *testing.T, mux http.Handler, path string, uid, as int64, hdr map[string]string) *httptest.ResponseRecorder {' go/internal/web/properties/more_helpers_test.go | tail -1` prints `1`.
   - `grep -cF 'func moreEnv(extra map[string]string) func(string) string {' go/internal/web/properties/more_helpers_test.go | tail -1` prints `1`.
   - `grep -cF 'func oneInt(t *testing.T, pool *pgxpool.Pool, sql string, args ...any) int64 {' go/internal/web/properties/more_helpers_test.go | tail -1` prints `1`.
   - `grep -cF 'func mustExec(t *testing.T, pool *pgxpool.Pool, sql string, args ...any) {' go/internal/web/properties/more_helpers_test.go | tail -1` prints `1`.
   - `grep -cF 'func noWrap(_ string, h http.HandlerFunc) http.Handler {' go/internal/web/properties/more_helpers_test.go | tail -1` prints `1`.
   - `grep -cF 'func registerRoutes(fn func(*http.ServeMux, *metrics, *pgxpool.Pool)) {' go/cmd/ubyhost-web/registry.go | tail -1` prints `1`.
   - `grep -rcF 'GET /apartments/ruian-suggest' go/internal/web go/cmd --include=*.go | grep -v ':0' | tail -3` prints nothing (no Go route for the path exists yet; a comment in `apartment_new.go` names the path without the method, which is fine).
   - `ls go/internal/web/properties/ruian_suggest.go go/internal/web/properties/ruian_suggest_test.go go/cmd/ubyhost-web/register_web_properties_ruian.go go/cmd/ubyhost-web/register_web_properties_ruian_test.go 2>&1 | grep -c 'No such file' | tail -1` prints `4`.
   - `find docs/tasks/1700d-files -type f -name '*.txt' | wc -l | tail -1` prints `4`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1700d-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOT' 2>&1 | tail -10
   ccad292e13049156f9e67e0ef00f4c5bf958017bf4b5390a2006ac20f5819b27  go/internal/web/properties/ruian_suggest.go
   b24664ed59403cb2507bfcf9ae0fa751e2096a112e6a88ca512eeb9def2cfd0d  go/internal/web/properties/ruian_suggest_test.go
   0fa62ac22884d276d56f864b711228e1d0c14af1508c2e5334a8441735a3aba2  go/cmd/ubyhost-web/register_web_properties_ruian.go
   1d92eef5368efd1bce902e590c5dfcf43c391f2553882581cbbc3947021aaac3  go/cmd/ubyhost-web/register_web_properties_ruian_test.go
   EOT
   ```

   Every line must end with `: OK` (4 lines). Then commit: `git add go/internal/web/properties/ruian_suggest.go go/internal/web/properties/ruian_suggest_test.go go/cmd/ubyhost-web/register_web_properties_ruian.go go/cmd/ubyhost-web/register_web_properties_ruian_test.go && git commit -m "1700d step 1" | tail -3`.

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/properties cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/properties/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). Nothing changed, so no commit.

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server where you may create databases and the `postgres` role is a superuser (the test database migration runs `CREATE EXTENSION pg_trgm`, so the contrib package must be installed), use it and skip this step. If `pg_isready -h 127.0.0.1 -p 55700 | tail -1` says `accepting connections`, use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55700/postgres` and skip the start. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg55700 && chown postgres /var/tmp/pg55700 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55700/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55700/data -o "-p 55700 -k /var/tmp/pg55700" -l /var/tmp/pg55700/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. No PostgreSQL 16 binaries at that path, or `CREATE EXTENSION pg_trgm` is refused in the migration: write "CI only" in the report and STOP before step 4.

4. Run the tests on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55700/postgres go test ./internal/web/properties/... ./cmd/ubyhost-web/... -count=1 2>&1 | grep -E '^(ok|FAIL|---|panic)' | tail -30
   ```

   Expected: two `ok` lines (`.../go/internal/web/properties`, `.../go/cmd/ubyhost-web`), no `FAIL`. Then show the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55700/postgres go test ./internal/web/properties/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestRuianSuggest' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of these 10 tests and two `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestRuianSuggestResults
   --- PASS: TestRuianSuggestTwoRowsAndCap
   --- PASS: TestRuianSuggestSignedOutAndSwitches
   --- PASS: TestRuianSuggestShortQuery
   --- PASS: TestRuianSuggestRateLimit
   --- PASS: TestRuianSuggestDatabaseErrorIsQuietAndPrivate
   --- PASS: TestRuianSuggestPureHelpers
   --- PASS: TestRuianSuggestRegisterDoesNotTouchThePool
   --- PASS: TestRuianSuggestSource
   --- PASS: TestRuianSuggestRouteRegistered

   Then the skip count of the properties package: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55700/postgres go test ./internal/web/properties/... -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` must print `0`. (`./cmd/ubyhost-web/...` has 3 existing SKIPs: `TestJobRunProbe`, `TestRouteProbe`, `TestJobProbe`; they are probe tests that need their own variables and are not part of this brief.) A failing test: read the last 30 lines, change nothing in the sidecar files, STOP (§8).

5. Write the report (§9), set `Status: review` in this file and commit: `git add docs/tasks/1700d-report.md docs/tasks/1700d-go-ruian-suggest.md && git commit -m "1700d step 5" | tail -3`.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file (Caddy, compose, env files); any existing file of `go/internal/web/properties` (in particular `ares.go`, `lists.go`, `properties.go`, `pages.go`, `i18n.json`, `i18n_keys.txt`) and its tests; the 1700b2 files named in §3; `go/internal/ruian/**` (owned by 1700c); `go/cmd/ubyhost-web/register_web_properties.go`; the shared `handlers.go`; anything under `App/` (Python keeps serving the route and the script `ruian_suggest.js`; `App/app/ruian.py` and `admin.py` stay until a later cleanup brief); `docs/ENVIRONMENT.md`; the templates and `go/internal/web/properties/apartmentnew/**` (1700a's form calls the route through the existing script, unchanged). If 1700a or 1700b briefs still list this route, say so in the report; do not edit them.

## 6. Commands

Exactly the commands of §4 (steps 2 and 4). Test-map row: the coordinator adds `go test ./internal/web/properties/... ./cmd/ubyhost-web/...` (PostgreSQL) from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

No screenshots and no UX gate: no template, CSS or page changes, and the route is a JSON endpoint. The credit line is not shown by this brief (brief 1700e puts it on the privacy/licence page).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 4 files.
- [ ] The format, build and vet step (2) printed nothing.
- [ ] Step 4: two `ok` lines, the 10 named tests `--- PASS`, properties SKIP count `0`.
- [ ] For the fixture rows the JSON keys are the Python keys: `label` and `fields` with only `addr_street, addr_house_no, addr_orient_no, addr_zip, addr_obec, addr_obec_cast, addr_okres` (the tests compare whole bodies).
- [ ] Signed out is `401` body `[]`; disabled, short and rate-limited requests are `200` body `[]` (as Python).
- [ ] The rate limit uses scope `ruian`, key the workspace id, 60 per 3600 s, in `rate_limit_event` (shared with Python, so a path switch does not reset the count).
- [ ] No outbound request: `grep -cE 'http\.(Client|Get|Post|NewRequest)' go/internal/web/properties/ruian_suggest.go | tail -1` prints `0`.
- [ ] The credit line is in one place: `grep -rlF 'Adresní data' go --include=*.go | tail -5` lists only `go/internal/ruian/attribution.go`.
- [ ] `git log --oneline --grep='^1700d step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1700d step') | tail -40` lists only the paths of §3.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env, migration, template or Python application file changed; nothing was pushed to `main`.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor, a hash or a file count of step 0 or 1 is not as stated (in particular `ruian_address`, `ruian.Fold` or `ruian.SearchText` missing or different: 1700c is not merged or changed);
- the `pg_trgm` extension cannot be created in the test database, or a test needs a skip;
- a test fails twice (do not edit the sidecar files: report);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency, a new column, a retention line or a new outbound request seems needed;
- a file outside §3 needs a change, or §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1700d-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git show --stat` as in §7).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. §7 ticked.
4. Deviations.
5. Questions: none expected. Settled by the orchestrator 2026-11-17: (1) the credit line `ruian.Attribution` goes on the privacy/licence page (plan ruian-local §4 line "Attribution line … privacy/licence page"), brief 1700e; this brief shows nothing; (2) `č.ev.` rows return the evidence number as `addr_house_no`, as Python `App/app/ruian.py` does with `cislodomovni` for every address type.
6. Owner steps left.

## Risk list (for the reviewer)

Read `ruian_suggest.go` fully (244 lines): (a) **owner scoping**: the route needs a session (`session.Load`; signed out is `401 []`), the rate key is the workspace id (an admin previewing a host counts under the host), and the table `ruian_address` is public address data with no owner column, so there is no row to leak; (b) **rate limit order**: switch, then query length, then `rateBlocked`, then `rateRecord`, then the lookup; a refused request is never recorded, as in Python; (c) **LIKE escaping and the cap**: `ruianLikeEscape`, bind parameters only, `LIMIT 6`, at most 8 tokens; (d) **no personal data and no outbound request**: the typed text is only a bind parameter, no log line contains it (`TestRuianSuggestDatabaseErrorIsQuietAndPrivate`), no HTTP client is imported; (e) the empty answer is `[]`, never `null`. Also read `register_web_properties_ruian.go` (24 lines): the route is registered but dormant.

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1705 (after 1700a, 1700b and the UX gate), and only after 1700c has loaded the table (`SELECT rows FROM ruian_import;`) and the owner has run `CREATE EXTENSION pg_trgm;` once (owner step of 1700c). Until the path is switched, Python keeps answering from ČÚZK.
- **Rollback:** Revert the PR; the route was never switched. After a switch: remove the path again (owner steps below).

## Owner steps

None now: nothing is switched on. Later, with brief 1705, after 1700c has loaded the table (`SELECT rows FROM ruian_import;` shows about 3,000,000):

1. On the server, open the env file that holds `UBYHOST_GO_PATHS` (see docs/ENVIRONMENT.md).
2. Add `/apartments/ruian-suggest` to the comma-separated list (exact path, before `/apartments/*` if that is listed).
3. Run `scripts/caddy-validate.sh`, then `docker compose up -d caddy`.
4. On the new-property form, type "vaclavske 12": suggestions appear. Rollback: remove `/apartments/ruian-suggest` again and repeat step 3.
