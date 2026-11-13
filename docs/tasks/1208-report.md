# 1208 report

Status: review

## 1. Files changed (commits on local branch exec-1208, not pushed)

- `deploy/lightsail/caddy/Caddyfile.cloudflare`: AOP snippets (`aop_off`, `aop_check`, `aop_enforce`) defined before the site block; `tls` block imports `aop_{$UBYHOST_AOP_MODE:off}`; probe handler split into `aop_probe_check` (the only one that handles `/__aop_probe`) and empty `aop_probe_off` / `aop_probe_enforce`, imported above the `@go` comment.
- `deploy/lightsail/docker-compose.yml`: caddy `environment:` gets `UBYHOST_AOP_MODE: ${UBYHOST_AOP_MODE:-off}`.
- `.github/workflows/ci.yml`: `caddy` job gets the AOP block (throwaway CA in `caddy/certs/aop-ca.pem`, removed at the end).
- `docs/ENVIRONMENT.md`: `UBYHOST_AOP_MODE` row.
- `docs/CLOUDFLARE.md`: section "Authenticated Origin Pulls (zone-level)" with the owner runbook.
- `docs/OPERATIONS.md`: two lines at the end of `## Scheduled jobs`.
- `docs/context/known-issues.md`: K-S14 row (120 chars, was 126).
- Commits: `3bb51fbc` (steps 2-3), `f5868069` (step 4), then one commit for docs and this report.

## 2. Commands

- `python3 scripts/context_lint.py | tail -30`: "context lint: OK" (warnings are pre-existing).
- `YAML parse of docker-compose.yml and ci.yml`: "yaml ok".
- `grep -rln Caddyfile App/tests`: no hits.
- `caddy validate` / `scripts/caddy-validate.sh`: not run locally (no caddy binary on PATH, no Docker). The CI `caddy` job is the first real test.

## 3. Brief section 7

- [x] Only §3 files changed.
- [x] Mode `off` (default) keeps `tls` without `client_auth`. Not run; logic checked by reading.
- [ ] enforce / off / check validation: not run locally (CI).
- [x] No domain, zone id, token or key added.
- [x] Context lint passes; `Caddyfile.acme` untouched.
- [x] No log directive added; probe returns only the issuer.

## 4. Deviations

- Probe placed in snippets, not inline: the orchestrator override requires the probe to exist only in check mode.
- K-S14 row last cell shortened to "1208 zone AOP; owner sets enforce" and middle cell to "Any Cloudflare account reaches origin" so the row is not longer.
- Commits are grouped (steps 2-3, step 4, docs) rather than one per step.

## 5. Questions

- `deploy/lightsail/scripts/finish-bootstrap.sh:68` curls `https://${DOMAIN}/healthz` (`|| true`). It goes through Cloudflare if DNS is proxied; it cannot break enforce. Owner to confirm.
- The import of `aop_{$UBYHOST_AOP_MODE:off}` is unverified until CI runs. An unknown mode value (for example a typo) fails Caddy startup.

## 6. Owner steps left

- Push the branch and open a draft PR (orchestrator does this).
- Runbook steps 1-12 in docs/CLOUDFLARE.md, after deploy.
