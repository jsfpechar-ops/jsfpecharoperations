# Brief 1782 exact-diff pass (checklist-only, 2026-11-20)

Deploy sidecars for the four §3 paths and `MANIFEST.sha256` are checked in (exact-diff deploy pass 2026-11-20). Haiku must still wait on the preconditions below and owner sign-off before step 0.

## Preconditions (executor step 0)

- Every wave in [go-cutover-runbook](../plans/go-cutover-runbook.md) complete; brief **1772** scheduler switch done; one quiet week on production (owner sign-off).
- `python3 scripts/context_lint.py` clean for this brief’s status line.

## §3 paths (no sidecar `.txt` yet)

| Path | Intended change |
|---|---|
| `deploy/lightsail/caddy/Caddyfile.cloudflare` | Default `handle` → `ubyhost-go:8081` / `ubyhost-go-b:8081`; remove or retire `UBYHOST_GO_PATHS` path split and Python GET/HEAD fallback block when owner deletes the env var. |
| `deploy/lightsail/caddy/Caddyfile.acme` | Same as cloudflare variant. |
| `deploy/lightsail/docker-compose.yml` | Remove `ubyhost` and `worker` services; keep last Python image tag documented for 30-day rollback. |
| `docs/LIGHTSAIL.md` | Service list matches compose. |

## Executor order (when sidecars land)

1. Copy sidecars / apply patches; `sha256sum -c docs/tasks/1782-files/MANIFEST.sha256`.
2. `bash deploy/lightsail/scripts/caddy-validate.sh`
3. Staging `smoke-remote.sh` per brief §6.
4. Report §9; owner deploy alone.

## Rollback

Re-add `ubyhost` + `worker` from git; restore saved image tag; Caddy default back to Python until paths wave is reversed.