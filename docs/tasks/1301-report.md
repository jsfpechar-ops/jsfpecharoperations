# 1301 report

Status: review

## Files changed (`git diff --stat c540113..HEAD`)

- App/tests/test_go_properties_pages.py (create)
- go/cmd/ubyhost-web/register_web_properties.go (replace, one added line)
- go/internal/web/properties/i18n.json (regenerated, step 3)
- go/internal/web/properties/i18n_keys.txt (replace)
- go/internal/web/properties/pages.go (create)
- go/internal/web/properties/pages_test.go (create)
- go/internal/web/properties/templates/guide.tmpl (create)
- go/internal/web/properties/testdata/pages_cases.json (create)
- go/internal/web/properties/testdata/pages_golden.json (generated, step 4)
- docs/tasks/1301-go-property-pages.md (Status line only)
- docs/tasks/1301-report.md (this file)
- the bundle (already tracked; removed later by brief 1410)

## Commands (last lines)

- Step 2 sha256 check: 7 files `OK`.
- Step 3 `go_host_i18n.py`: `wrote .../go/internal/web/properties/i18n.json`; sum `e72cb114...fbac06` matches.
- Step 4 golden: `2 passed in 1.44s`; sum `14a8bfa1...d2c63d169` matches.
- `gofmt -l .`: empty. `go vet ./...`: clean.
- `go test -count=1 -v` (properties, hostweb, hostweb/layout, cmd/ubyhost-web): `--- PASS: TestExtractItemsScope`, `--- PASS: TestPagesMatchPython`, `--- PASS: TestPagesRegisterDoesNotTouchThePool`; `ok` for all four packages; no SKIP or FAIL.
- `BUILD OK`.
- Python `test_go_properties_pages.py` + `test_go_properties_actions.py`: `4 passed in 2.40s`.
- `go_host_i18n.py --check`: no `stale:` line.
- `context_lint.py`: `context lint: OK` (warning only: 5 App commits after last status.md update; status is the orchestrator's job).
- `grep UBYHOST_GO_PATHS` in go/internal/web and register file: only a comment line; no route enabled.

## Section 7 acceptance

All boxes ticked. Postgres ran on 127.0.0.1:55430 with UBYHOST_TEST_DATABASE_URL set, so TestPagesMatchPython ran and was not skipped.

## Deviations

None. Test env var was set inline for the pytest golden step (same value as §6 export).

## Questions

None.

## Owner steps left

1. Review the draft PR; CI `go` job runs the Postgres replay.
2. Nothing to deploy: routes stay off until a later brief adds them to UBYHOST_GO_PATHS after 1381.

Left out on purpose (§2): `GET /menu` (cleaning and filing data) and `GET /housebook` (guest rows, Tier A). Each needs its own brief.
