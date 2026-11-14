# 1414 report

Status: review

Brief 1413 had landed: `changes` job exists in ci.yml (line 19). Shards carry `needs: changes` and `if: needs.changes.outputs.code == 'true'`; the aggregate accepts `skipped` only when code is `false`.

## Files changed
- `.github/workflows/ci.yml`: old job `test-postgres-full` (about lines 263-315) replaced by matrix job `postgres-full-shard` (shards 1-4, timeout 25, fail-fast false, per-shard junit `App/pg-full-N.xml`, artifact `pg-full-junit-N`) and aggregate `test-postgres-full` (lines ~324-337, `if: always()`).
- `.github/workflows/deploy-lightsail.yml` line 100: `test-postgres-full` added to `need`.

## Checks
- Step 2: 761 files (`/tmp/pg_all.txt`). Collect-only not run.
- Step 5: shard sizes 191/190/190/190; `SAME`; duplicates `0`.
- Step 6: session fixtures in conftest.py at lines 213, 278, 320 (autouse) and 349. No order/dependency marks. `ubyhost_test` only in `tests/test_db_postgres.py` (excluded).
- Step 8: `yaml ok`. Old job name appears in no other file.
- Context lint: OK (pre-existing WARN lines only).

## Aggregate rule
Pass if shards result is `success`, or `skipped` with code `false`. Any other result (failure, cancelled, skipped with code true) fails.

## Deploy gate
need=["test","smoke","browser","shellcheck","docker","secrets","caddy","test-postgres-full"]

## Not verified
- YAML is valid, but Actions semantics are unverified; first CI run is the real check.
- No PR opened (orchestrator rule for this session).
- No pytest run (per brief).
