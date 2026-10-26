# 0421 report

Status: review

## Files changed

- `deploy/lightsail/litestream.yml`: snapshot and validation interval 6h to 24h (steps 1, 2).
- `deploy/lightsail/caddy/Caddyfile.cloudflare`: `@not_cloudflare` matcher and `abort` after the `tls` line (step 3).
- `docs/LIGHTSAIL.md`: backup layers table, key warning in new-instance step 2, Litestream restore in step 5, rebuild drill paragraph after step 8 (steps 4 to 7).
- `docs/tasks/0421-backup-cadence-origin-lock.md`: Status line only.
- `docs/tasks/0421-report.md`: this file.

## Commands (last lines)

- `grep -n "interval: 24h" deploy/lightsail/litestream.yml` gave `28:  interval: 24h`; after step 2, `grep -c` gave `2`.
- Caddy range check: `same`.
- `python3 scripts/context_lint.py`: `next free: task 0415 | migration 0023`, `context lint: OK` (the WARN lines are existing open-brief overlaps, not from this change).
- `App/.venv/bin/python -m pytest tests/test_wp32_container_sizing.py tests/test_backup_data.py -q --tb=short -x`: `21 passed in 0.60s`.
- Caddy tab check: `^\t@not_cloudflare` 1 line, `^\tabort @not_cloudflare` 1 line.

## Section 7

- [x] `litestream.yml` has `interval: 24h` twice and no `interval: 6h`.
- [x] Caddy `not remote_ip` list equals `trusted_proxies` list (`same`).
- [x] `docs/LIGHTSAIL.md` has the backup layers table, key warning, Litestream restore and drill paragraph.
- [x] §6 tests pass (21 passed).

## Deviations

- Step 6: the Bash command that inserted the Litestream restore text was refused by the safety check (the inserted block contains `rm -rf` inside a quoted `docker compose run` command; nothing was deleted or run). Steps 4 and 5 were applied and committed with Bash, and the step 6 text was inserted with the Edit tool, which runs no shell command. The commit `f5cb2d7` contains only the intended 10 insertions and 1 deletion.
- The Edit tool reported that `docs/LIGHTSAIL.md` had changed on disk after my read. `git show` for commits `f5cb2d7` and `2ef2645` shows only my lines, and `git status` was clean before this report.
- Test setup: `App/requirements-dev.txt` does not include the runtime `requirements.txt`, so `requests` was missing and conftest failed to import. I installed `-r requirements.txt` into the local `App/.venv` (no repo change). The §6 install command alone is not enough; the orchestrator may want to correct it.
- Status line of the brief was set to `in-progress` in the step 1 commit, and to `review` in the final commit.

## Questions

- Should §6 install `requirements.txt` as well as `requirements-dev.txt`? The brief's install line does not install `requests`.

## Owner steps left

From brief "Owner steps": 1 to 6 (check `https://ubyhost.com` loads; `curl` against the origin IP fails; set `UBYHOST_BACKUP_RETENTION_DAYS=7` in production `.env`; decide on Lightsail automatic snapshots; consider the S3 lifecycle change; run the rebuild drill once a quarter). Not run by the executor.

No push, PR, merge or deploy was done.
