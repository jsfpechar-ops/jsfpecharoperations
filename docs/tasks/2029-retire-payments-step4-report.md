# 2029 step 4 report

Status: review

## Files changed
- `deploy/lightsail/docker-compose.yml` — `UBYHOST_PAYMENTS_RETIRED` passthrough on `ubyhost-go`
- `.env.example` — retired flag and dormant Stripe comments
- `docs/ENVIRONMENT.md` — retired paragraph, `UBYHOST_PAYMENTS_RETIRED` row, `UBYHOST_GO_PATHS` webhook note
- `deploy/lightsail/caddy/Caddyfile.*` — no edit (`rg` found no payment-specific matchers)

## Commands (last 5 lines)
- `rg -n 'pay|webhook|/p/' deploy/lightsail/caddy` → empty
- `UBYHOST_AOP_MODE=off ./scripts/caddy-validate.sh` → (see PR CI `caddy` job)
- `shellcheck -S error deploy/lightsail/scripts/*.sh` → not installed in cloud VM; CI `shellcheck` job runs it

## §7 (step 4 scope)
- [x] Compose passes `UBYHOST_PAYMENTS_RETIRED` to Go
- [x] `.env.example` and `ENVIRONMENT.md` document dormant Stripe + retired flag
- [x] Caddy confirmed: all traffic to Go; no payment path matchers to change
- [x] No live `.env`, no secrets in diff

## Deviations
- Local `shellcheck` binary missing; rely on CI.

## Questions
None.

## Owner
Do not set `UBYHOST_PAYMENTS_RETIRED=1` until steps 1–4 are merged (per brief).