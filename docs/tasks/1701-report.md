# 1701 report: GET /apartments/{id} (Go, dormant)

Status: review. Branch: claude/beautiful-archimedes-lxhrit. Commits: `1701 step 1` (5aa4d42). Steps 2, 4 and 5 changed no files.

## 1. Files changed (`git show --stat`)

10 files, 4485 insertions, all created: the §3 paths under `go/internal/web/properties/` (apartment_detail.go, _data.go, _police.go, _test.go, apartmentdetail/apartment_detail.tmpl, i18n_keys.txt, i18n.json), `go/cmd/ubyhost-web/register_web_properties_apartment_detail{,_test}.go`, `go/internal/palette/slug_export.go`. No Python, Caddy, compose, env or `UBYHOST_GO_PATHS` change.

## 2. Commands (last lines of output)

- Step 0 anchors: all 47 expected lines matched 1 (route not registered, 10 sidecars present, both "No such file" lines present).
- Step 1 `sha256sum -c`: 10 of 10 `: OK`.
- Step 2 gofmt, `go build ./...`, `go vet`: no output.
- Step 3: "Python checks: CI only (no App/.venv)".
- Step 4: server on port 55701 started (see Deviations); stopped at the end.
- Step 5 `go test ./internal/web/properties/... ./cmd/ubyhost-web/...`: `ok` (properties 36.5s), `ok` (ubyhost-web 7.8s).
- Step 5 named tests: 14 `--- PASS` in properties, `--- PASS: TestApartmentDetailRouteRegistered` in ubyhost-web (15 of 15), no FAIL.
- Step 5 SKIP count for `./internal/web/properties/...`: 0.
- Context lint: `context lint: OK`, rc=0.

## 3. §7 acceptance

- [x] sha256 10/10 OK
- [x] format, build, vet silent
- [ ] Step 3 i18n check: CI only (no App/.venv)
- [x] Step 5: two `ok`, 15 named tests PASS, SKIP 0
- [x] Step commits listed; stat shows only §3 paths and sidecars
- [x] No path added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python change; no push
- [ ] UI gate (390/768/1280 screenshots, layout lint on Go): pending, owner item until 1701b and the path switch

## 4. Deviations

- Step 4: `/var/tmp/pg55701/data` already existed (PG_VERSION 16), so initdb was skipped and the existing cluster was started with the brief's pg_ctl options. Stopped at the end.
- Step 6 UX gate: Python baseline not run (no App/.venv). Design checklist (design-system §5) not ticked: the screenshots and layout lint have not run, so no tick is honest yet. The template keeps Python's classes; the only markup diff is `_csrf` on Go forms (per the brief).
- Done: steps 1 to 7 (step 6 partly pending). Left: nothing in this brief; 1701b (Stay fee section) is the next brief and the route must not be switched on before it.

## 5. Questions

None.

## 6. Owner steps left

- 1701b (Stay fee section) is the next brief; the route must not be switched on before it.
- After 1701b to 1703 and the UX gate on Go: the path switch is brief 1705.
