# 1700c report (executor run, Haiku 5.5)

Status: review

## 1. Files changed
- Commit `1700c step 1` (11 files): `App/migrations_pg/00021_ruian_address.sql`; `go/cmd/ubyhost-web/register_ruian_import.go` and `_test.go`; `go/internal/ruian/` (attribution.go, fold.go, import.go, okres.go, okres.csv, row.go, ruian_test.go, testdata/20261031_OB_999991_ADR.csv). 7,142 insertions.
- Commit `1700c step 2` (4 files, the patch): `App/tests/test_db_postgres.py`, `deploy/lightsail/scripts/backup.sh`, `docs/ENVIRONMENT.md`, `go/internal/schema/testdata/goose_statements_golden.json`.
- This report and the brief Status line.

## 2. Commands (last lines)
- Step 0 anchors: all as stated (`00020_guest_contract.sql` is the last migration, 12 sidecars).
- Step 1: 12 of 12 `: OK`.
- Step 2: `git apply --check` and `git apply` clean; diff 4 files (plus brief status), 13 insertions, 3 deletions in the four files.
- Step 3 (gofmt, build, vet, go.mod diff): no output.
- Step 4: PostgreSQL 16 started on 127.0.0.1:55700 (throwaway data dir `/var/tmp/pg1700c/data`, existing cluster restarted). Role `postgres` is superuser.
- Step 5 A: `ok` for ruian, schema, scheduler, cmd/ubyhost-web.
- Step 5 B: nine `--- PASS` (TestFold, TestOkres, TestCandidates, TestParseLineAndStream, TestImport, TestImportLock, TestGooseFilesMatchPython, TestRuianImportSwitches, TestRuianImportTaskRegisteredOnce).
- Step 5 C: SKIP count `3` (the probes in cmd/ubyhost-web); none in internal/ruian.
- Step 6: no `App/.venv`; Python checks CI only.

## 3. Section 7 acceptance
- [x] Step 1 12 of 12 OK; step 2 changed exactly the four files.
- [x] Format, build, vet silent; go.mod and go.sum unchanged.
- [x] Four ok lines, nine PASS, SKIP 3 (probes only).
- [x] The named tests pass (the import behaviours in §7 are covered by TestImport, TestImportLock, TestRuianImportSwitches).
- [x] Step commits list only the §3 paths.
- [x] Dormant by default (TestRuianImportSwitches).

## 4. Deviations
- Commits used explicit paths, not `git add -A`, per the run instruction (other agents' files under docs/tasks/ are untracked).
- Brief commits carry the attribution trailers.
- Step 1 `sha256sum -c` was run once more by mistake without its input; it hung and was stopped (TaskStop). No effect on files.

## 5. Questions
None.

## 6. Owner steps left
See brief section "Owner steps": run `CREATE EXTENSION IF NOT EXISTS pg_trgm` on the server before merging; merge with `scripts/merge-pr-on-green.sh`; optionally set `UBYHOST_RUIAN_IMPORT=1` afterwards; refresh okres.csv yearly.
