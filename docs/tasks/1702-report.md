# 1702 report (executor: Haiku 5.5)

## 1. Files changed (commit b82d57b, `1702 step 1`)

go/cmd/ubyhost-web/register_web_properties_apartment_door_codes.go (+25), go/cmd/ubyhost-web/register_web_properties_apartment_door_codes_test.go (+25), go/internal/web/properties/apartment_door_codes.go (+130), go/internal/web/properties/apartment_door_codes_test.go (+175), go/internal/web/properties/apartmentdoorcodes/i18n.json (+20), go/internal/web/properties/apartmentdoorcodes/i18n_keys.txt (+6). 6 files, 381 insertions. This report and the brief status line are committed as `1702 step 7`.

## 2. Commands (last lines)

- Step 0: all anchors 1, six sidecars, route not registered (0). No output problems.
- Step 1: sha256sum -c: all six `: OK`.
- Step 2 (gofmt, go build, go vet): no output, build rc=0, vet rc=0.
- Step 3: "Python checks: CI only (no App/.venv)".
- Step 4: PostgreSQL 16 started on port 55472: `server started`; stopped at end: `server stopped`.
- Step 5: `ok .../go/internal/web/properties` and `ok .../go/cmd/ubyhost-web`. Named tests: `--- PASS` for TestApartmentDoorCodes, TestApartmentDoorCodesAccess, TestApartmentDetailDoor, TestApartmentDoorCodesRouteRegistered, TestApartmentDetailRouteRegistered. Properties SKIP count: 0.
- Context lint: `next free: task 1840 ...`, `context lint: OK`.

## 3. Section 7 ticked

- [x] Step 0 anchors and six sidecars; sha256 OK.
- [x] Format, build and vet printed nothing.
- [x] Step 3: CI only (no App/.venv).
- [x] Step 5: two ok lines, five named tests PASS, SKIP count 0.
- [x] Refusal and write tests passed (TestApartmentDoorCodes, TestApartmentDoorCodesAccess).
- [x] Only the six §3 paths in the step commit; no UBYPORT_GO_PATHS, Caddy, compose, env or Python change; nothing pushed.

## 4. Deviations

None. Branch is claude/beautiful-archimedes-lxhrit (not task/1702); step commits on that branch as instructed.

## 5. Questions

None.

## 6. Owner steps left

1702b (POST /apartments/{id}) and 1703 are next. The route must not be switched on before them. UX: no page change.
