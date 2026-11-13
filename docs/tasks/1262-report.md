# 1262 report: Go schema fix 1

Status: review

## Files changed (`git diff --stat 36ab7a1..HEAD`)

13 files, 1052 insertions, 39 deletions: the 10 patched files, `go/internal/schema/expected_schema.json` (step 2 regenerate), and the brief plus `fix.patch` under `docs/tasks/`.

## Commands (last 5 lines)

- `git apply --check ... && git apply ...`: patch applied, 10 files ` M`.
- `scripts/pg_schema_golden.py`: `wrote: go/internal/schema/expected_schema.json`
- sha256sum (11 files): 11 x `OK`.
- `go test ./internal/schema ./cmd/ubyhost-web -count=1` (after gofmt and go vet clean): `ok` for both packages.
- `pytest tests/test_go_schema_golden.py`: `5 passed in 1.27s`
- `pg_schema_golden.py --check`: `check exit 0`
- `pytest tests/test_go_schema_migrate.py` without a PostgreSQL URL: `4 skipped in 0.14s`
- `pytest tests/test_go_schema_migrate.py` with `UBYHOST_TEST_DATABASE_URL` on a disposable PostgreSQL 16 (port 5433): `4 passed in 8.40s`
- ruff (E9,F63,F7,F82,F401,F841): `All checks passed!`
- `bash -n deploy/lightsail/scripts/deploy.sh`: `syntax ok`
- `python3 scripts/context_lint.py`: `context lint: OK`

## Section 7 acceptance

- [x] Step 1: patch applied cleanly. Step 3: 11 x OK.
- [x] Section 6 all as expected.
- [x] `git diff --stat 36ab7a1..HEAD` lists only section 3 files (plus the brief and patch).
- [ ] CI `test-postgres-full` result: not yet, needs push (not done, per instructions).

## Deviations

- Local PostgreSQL 16 was started as the `postgres` user with data dir `/var/tmp/pg1262/data` on port 5433, and stopped afterwards. Nothing outside `/var/tmp` was changed.
- Commits: `e8166ae 1262 step 1-3`. This report is committed as `1262 step 5: report`.
- No PR opened and nothing pushed (instructions said not to push).

## Questions

None.

## Owner steps left

None new. Push the branch and open the draft PR when ready, then check CI `test-postgres-full` for the 4 migrate tests passing (not skipped).
