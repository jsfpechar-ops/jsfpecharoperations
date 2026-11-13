# 1414: Split `test-postgres-full` into four parallel shards and gate deploys on it

Status: todo
Depends on: 1413 (ci.yml order: 1413, 1414, 1415) | Base commit: 531e8359 | Branch: task/1414-postgres-shards
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Turn the one serial 31-minute job `test-postgres-full` into four parallel shards, each with its own Postgres service, plus an aggregate job that keeps the name `test-postgres-full`. Then add `test-postgres-full` to the deploy gate, because production runs on Postgres (docs/context/status.md) and today the Postgres full suite does not gate a deploy.

## 2. Context

Owner decision (2026-11-13): no GitHub branch protection or required checks; the gate is `scripts/merge-pr-on-green.sh` (reads every check of the PR) plus the deploy gate. Hard rule 4: no new dependency, no new third-party Action; copy the `uses:` pins already in `ci.yml`.

Current job (grep `^  test-postgres-full:` in `.github/workflows/ci.yml`, about lines 225 to 275, read it in ranges of 150 lines or fewer): `runs-on: ubuntu-latest`, `timeout-minutes: 50` with a comment about 28 to 35 minutes, `defaults.run.working-directory: App`, a `postgres:17-alpine` service (env `POSTGRES_PASSWORD: ubyhost`, `POSTGRES_DB: ubyhost_test`, port 5432, health options), checkout, setup-python 3.12 with pip cache, install step, then:
```
python -m pytest tests -m "not sqlite_only" --ignore=tests/test_db_postgres.py -q -o faulthandler_timeout=120 --junitxml=pg-full.xml
```
and an `always()` upload of `App/pg-full.xml` as artifact `pg-full-junit`.

The browser shards (grep `Pick this shard's files`, about line 428) deal files round-robin: `... | sort -u | awk -v n=4 -v s=${{ matrix.shard }} '(NR - 1) % n == s - 1'`. Use the same method here. `App/pytest.ini` has no `testpaths` or `python_files`, so pytest's default (`test_*.py`, `*_test.py`) applies; there are 769 `.py` files in `App/tests` (helpers included).

Brief 1413 adds a job `changes` (output `code`) and `needs: changes` plus `if: needs.changes.outputs.code == 'true'` on heavy jobs. Check which is true on your branch at the start: `grep -n "^  changes:" .github/workflows/ci.yml`. If it exists, the shards get the same `needs` and `if`, and the aggregate accepts `skipped` only when `needs.changes.outputs.code == 'false'`. If it does not exist, omit all of that and the aggregate accepts only `success`. Say which case applied in the report.

## 3. Files

| Path | Action | What |
|---|---|---|
| `.github/workflows/ci.yml` | edit | job `test-postgres-full` replaced by `postgres-full-shard` (matrix) and a new aggregate `test-postgres-full` |
| `.github/workflows/deploy-lightsail.yml` | edit | add `test-postgres-full` to the `need` list (OWNER-APPROVED GATE CHANGE) |
| `docs/tasks/1414-report.md` | create | the report |

No other file may change.

## 4. Steps

1. Baseline: `grep -n "^  test-postgres-full:\|^  go:" .github/workflows/ci.yml | head; grep -n "^  changes:" .github/workflows/ci.yml | head -2`. Note the line range of the old job (ends just before `  go:`).
2. Compute the reference file set before editing, from `App/`: `cd App && ls tests/test_*.py tests/*_test.py 2>/dev/null | grep -v '^tests/test_db_postgres.py$' | sort -u > /tmp/pg_all.txt; wc -l < /tmp/pg_all.txt`. Expected: a few hundred lines. If `python -m pytest tests --collect-only -q -m "not sqlite_only" --ignore=tests/test_db_postgres.py 2>&1 | grep '::' | cut -d: -f1 | sort -u | wc -l` is cheap to run (skip it if the venv is missing), compare its count with `/tmp/pg_all.txt`: files that collect zero tests may be absent from the collect list; that is fine, a file missing from `/tmp/pg_all.txt` but present in the collect list is not (then add its pattern to the `ls` and note it).
3. Rewrite the job. Rename the job key to `postgres-full-shard`, add `name: postgres full shard ${{ matrix.shard }}`, `timeout-minutes: 25`, replace the comment above the timeout by `# Each shard is about a quarter of the old 31 minutes.`, and add:
   ```yaml
       strategy:
         fail-fast: false
         matrix:
           shard: [1, 2, 3, 4]
   ```
   (plus `needs`/`if` from 1413 if that landed). Keep services, checkout, setup-python and the install step unchanged. Replace the run step by:
   ```yaml
         - name: Run this shard on PostgreSQL
           env:
             UBYHOST_DATABASE_URL: postgresql://postgres:ubyhost@localhost:5432/ubyhost_test
           run: |
             files="$(ls tests/test_*.py tests/*_test.py 2>/dev/null | grep -v '^tests/test_db_postgres.py$' | sort -u \
               | awk -v n=4 -v s=${{ matrix.shard }} '(NR - 1) % n == s - 1' | tr '\n' ' ')"
             echo "Shard ${{ matrix.shard }}: ${files}"
             python -m pytest ${files} -m "not sqlite_only" -q -o faulthandler_timeout=120 --junitxml=pg-full-${{ matrix.shard }}.xml
   ```
   Replace the upload step by one with `name: pg-full-junit-${{ matrix.shard }}` and `path: App/pg-full-${{ matrix.shard }}.xml` (same pinned `actions/upload-artifact`, same `if: always()`, same `if-no-files-found: warn`).
