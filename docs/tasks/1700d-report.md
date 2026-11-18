# 1700d report: Go RUIAN suggest route (dormant)

Status: review

## 1. Files changed

Step commit `85d2247 1700d step 1` (4 files, 548 insertions):

- go/cmd/ubyhost-web/register_web_properties_ruian.go (24 lines)
- go/cmd/ubyhost-web/register_web_properties_ruian_test.go (23 lines)
- go/internal/web/properties/ruian_suggest.go (244 lines)
- go/internal/web/properties/ruian_suggest_test.go (257 lines)

Step 5 adds docs/tasks/1700d-report.md and sets Status in docs/tasks/1700d-go-ruian-suggest.md.

## 2. Commands

- Step 0 anchors: all 21 greps printed `1`. Route grep printed nothing. 4 new files absent. 4 sidecars present.
- Step 1: `sha256sum -c` printed `: OK` for all 4 files.
- Step 2 (gofmt, build, vet): no output.
- Step 3: PostgreSQL on 127.0.0.1:55700 already accepting connections, used as is.
- Step 4, last lines:
  - `ok  github.com/.../go/internal/web/properties  20.052s`
  - `ok  github.com/.../go/cmd/ubyhost-web  4.400s`
  - Named tests: 10 `--- PASS` (TestRuianSuggestResults, TwoRowsAndCap, SignedOutAndSwitches, ShortQuery, RateLimit, DatabaseErrorIsQuietAndPrivate, PureHelpers, RegisterDoesNotTouchThePool, Source, RouteRegistered).
  - Properties SKIP count: `0`.
- §7 greps: outbound HTTP count `0`. Lint: `context lint: OK`.

## 3. §7 ticked

- [x] Step 1 sha256 all OK
- [x] Step 2 printed nothing
- [x] Step 4: two `ok`, 10 tests PASS, SKIP count 0
- [x] JSON keys and bodies (covered by the passing tests)
- [x] 401 `[]`; disabled, short and rate-limited `200 []` (covered by the passing tests)
- [x] Rate limit scope `ruian`, key workspace id, 60/3600 s (covered by the passing tests)
- [x] No outbound request (count 0)
- [ ] Credit line in one place: see Deviations
- [ ] Step commits and stat: step 1 verified; step 5 pending the commit below
- [x] No `UBYHOST_GO_PATHS`, Caddy, compose, env, migration, template or Python change; nothing pushed

## 4. Deviations

- Credit-line grep: `grep -rlF 'Adresní data' go` also lists `go/internal/web/properties/ruian_suggest_test.go` (line 252). That line is a banned-strings guard in `TestRuianSuggestSource`, not a credit line. The brief's expected output is off by that file. The sidecar was not edited.
- No PR opened and nothing pushed, per the run rules for this session (the brief's "open one PR" was not done).
- Step 3 used the already-running PostgreSQL, so no server was started.
- Not checked: whether the 1700a/1700b briefs list this route (no file in §3 names them).

## 5. Questions

None.

## 6. Owner steps left

None for this brief (nothing is switched on). The orchestrator opens the PR from `claude/beautiful-archimedes-lxhrit`, and adds the test-map row: `go test ./internal/web/properties/... ./cmd/ubyhost-web/...` (PostgreSQL).
