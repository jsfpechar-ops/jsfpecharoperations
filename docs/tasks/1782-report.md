# 1782 report — Caddy everything to Go

Status: review

## Commits

- `1782 step 1` — copy sidecars to §3 paths; `MANIFEST.sha256` all OK

## Step 0 anchors (pre-copy, current `main`)

| Check | Result |
|---|---|
| `reverse_proxy ubyhost:8080` in Caddyfile.cloudflare | 2 |
| `UBYHOST_GO_PATHS` in Caddyfile.cloudflare | 3 |
| `  ubyhost:` in docker-compose | 4 |
| `  worker:` in docker-compose | 1 |
| `ubyhost-go` in Caddyfile.cloudflare | 3 |
| CHECKLIST.md under 1782-files | 1 |
| Sidecar `.txt` count | 5 |

Anchors matched pre-1782 state; post-copy files match manifest.

## Commands

### `sha256sum -c docs/tasks/1782-files/MANIFEST.sha256`

```
deploy/lightsail/caddy/Caddyfile.acme: OK
deploy/lightsail/caddy/Caddyfile.cloudflare: OK
deploy/lightsail/docker-compose.yml: OK
docs/LIGHTSAIL.md: OK
```

### `bash deploy/lightsail/scripts/caddy-validate.sh`

```
deploy/lightsail/scripts/caddy-validate.sh: line 8: docker: command not found
```

Docker not available in executor environment (same as brief writer note).

### `python3 scripts/context_lint.py`

Last lines: `context lint: OK`

## Files changed

- `deploy/lightsail/caddy/Caddyfile.cloudflare`
- `deploy/lightsail/caddy/Caddyfile.acme`
- `deploy/lightsail/docker-compose.yml`
- `docs/LIGHTSAIL.md`
- `docs/tasks/1782-report.md` (this file)

## §7 not run here

- Staging `smoke-remote.sh`
- Route golden parity vs Python
- Owner CHECKLIST: all waves + 1772 + quiet week (owner sign-off)

## Deviations

None on diffs; sidecars applied byte-identical to manifest.

## Questions

None.

## Owner steps left

1. Confirm go-cutover preconditions and quiet week.
2. Run `bash deploy/lightsail/scripts/caddy-validate.sh` on a host with Docker.
3. Staging smoke per brief §6; then production deploy alone.
4. Run `deploy/lightsail/scripts/smoke-remote.sh` after deploy.