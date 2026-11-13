# 1302 report

Status: review

## Files changed (`git diff --stat d25f8b6..HEAD`)

Only §3 paths, this brief, and the bundle (unchanged; removed later by brief 1410). 17 files, +3024 / -1.

- Code: `go/internal/web/properties/lists.go`, `lists_test.go`, `templates/lists.tmpl`, `i18n_keys.txt`, `i18n.json`, `testdata/lists_cases.json`, `testdata/lists_golden.json`
- Wiring: `go/cmd/ubyhost-web/register_web_properties.go` (one line)
- Python: `App/tests/test_go_properties_lists.py`
- Docs: `docs/tasks/1302-go-property-lists.md` (Status line), this report

## Commands (last lines)

- Step 2: 7 files `OK` (sha256 sums match).
- Step 3: `wrote .../i18n.json`; sum `36ee3c58...6dd` matches.
- Step 4: `2 passed`; golden sum `7b1ea759...bbb20` matches.
- §6 Go: gofmt empty, vet clean. `TestListsMatchPython`, `TestListsRegisterDoesNotTouchThePool`, `TestPagesMatchPython` PASS. `ok` for properties, hostweb, hostweb/layout, cmd/ubyhost-web. No SKIP or FAIL. `BUILD OK`.
- §6 Python: `6 passed`. `go_host_i18n.py --check` exit 0, no `stale:`.
- §6 lint: `context lint: OK` (warning only: App/ commits after last status.md update; orchestrator's job).
- `UBYHOST_GO_PATHS` grep in go/internal/web and register file: only a comment, no route enabled.

## §7 acceptance

All ticked. Postgres at 127.0.0.1:55430 was up; the replay was not skipped.

## Deviations

None.

## Questions

None.

## Not ported (501)

The three 501 branches of §2 are not ported: `/entities?edit=N`, `/entities` with an open alert, and `/apartments` with a live property.

## Owner steps left

1. Wait for the draft PR CI (the `go` job runs the Postgres replay) to go green.
2. Nothing to deploy or configure; routes stay off until a later brief adds them to `UBYHOST_GO_PATHS`.
