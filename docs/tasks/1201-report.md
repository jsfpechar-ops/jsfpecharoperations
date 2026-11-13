# 1201 report: Compose container hardening

Status: review
Branch: exec-1201 (local only, not pushed; no PR opened, per session override)
Commit: 23bfe30f (`1201: steps 1-8 compose container hardening`)

## Files changed

`git diff --stat`: `deploy/lightsail/docker-compose.yml` only (20 insertions, 2 deletions), plus this report.

## Commands

1. `docker compose ... config -q` (profiles walg,monitoring,go): PASS, exit 0, no output.
2. `docker compose ... config | grep -nE ...`: PASS. Last lines:
   ```
   433:  caddy-config:
   435:  caddy-data:
   437:  ubyhost-data:
   439:  ubyhost-pgdata:
   441:  ubyhost-pgsock:
   ```
   Parsed with PyYAML as well: ubyhost, worker, ubyhost-go, caddy have `cap_drop: [ALL]`; caddy alone has `cap_add: [NET_BIND_SERVICE]`; alloy on [web, monitoring]; node-exporter and cadvisor on [monitoring]; `monitoring` is `internal: true`.
3. `App/.venv/bin/python -m pytest tests/test_wp32_container_sizing.py tests/test_pg_cutover_script.py tests/test_pg_backup_scripts.py -q --tb=short -x`: PASS, `97 passed in 2.43s`.
4. `python3 scripts/context_lint.py`: PASS, last lines: `next free: task 1204 | migration 0046` / `context lint: OK`. Its WARN lines concern open briefs and were already there before this change.

## Section 7 acceptance

- [x] `config -q` exits 0 with no output
- [x] ubyhost, worker, ubyhost-go, caddy: `cap_drop: [ALL]` and `no-new-privileges:true`; caddy alone has `cap_add`
- [x] node-exporter and cadvisor only on `monitoring`; alloy on `web` and `monitoring`; `monitoring` internal
- [x] Three pytest files and context_lint pass
- [x] Diff touches only the compose file (plus this report)
- [ ] PR is a draft with rollback and post-deploy text: not done here (session override: no PR; orchestrator opens it)

## Deviations

- Steps 1 to 8 are in one commit (`23bfe30f`), not one commit per step. Message prefix is `1201:` per session override.
- No PR opened and nothing pushed, per session override.

## Questions

- Alloy still listens on 0.0.0.0:12345 on `web`, so the app container can still reach it. Decision needed: bind to 127.0.0.1 (then docs/OBSERVABILITY.md line 70-71 curl-by-container-IP check must change).
- Caddy with `cap_drop: ALL` needs `origin-key.pem` readable (see owner step 1).

## Owner steps left

Copied from brief §9 "Owner steps" (1 to 7): check cert and Caddyfile permissions on the server first (the key must be readable by root OR covered by `DAC_READ_SEARCH`, which follow-up 1201b now grants); mark the PR ready and merge with `scripts/merge-pr-on-green.sh`; verify `docker compose --profile monitoring ps`, `/healthz`, caddy logs, and Grafana `up{job=...}` and Loki logs; revert if anything fails.

## Follow-up 1201b

- CI `caddy` job failed after task 1201 added `cap_drop: [ALL]`. Reproduction not done: no Docker daemon in this environment (`docker version` could not reach /var/run/docker.sock); not started, per brief.
- Likely cause (from code reading, not reproduced): caddy runs as root in `caddy:2-alpine`. With all caps dropped, root lacks CAP_DAC_OVERRIDE/CAP_DAC_READ_SEARCH and cannot read `caddy/certs/origin-key.pem` (mode 0600, owned by the runner uid). `Caddyfile.cloudflare` line 20 loads that key in `tls`, which `caddy validate` reads.
- Fix: `deploy/lightsail/docker-compose.yml` caddy service `cap_add: [NET_BIND_SERVICE, DAC_READ_SEARCH]` with a comment. `cap_drop: [ALL]` and `no-new-privileges` unchanged. DAC_READ_SEARCH is read-only bypass.
- Not added: DAC_OVERRIDE, CHOWN, SETUID, SETGID. No evidence they are needed: validation reads the key; the /data and /config ownership was not checked.
- Verify: `COMPOSE_PROFILES=walg,monitoring,go docker compose -f deploy/lightsail/docker-compose.yml config -q` with `.env` touched and `UBYHOST_DOMAIN`/`ACME_EMAIL` set: exit 0. Caddy validate loop for both Caddyfiles and both app domains: not run (no Docker). `App/tests/test_wp32_container_sizing.py` (run with the shared venv from `App/`): 16 passed.
- Owner: the CI caddy job still needs a green run to confirm the fix. Not verified.
