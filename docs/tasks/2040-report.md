# 2040 report (executor run, third attempt)

Status: blocked

## Done

- Step 0: `scripts/e2e/parity_env.sh` install block split into two pip calls (`requirements.lock`, then `requirements-dev.txt`). Commit `2040 step 0`.
- Step 1 (run command only, file already existed): Postgres 16 accepting connections on 127.0.0.1:5433; `App/.venv/bin/python` present; import check prints `ok`. `git status` clean apart from the brief's files.

## Stopped at step 2 (smoke test)

Command: `source scripts/e2e/parity_env.sh; cd App && PARITY_ONLY=admin-home PARITY_WIDTHS=390 .venv/bin/python ../scripts/e2e/page_parity_visual.py`
Exit 1. Last lines:

```
  File "/home/user/jsfpecharoperations/App/app/db.py", line 1904, in apply_postgresql_schema
    with startup_lock():
  File "/home/user/jsfpecharoperations/App/app/db.py", line 1556, in startup_lock
    conn = _open()
  File "/home/user/jsfpecharoperations/App/app/db.py", line 672, in _open
    conn = db_postgres.connect(config.DATABASE_URL)
  File "/home/user/jsfpecharoperations/App/app/db_postgres.py", line 803, in connect
    raise ConnectionError("Unable to connect to the configured PostgreSQL database") from None
ConnectionError: Unable to connect to the configured PostgreSQL database
```

Likely cause (not verified, brief says do not explore): the app reads `config.DATABASE_URL`, while `parity_env.sh` only exports `UBYHOST_E2E_PG`. The brief does not set `DATABASE_URL`.

## Not done

- Step 3 (`scripts/e2e/parity_cases.py`), step 4 (probe edits), step 5 (groups A, B, C, D), step 6 (screenshot review), step 7 (this report's full table), step 8 (context_lint and pytest).
- Verdict counts: identical 0, invisible 0, visible 0, error 0. Groups run: none. Groups missing: A, B, C, D, L.
- No screenshots taken. `/var/tmp/parity-visual/` not populated by this run.

## Owner or next-chat steps

- Decide the DATABASE_URL value for the parity env (or a brief change to `parity_env.sh`), then re-run step 2 before step 3.
