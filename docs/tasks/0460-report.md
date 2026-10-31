# 0460 report: Run the PostgreSQL test module in CI

Status: review

## Files changed

- `.github/workflows/ci.yml`: new job `test-postgres` inserted between `test` and `smoke` (53 added lines, 0 removed).
- `docs/tasks/0460-postgres-tests-in-ci.md`: copied from commit d346596 (its only copy is on branch `claude/project-thread-tmwhek`); Status set to `review`.
- `docs/tasks/0460-report.md`: this file.

## Job text

```yaml
  test-postgres:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    defaults:
      run:
        working-directory: App
    services:
      postgres:
        image: postgres:17-alpine
        env:
          POSTGRES_PASSWORD: ubyhost
          POSTGRES_DB: ubyhost_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U postgres"
          --health-interval 5s
          --health-retries 10
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          persist-credentials: false
      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: |
            App/requirements.txt
            App/requirements.lock
            App/requirements-dev.txt
      - name: Install dependencies
        run: pip install --require-hashes -r requirements.lock && pip install -r requirements-dev.txt
      - name: Run PostgreSQL tests
        if: hashFiles('App/tests/test_db_postgres.py') != ''
        env:
          UBYHOST_TEST_DATABASE_URL: postgresql://postgres:ubyhost@localhost:5432/ubyhost_test
        run: |
          set -o pipefail
          python -m pytest tests/test_db_postgres.py -q -rs --tb=short 2>&1 | tee "$RUNNER_TEMP/pg-tests.log" | tail -30
      - name: Fail if PostgreSQL tests were skipped
        if: hashFiles('App/tests/test_db_postgres.py') != ''
        run: |
          if grep -q skipped "$RUNNER_TEMP/pg-tests.log"; then echo "PostgreSQL tests skipped; they must run with 0 skipped"; exit 1; fi
      - name: No PostgreSQL module yet
        if: hashFiles('App/tests/test_db_postgres.py') == ''
        run: echo "no PostgreSQL module yet"
```

## Commands

- `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`: parsed OK. Jobs: test, test-postgres, smoke, browser-shard, browser, shellcheck, docker, context, secrets. New job steps: checkout, setup-python, Install dependencies, Run PostgreSQL tests, Fail if PostgreSQL tests were skipped, No PostgreSQL module yet.
- `git diff --numstat`: `53 0 .github/workflows/ci.yml`. The `test` job is unchanged.
- `zizmor`: not installed, not run.

## Section 7 acceptance

- [x] YAML parses.
- [x] On main the new job is a visible no-op: the test file is absent, so only the "no PostgreSQL module yet" step runs.
- [x] The `test` job is byte-identical (the diff only adds lines).

## Deviations

- The brief was not on this branch. It exists only on `claude/project-thread-tmwhek` (commit d346596), so it was copied in to set its Status.
- §4 step 4: `browser` needs only `browser-shard`, and `test` is not in its list, so `test-postgres` was not added there.
- The worktree had no `App/.venv`; the YAML check used system `python3` with PyYAML.

## Questions

- None.

## Owner steps left

- None for this brief. Open the PR when the owner asks. The job stays a no-op until PR #592 adds `App/tests/test_db_postgres.py`.
