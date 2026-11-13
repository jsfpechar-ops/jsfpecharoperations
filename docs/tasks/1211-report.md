# 1211 report

Status: review

## Files changed (vs 1210 tip 1dfa281)

```
 App/scripts/retention_golden.py            |  46 ++-
 App/tests/test_go_retention_parity.py      |   6 +-
 go/internal/retention/golden_test.go       |  37 +-
 go/internal/retention/retention.go         |   7 -
 go/internal/retention/steps.go             | 419 +++++++++++++++++++----
 go/internal/retention/testdata/golden.json | 522 +++++++++++++++++++++++++++++
 6 files changed, 943 insertions(+), 94 deletions(-)
```

All six paths are in brief §3. Not touched: `retention_test.go`, `fixture.sql`, `register_job_retention.go`, `deploy/`.

## Commands (last lines)

§6 Go (`go test ./internal/retention/ ./cmd/ubyhost-web/ -count=1 -v`):

```
--- PASS: TestRunMatchesPythonGolden (2.80s)
    --- PASS: TestRunMatchesPythonGolden/global_dry
    --- PASS: TestRunMatchesPythonGolden/owner1_dry
    --- PASS: TestRunMatchesPythonGolden/owner1_apply
    --- PASS: TestRunMatchesPythonGolden/global_apply
--- PASS: TestApplyWithoutDataDirDeletesNoGuest
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/retention
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web
```

Parity pytest (with `UBYHOST_TEST_DATABASE_URL` set): `2 passed in 3.53s`. Ruff: `All checks passed!`. Context lint: `context lint: OK`.

## Acceptance (§7)

- [x] Step 0 sha256 list matched; every later sha256 matched (extractor hashes and golden.json `65de56d3...`).
- [x] Go: all four golden subtests and the data-dir test `--- PASS`, no SKIP.
- [x] Parity pytest `2 passed`; ruff clean; context lint OK.
- [x] Diff lists only §3 paths.
- [x] Commits `1211 step 1` to `1211 step 4`; nothing pushed.

## Deviations

- Helper files written to `/tmp/claude-0/x1211/` per the session instruction. The extractor maps any `/tmp/...` output path into that folder; the hashes are unchanged.
- The first parity pytest run had no database URL and reported 1 skipped. Rerun with the URL gave `2 passed`.
- Diff stat is against 1210 tip `1dfa281`, not `main`, because 1210 is not merged yet.
- Appendix deletion (`docs/tasks/1211-appendix`) is done in the report commit.

## Questions

None.

## Owner steps left

Per brief "Owner steps": (1) decide photo mount for `ubyhost-go` (read-only `/data`), (2) check no workspace due within 7 days, (3) set `UBYHOST_RETENTION_AUTOPURGE=1` and `UBYHOST_GO_RETENTION_APPLY=1`, then deploy, (4) verify next morning, (5) rollback path. Only after 1210's three dry-run nights matched.
