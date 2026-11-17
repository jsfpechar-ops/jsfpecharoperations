# 1830 report: two-copy deploy of ubyhost-go

Status: blocked (steps 1 to 4 done; section 6 checks not run in this session)

## Files changed
- deploy/lightsail/docker-compose.yml: slot A tag `ubyhost-go:slot-a`, new `ubyhost-go-b` via `extends`.
- deploy/lightsail/caddy/Caddyfile.acme, Caddyfile.cloudflare: both Go `reverse_proxy` blocks use two upstreams, `lb_policy first`, active health check on /healthz.
- deploy/lightsail/scripts/go-slot.sh (new, executable): slot helpers.
- deploy/lightsail/scripts/deploy.sh: slot rotation block after `docker compose up -d --remove-orphans`.
- docs/tasks/1830-report.md (this file).

## Commands
- `docker compose --profile go config --format json` (temporary .env copied from .env.example, removed after): exit 0. Compared resolved `ubyhost-go` and `ubyhost-go-b`: identical in every field except `image` (mem_limit 134217728, healthcheck, volumes, environment 85 keys).
- `bash -n` on go-slot.sh and deploy.sh: syntax ok.
- shellcheck: NOT RUN. Binary not installed; apt install did not succeed here.
- Caddy validate (`caddy/scripts/caddy-validate.sh`, both files, AOP modes): NOT RUN. Last lines: `failed to connect to the docker API at unix:///var/run/docker.sock ... no such file or directory`.
- pytest `test_pg_*script*.py`: NOT RUN. `App/.venv` does not exist in this worktree.

## Section 7 acceptance
- [ ] shellcheck, compose config, caddy validate, pytest: only compose config passed.
- [x] `git diff` lists only section 3 paths.
- [x] `lb_policy first` appears twice in each Caddyfile; the `ubyhost:8080` line count is 3 per file and no such line changed (diff touches only the reverse_proxy lines).
- [x] `source ./scripts/go-slot.sh` appears once in deploy.sh.

## Deviations
- Compose needs a `.env` because of `env_file`; a temporary one was used and deleted, not committed.
- The Caddy and pytest checks need Docker, shellcheck and App/.venv, which this session lacks. CI must run them.
- go-slot.sh sets `set -euo pipefail`; sourced from deploy.sh it changes that shell's options. Brief text used as written; review this.
- Compose output was written to /tmp (the brief names /tmp/c.yml).

## Questions
- Brief open questions 1 to 4 stand (migration lint, depends_on bounce, opt-in Python two-copy, compose v2 version).

## Owner steps left
1. Run shellcheck, Caddy validate and the pytest row in CI or on a machine with Docker.
2. Staging per brief section 10 (steps 1 to 4) before marking the PR ready.