4. Add the aggregate job after the shard job, exactly named `test-postgres-full` (this is the check name the deploy gate and `gh pr checks` will see):
   ```yaml
     test-postgres-full:
       # Aggregate. The deploy gate and the PR checks look for this name.
       if: always()
       needs: postgres-full-shard
       runs-on: ubuntu-latest
       timeout-minutes: 5
       steps:
         - name: All four Postgres shards passed
           env:
             SHARDS: ${{ needs.postgres-full-shard.result }}
           run: test "${SHARDS}" = "success"
   ```
   With 1413 landed: `needs: [changes, postgres-full-shard]`, add `CODE: ${{ needs.changes.outputs.code }}`, and the run block `if [ "${SHARDS}" = "success" ]; then exit 0; fi; if [ "${SHARDS}" = "skipped" ] && [ "${CODE}" = "false" ]; then exit 0; fi; echo "shards: ${SHARDS} (code=${CODE})" >&2; exit 1`.
5. Disjoint and complete check (the exact shell check; put the output in the report). From `App/`:
   ```bash
   for s in 1 2 3 4; do awk -v n=4 -v s=$s '(NR - 1) % n == s - 1' /tmp/pg_all.txt > /tmp/pg_s$s.txt; done
   cat /tmp/pg_s1.txt /tmp/pg_s2.txt /tmp/pg_s3.txt /tmp/pg_s4.txt | sort > /tmp/pg_union.txt
   wc -l /tmp/pg_all.txt /tmp/pg_union.txt | head -3; diff /tmp/pg_all.txt /tmp/pg_union.txt && echo SAME; sort /tmp/pg_union.txt | uniq -d | wc -l
   ```
   Expected: equal counts, `SAME`, then `0` duplicates.
6. Shared-state check. Grep for signs that a file relies on running with others, each ending `| head -20`, from `App/`: `grep -n "scope=\"session\"\|scope='session'" tests/conftest.py`; `grep -ln "pytest.mark.order\|pytest.mark.dependency" tests/*.py`; `grep -ln "ubyhost_test" tests/*.py`. Report what you find in one line each. Do NOT run the suite. If a file looks order-dependent, name it in the report; do not skip, delete or edit tests. The first CI run is the real check: a file that fails only when sharded goes to the reviewer.
7. Deploy gate, `.github/workflows/deploy-lightsail.yml` (about line 100): in the `need=[...]` list add `"test-postgres-full"` (so it reads `need=["test","smoke","browser","shellcheck","docker","secrets","caddy","test-postgres-full"]`). If 1413 has landed the line is already a skip-aware program: add the name to its `need` list only. If the line differs from this shape, STOP. This step is an owner-approved gate change; say so in the PR text.
8. Parse check: `python3 -c "import yaml; [yaml.safe_load(open(f)) for f in ('.github/workflows/ci.yml','.github/workflows/deploy-lightsail.yml')]; print('yaml ok')" 2>&1 | tail -5` (if PyYAML is missing, say how it was checked). Then `grep -n "test-postgres-full\|postgres-full-shard" .github/workflows/*.yml docs/*.md scripts/* 2>/dev/null | head -20` and report any other file that names the old job (do not edit them, except that you list them).
9. Report, commit per step as `1414 step k`, push the task branch (never `main`).

## 5. Do not touch

`App/`, other jobs, `deploy-production.yml`, any test. Do not change `-m "not sqlite_only"` or the `--ignore`. Hard rules 3, 4, 8.

## 6. Commands

Steps 1, 2, 5, 6, 8. Context lint: `python3 scripts/context_lint.py 2>&1 | tail -30`. No pytest run.

## 7. Acceptance

- [ ] Step 5 prints equal counts, `SAME`, and `0` duplicates.
- [ ] YAML parses (or the check is stated).
- [ ] Four shard jobs, each with its own `postgres` service, a per-shard junit artifact, `timeout-minutes: 25`; an aggregate named exactly `test-postgres-full` with `if: always()`.
- [ ] Deploy gate lists `test-postgres-full`.
- [ ] Report says whether 1413 had landed and which aggregate rule was written.
- [ ] Step 6 findings listed (even "none found").

## 8. Stop and ask

Stop and write the report if: an anchor is not found verbatim; the deploy gate line has a different shape; step 5 does not print `SAME`; a new dependency or Action seems needed; you reach 25 tool calls or about 50k tokens.

## 9. Report

`docs/tasks/1414-report.md` (600 tokens at most), `Status: review`: files changed, step 5 output, step 6 findings, which 1413 case applied, deviations, questions, owner steps.

## Risk list (for the reviewer)

The aggregate job `test-postgres-full` (a skipped or cancelled shard must fail it) and the gate edit in `deploy-lightsail.yml`: from now on a red Postgres suite blocks deploys. After merge, watch the first CI run for a file that fails only when sharded; expected wall time is about 8 minutes per shard plus setup.

## Owner steps

1. Open the PR and wait for the green check.
2. Merge with `scripts/merge-pr-on-green.sh <PR number>`. This also changes the deploy gate: you approved that on 2026-11-13.
3. After the merge check that `gh pr checks` on the next PR shows `test-postgres-full` as one line.
