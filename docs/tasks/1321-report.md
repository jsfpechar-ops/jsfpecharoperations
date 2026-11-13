# 1321 report

Status: review

## Diff

`git diff --stat HEAD~1..HEAD` (step 1): 6 files, 1545 insertions, 3 deletions. Files: the six §3 paths only (housebook.go, guest_json.go, routes.go, exports_golden.py, test_go_exports.py, exports_golden.json). Step 3 adds this report only.

## Commands (last 5 lines)

- Step 0 checks: branch `task/1320-go-exports`, `1320 step 5` count 1, both new files absent, exports_test.go hash `80fa3aff095f`. All as expected.
- Step 1 sha256: all six hashes match §2 (housebook.go a6d23e63..., guest_json.go f5952102..., routes.go 3630c833..., exports_golden.py ca93c212..., test_go_exports.py 54d31103..., exports_golden.json 49035cb1...).
- Golden `--check` (from App/): no output, no `stale:` line. `git status --short go` empty.
- Go (`gofmt`, `go vet`, `go test`): `--- PASS: TestGoldenParity`, `--- PASS: TestRoutesNeedNoPool`, `--- PASS: TestHelpers`, `ok` for cmd/ubyhost-web and internal/web/exports. No FAIL, no SKIP.
- Python (`tests/test_go_exports.py tests/test_go_host_i18n.py`): `5 passed in 3.61s`, 0 skipped.
- `python3 scripts/context_lint.py`: `context lint: OK`, next free task 1322 (warnings pre-existing).

## Section 7

- [x] Six sha256 values match §2.
- [x] Golden clean; TestGoldenParity PASS on PostgreSQL 16 (127.0.0.1:55432); pytest green.
- [x] Only §3 paths changed.
- [x] Commit "1321 step 1" made; step 3 commit made; nothing pushed.

## Deviations

- Brief §9 asks to set `Status: review` in the brief file. Not done: §3 says no other file may change. The status is recorded in this report instead.
- Executor doc asks to open one PR. Not done: the task said do not push.
- The brief writer's note says "pytest 3 passed"; the 1320 step 5 command ran 5 tests across two files, all passed.

## Questions

- Should the brief's status line be set to `review` by the orchestrator, or should this brief be allowed to touch its own status line?

## Owner steps left

None. Nothing is switched on.
