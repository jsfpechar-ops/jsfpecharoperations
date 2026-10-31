# 0463 report (executor Haiku 5.5)

## Files changed
- New: `deploy/lightsail/scripts/pg-cutover.sh` (rehearse, cutover, rollback; `env-switch` and `env-restore` functions), `App/tests/test_pg_cutover_script.py`.
- Edit: `deploy/lightsail/docker-compose.yml` (postgres service pinned `postgres:16-alpine@sha256:0cefaabd...`, no ports, `mem_limit: 1g`; socket volume into `ubyhost` and `worker`; two named volumes), `deploy/lightsail/.env.example`, `deploy/lightsail/scripts/preflight.sh`, `deploy/lightsail/README.md`, `docs/LIGHTSAIL.md`, `docs/ENVIRONMENT.md`, brief status.

## Commands (last lines)
- `bash -n deploy/lightsail/scripts/pg-cutover.sh`: exit 0.
- `App/.venv/bin/python -m pytest tests/test_pg_cutover_script.py -q --tb=short -x`: `6 passed in 0.66s`.
- `shellcheck`: not installed here.
- `python3 scripts/context_lint.py`: `context lint: OK`, exit 0.
- Docker is not available here, so `rehearse` and `cutover` were not run.

## Section 7 acceptance
- Syntax and test: met.
- No command writes `/data/ubyhost.db`: met by reading the code; the script only takes a `.backup` copy.
- `cutover` exits before stopping anything without a fresh rehearsal: met by code order; not run.
- Every failure path ends with the app on SQLite: `fail_cutover`; not run.
- `postgres` publishes no port and has a memory limit: met (tested).
- Password never logged: met (test greps the script).

## Deviations
- Preflight uses `psql` in the postgres container, not a one-off `ubyhost` container.
- Rehearsal copies SQLite in a one-off container, not inside the running `ubyhost`. Same `.backup`.
- `deploy/lightsail/README.md` has no table; one pointer line was added.
- Verify reports go to `<name>.verify.json`; `cutover` checks the newest `rehearsal-*.verify.json` for `status: ok` under 24 h.

## Unverified (needs a rehearsal on the server)
- `/app/scripts/sqlite_to_postgres.py` exists in the image and reads `UBYHOST_DATABASE_URL` from the environment.
- It accepts the run when `.env` still sets `UBYHOST_DB`.
- Its reports carry a `status` key.
- Socket volume access for uid 10001 (brief section 8). Not checked. Postgres defaults to socket mode 0777.
- I did not open `App/scripts/sqlite_to_postgres.py`, so the brief's "transfer script needs a change" stop check was not done.

## Owner steps left
- Not read: `docs/plans/postgresql/owner-steps-cutover.md`.
- Owner: set `UBYHOST_PG_PASSWORD` in `deploy/lightsail/.env`, run `./scripts/pg-cutover.sh rehearse`, then `./scripts/pg-cutover.sh cutover` after a clean rehearsal. `rollback` is the way back.

## Review fixes
- `fresh_rehearsal` now reads the real verify report keys (`mode`, `target_database`, `tables[*].match`) and no longer looks for `status`.
- The transfer runs the app script with `UBYHOST_DB` unset, so an `.env` that still sets it does not crash the run.
- An `ERR` trap around the downtime window calls `fail_cutover`, so an unexpected error after the stop still restarts the app. `fail_cutover` clears the trap first to avoid recursion.
- The script header says it needs `UBYHOST_PG_PASSWORD`.
- `deploy/lightsail/.gitignore` ignores `.env.sqlite-*`.
- New test: the script contains `unset UBYHOST_DB` and no `"status"`.

## Change: no password
The owner cannot set a password soon, so the `postgres` service has none. It runs with `network_mode: none` and `listen_addresses=` (no TCP listener), and it trusts local socket connections (`POSTGRES_HOST_AUTH_METHOD: trust`). Only containers that mount the `ubyhost-pgsock` volume can reach it, the same trust boundary as the SQLite file. `preflight.sh` and `.env.example` are back at origin/main, `UBYHOST_PG_PASSWORD` is gone from the repo, and the header of `pg-cutover.sh` no longer names it.
