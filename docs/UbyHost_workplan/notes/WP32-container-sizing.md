# WP32: Size the containers for the 8 GB server

Series step 0005, right after STEP0. Commit `WP32: Size the containers for the 8 GB server`.

## Summary
Production moved to Lightsail 8 GB RAM, 2 vCPUs, 160 GB SSD. The web worker count and every container memory cap are now set from `.env`, with defaults sized for that server. Local snapshot retention of 7 days is documented for once Litestream replicates; the code default stays 30.

- Web workers: the Dockerfile CMD runs uvicorn with `--workers "${UBYHOST_WEB_WORKERS:-2}"` (through `sh -c "exec ..."`: exec replaces the shell, so uvicorn still gets the stop signal directly). The image sets `UBYHOST_WEB_WORKERS=2`; `.env.example` sets 4 for the 8 GB / 2 vCPU server. `docker-entrypoint.sh` and `preflight.sh` refuse anything but a whole number from 1 to 16.
- `mem_limit`: web `${UBYHOST_WEB_MEM:-2g}`, worker `${UBYHOST_WORKER_MEM:-1g}`, litestream `${UBYHOST_LITESTREAM_MEM:-256m}`, caddy `${UBYHOST_CADDY_MEM:-256m}`. Compose reads these from `deploy/lightsail/.env` (the project directory), the same file the services already use.
- SQLite: no PRAGMA changes (WP14 later keeps one connection per thread).
- Docs: sizing table in `docs/LIGHTSAIL.md` (Sizing section), staging values in the README, new variables in `docs/ENVIRONMENT.md`, and the note that `mem_limit` does not change `docker compose build` speed.

## Files changed
- `Dockerfile`: `UBYHOST_WEB_WORKERS=2` env, CMD reads it.
- `docker-entrypoint.sh`: worker-count check (1 to 16).
- `deploy/lightsail/docker-compose.yml`: four `mem_limit` values from `.env` with defaults; Caddy gets a limit for the first time; comments.
- `deploy/lightsail/.env.example`: server sizing block (`UBYHOST_WEB_WORKERS=4`, commented mem variables, staging values); retention comment.
- `deploy/lightsail/scripts/preflight.sh`: worker-count check; sizing comment.
- `deploy/lightsail/README.md`: retention 7 after Litestream; staging `.env` with lower values.
- `docs/LIGHTSAIL.md`: Sizing (WP32) section and table; plan table row.
- `docs/ENVIRONMENT.md`: `UBYHOST_WEB_WORKERS`, the four mem variables, retention note.
- `App/tests/test_wp32_container_sizing.py`: new.

## Tests added
`tests/test_wp32_container_sizing.py`, 16 tests: the compose file parses as YAML and has the services; each `mem_limit` is the expected `${VAR:-default}`; the defaults expand to 2g/1g/256m/256m and staging values replace them; the Dockerfile has no hard-coded `--workers 2` and its single CMD uses the variable; the entrypoint accepts unset, 1, 2, 4, 16 and refuses 0, 17, two, 4x, -1, 04; `.env.example` and `docs/LIGHTSAIL.md` carry the documented values.

## Test commands and results (exact counts)
From `App/`, with `LD_LIBRARY_PATH=/tmp/libs/root/usr/lib/aarch64-linux-gnu /tmp/pr230/App/.venv/bin/python -m pytest -q -p no:cacheprovider`:
- `tests/test_wp32_container_sizing.py tests/test_backup_offsite.py tests/test_env_guard.py` on the WP32 commit: 35 passed.
- Full suite on the final 33-patch tree: see `series/INTEGRATION_NOTES.md` (2775 passed, 2 skipped). Ruff: all checks passed.

## Deviations from the spec and why
- Caddy had no `mem_limit` before (the spec said 128m); it now gets `${UBYHOST_CADDY_MEM:-256m}`. The staging mock UbyPort keeps its fixed 128m.
- `UBYHOST_BACKUP_RETENTION_DAYS=30` stays in `.env.example` with a comment to set 7 once Litestream replicates, so the owner switches it after confirming the replica works.
- The 1 GB preflight floor (`UBYHOST_ALLOW_SMALL_HOST`) is unchanged; the defaults are caps, not reservations, so a 2 GB staging server still starts, and the README shows lower values for it.

## What Cursor must verify or adapt when applying on the real main
- Run `docker compose config | grep -E "mem_limit|mem"` in `deploy/lightsail` once; Compose v2 accepts `2g`/`256m` strings from substitution, but it was not run here.
- After the first deploy: `docker stats --no-stream` shows the new limits, and the web container's log shows four `Started server process` lines with `UBYHOST_WEB_WORKERS=4`.

## Manual steps for the owner
- In the production `.env`: keep or set `UBYHOST_WEB_WORKERS=4`. Once Litestream replicates (heartbeat green), set `UBYHOST_BACKUP_RETENTION_DAYS=7`.
- In the staging `.env` on a 2 GB server: `UBYHOST_WEB_WORKERS=2`, `UBYHOST_WEB_MEM=896m`, `UBYHOST_WORKER_MEM=448m`, `UBYHOST_LITESTREAM_MEM=128m`, `UBYHOST_CADDY_MEM=128m`.
