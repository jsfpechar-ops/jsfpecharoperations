# 1830: Deploy safety 1: two-copy deploy of `ubyhost-go` with a health check before the switch

Status: todo
Depends on: none (first of 1830, 1831, 1832, 1833) | Base commit: current tip of the working branch | Branch: task/1830-deploy-two-copy-health
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (deploy, migrations and filing run next to this code; exact diffs only; fresh review of the full diff before ready)
Plan: [guest-form-isolation](../plans/guest-form-isolation.md) section 6 and 9.

> **One PR mode.** Commit each step as `1830 step k`. Never push, merge or deploy. Hand the owner the staging steps in §10.

## 1. Objective

A new `ubyhost-go` image starts beside the old one, must pass `/healthz`, and only then takes traffic; the old copy is stopped last. Python (`ubyhost`) keeps today's single-copy restart in this brief.

## 2. Context

Hard rules: 1 filing correctness first (nothing here may change what is filed or when); 3 no secrets, no server names or IPs in the repo; 4 no new dependency; 8 green merges auto-deploy.

**Mechanism chosen: two compose service slots plus Caddy active health checks.** Slot A is the existing service `ubyhost-go` (port 8081). Slot B is a new service `ubyhost-go-b` that `extends` it. Caddy lists both as upstreams with `lb_policy first` and an active check on `/healthz`. Deploy rotates: start the idle slot on the new image, wait until Docker reports it healthy, then stop the old slot. Why this one: no new dependency, no new container type, Caddy already does health checks, and Caddy is reloaded (never recreated) so it works with brief 1833. A scaled service (`--scale ubyhost-go=2`) was rejected: it cannot name which copy runs which image, so "stop the old one" is guesswork.

**Memory.** `ubyhost-go` has `mem_limit: ${UBYHOST_GO_MEM:-128m}`. Two copies for a few seconds cost at most 128 MB more: fine on the 8 GB host and on the 2 GB target.

**Python web container: NOT two-copy in this brief.** `ubyhost` has `mem_limit: ${UBYHOST_WEB_MEM:-2g}` and peaks at 1.26 GB; two copies need about 2.6 GB, which does not fit the 2 GB target server and is tight on 8 GB beside Postgres. In the meantime Python gets: the existing health wait, the public check, and (brief 1832) automatic rollback; plus in brief 1833 a maintenance page while it restarts. When the Python web service leaves compose (task 1782) the problem disappears. Open question 3 asks whether the owner wants an opt-in two-copy flag for the 8 GB host.

**Jobs.** `go/internal/jobs/queue.go` claims jobs with `SKIP LOCKED` and a lease, so two Go copies running for seconds do not run one job twice.

**Precondition: migrations are add-only within a release, so the old copy keeps working on the new schema.** The rule is written in `docs/context/rules.md` line 47 (Goose files must be additive). No automated check exists today (see open question 1). This brief only adds a deploy-time echo of the rule; the executor must not write a migration lint.

Current anchors (verify with `grep -nF`):

`deploy/lightsail/docker-compose.yml`:
```
  ubyhost-go:
    image: ubyhost-go:local
    profiles: ["go"]
    mem_limit: ${UBYHOST_GO_MEM:-128m}
    depends_on:
      ubyhost:
        condition: service_healthy
```
`deploy/lightsail/scripts/deploy.sh` (lines 216 to 222 and 251):
```
if docker image inspect ubyhost-go:local >/dev/null 2>&1; then
  docker tag ubyhost-go:local ubyhost-go:previous
...
    docker tag "${UBYHOST_GO_IMAGE}" ubyhost-go:local
```
and (lines 317 to 318):
```
docker compose pull caddy
docker compose up -d --remove-orphans
```
`deploy/lightsail/caddy/Caddyfile.cloudflare` and `Caddyfile.acme` both contain, in two places:
```
reverse_proxy ubyhost-go:8081 {
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `deploy/lightsail/docker-compose.yml` | edit | add service `ubyhost-go-b`; image tag of slot A |
| `deploy/lightsail/caddy/Caddyfile.cloudflare` | edit | both Go `reverse_proxy` blocks: two upstreams plus health check |
| `deploy/lightsail/caddy/Caddyfile.acme` | edit | same |
| `deploy/lightsail/scripts/deploy.sh` | edit | slot rotation after `up -d` |
| `deploy/lightsail/scripts/go-slot.sh` | create | small helper: live slot, idle slot, wait healthy (keeps deploy.sh readable) |
| `docs/tasks/1830-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

1. **Compose.** In `docker-compose.yml` change slot A to its own tag and add slot B directly after the `ubyhost-go:` service block (before the `mock-ubyport` comment):
   - Slot A: `image: ubyhost-go:local` becomes `image: ubyhost-go:slot-a`. Keep `build:` as is.
   - Slot B (exact text):
```
  # 1830: second slot of ubyhost-go. deploy.sh starts the idle slot on the new
  # image, waits for healthy, then stops the old one. Never built here.
  ubyhost-go-b:
    extends:
      service: ubyhost-go
    image: ubyhost-go:slot-b
    profiles: ["go"]
```
   Run `docker compose --profile go config > /tmp/c.yml 2>&1; grep -c 'ubyhost-go' /tmp/c.yml | tail -30` then check with `grep -A2 'ubyhost-go-b:' /tmp/c.yml` that slot B shows the same `environment`, `volumes`, `healthcheck` and `mem_limit` as slot A (`grep -c mem_limit` equal for both). If `extends` drops any of them or errors: STOP (§8).
2. **Caddy, both files.** Replace both occurrences of `reverse_proxy ubyhost-go:8081 {` with the block below. Keep every inner line (`header_up`, `@not_ported`, `handle_response`) exactly as it is, and add these lines first inside the block:
```
		reverse_proxy ubyhost-go:8081 ubyhost-go-b:8081 {
			# 1830: two slots. "first" sends traffic to slot A while it is healthy,
			# else slot B. The active check marks a stopped slot down within 2 s;
			# a request that hits a stopping slot is retried on the other for up to 5 s.
			lb_policy first
			lb_try_duration 5s
			lb_try_interval 250ms
			health_uri /healthz
			health_interval 2s
			health_timeout 2s
			health_status 200
```
   Keep the existing tab indentation of the file (the `@go_read` block is two tabs deep, the `handle @go` block is two tabs deep; match the line you replace). Do not touch the Python upstream blocks.
3. **Helper `scripts/go-slot.sh`** (create, `chmod +x`). Exact text:
```bash
#!/usr/bin/env bash
# 1830: slot helpers for deploy.sh. Source it, do not run it.
# Slot A is the compose service ubyhost-go, slot B is ubyhost-go-b.
# .go-slot (beside docker-compose.yml, not in git) holds the live slot: a or b.
set -euo pipefail

go_svc() { if [ "$1" = "a" ]; then echo ubyhost-go; else echo ubyhost-go-b; fi; }

go_live_slot() {
  local s
  s="$(cat .go-slot 2>/dev/null || echo a)"
  case "${s}" in a | b) echo "${s}" ;; *) echo a ;; esac
}

go_idle_slot() { if [ "$(go_live_slot)" = "a" ]; then echo b; else echo a; fi; }

# go_wait_healthy <slot> <seconds>: 0 when Docker reports the container healthy.
go_wait_healthy() {
  local cid status i
  for i in $(seq 1 "$2"); do
    cid="$(docker compose --profile go ps -q "$(go_svc "$1")" 2>/dev/null || true)"
    if [ -n "${cid}" ]; then
      status="$(docker inspect -f '{{.State.Health.Status}}' "${cid}" 2>/dev/null || true)"
      [ "${status}" = "healthy" ] && return 0
    fi
    sleep 1
  done
  return 1
}
```
4. **deploy.sh rotation.** Directly after the line `docker compose up -d --remove-orphans` (line 318) and before the `# Reload Caddy unconditionally` comment, insert (the Go block runs only when the Go service exists in this stack):
```bash
# 1830: two-copy deploy of ubyhost-go. The idle slot gets the new image and
# must be healthy before the old slot stops. Migrations are add-only, so the
# old copy keeps working on the new schema (docs/context/rules.md).
if docker compose --profile go config --services | grep -qx 'ubyhost-go' \
  && docker image inspect ubyhost-go:local >/dev/null 2>&1; then
  # shellcheck disable=SC1091
  source ./scripts/go-slot.sh
  LIVE_SLOT="$(go_live_slot)"
  NEW_SLOT="$(go_idle_slot)"
  echo "==> Starting ubyhost-go slot ${NEW_SLOT} beside slot ${LIVE_SLOT}"
  docker tag ubyhost-go:local "ubyhost-go:slot-${NEW_SLOT}"
  docker compose --profile go up -d --no-build --no-deps --force-recreate "$(go_svc "${NEW_SLOT}")"
  if ! go_wait_healthy "${NEW_SLOT}" 60; then
    echo "New ubyhost-go copy (slot ${NEW_SLOT}) never became healthy; the old copy keeps serving." >&2
    docker compose --profile go stop "$(go_svc "${NEW_SLOT}")" || true
    rollback
    exit 1
  fi
  echo "${NEW_SLOT}" > .go-slot
  sleep 3 # one Caddy health interval, so Caddy sees the new copy before the old one stops
  docker compose --profile go stop "$(go_svc "${LIVE_SLOT}")" || true
  echo "ubyhost-go now runs on slot ${NEW_SLOT}."
fi
```
   Notes for the executor: do not change the `docker compose up -d --remove-orphans` line itself. If, on staging, that line recreates a running Go slot (see §10 check 3), report it, do not fix it.
5. Run the commands of §6. Commit.

## 5. Do not touch

`rollback()` and the `:previous` lines (brief 1832 owns them); the Python upstream blocks and the `not_ported` fallback to `ubyhost:8080`; `UBYHOST_GO_PATHS`; any migration, `App/`, `go/`; filing code; `.env` or any server file.

## 6. Commands

From the repo root, each ending `2>&1 | tail -30`:
- `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30` (CI job `shellcheck`)
- `cd deploy/lightsail && docker compose --profile go config -q 2>&1 | tail -30` (needs a `.env`; if there is none, copy `.env.example` to a temp path and pass `--env-file`; never commit it)
- Caddy: replicate CI job `caddy` (`.github/workflows/ci.yml` lines 650 to 692): for each of `Caddyfile.acme` and `Caddyfile.cloudflare`, `cp` it to `caddy/Caddyfile.active`, then `./scripts/caddy-validate.sh 2>&1 | tail -30`. The Cloudflare file needs the dummy certificate step shown there.
- Test-map row "Deploy scripts, Caddyfile, compose": `test_pg_*script*.py` from `App/`: `.venv/bin/python -m pytest $(ls tests/test_pg_*script*.py) -q --tb=short -x 2>&1 | tail -30`.

## 7. Acceptance

- [ ] shellcheck, compose config, both `caddy validate` and the pytest row are green.
- [ ] `git diff --stat` lists only the §3 paths.
- [ ] Both Caddyfiles contain `lb_policy first` exactly twice each; `grep -c 'ubyhost:8080'` is unchanged from before.
- [ ] `grep -nF 'source ./scripts/go-slot.sh' deploy/lightsail/scripts/deploy.sh` finds one line.

## 8. Stop and ask

An anchor is not found; `extends` loses a field of slot A; Caddy validate rejects `health_*` or `lb_*` options (report the exact error); a file outside §3 needs a change; a test fails twice; 25 tool calls reached.

## 9. Report

`docs/tasks/1830-report.md`, 600 tokens at most: files changed, each command with the last 5 lines, §7 ticked, deviations, open questions, owner steps left.

## 10. Staging before production (owner steps; green merges auto-deploy, so staging comes first)

Staging is the Deploy staging workflow (`deploy-staging.yml`, manual, branch picker, mock UbyPort). Keep the PR a draft until these pass.
1. Actions, Deploy staging, pick branch `task/1830-deploy-two-copy-health`, run. On the server run `cd <deploy dir> && cat .go-slot && docker compose --profile go ps | tail -30`: one Go slot `healthy`, the other stopped.
2. Run Deploy staging again. `.go-slot` flipped; during the run, in a second terminal, `while true; do curl -s -o /dev/null -w '%{http_code}\n' <staging url>/healthz; sleep 0.5; done` shows no run of non-200 longer than 2 seconds.
3. Deploy a change that touches only Python. `docker inspect -f '{{.State.StartedAt}}' $(docker compose --profile go ps -q <live go service>)` must be unchanged. If it restarted, tell the orchestrator (open question 2).
4. Break it on purpose: set `UBYHOST_GO_JOB_KINDS=nonsense` in staging `.env`... only if the new slot then fails to become healthy; expected: deploy stops, old copy keeps serving. Otherwise skip this check and say so.
Only then does the owner mark the PR ready.

## Rollback

`git revert` the PR and deploy. Slot B stays defined but unused; `docker compose --profile go stop ubyhost-go-b`; delete `.go-slot`. Slot A's image tag returns to `ubyhost-go:local` with the revert.

## Open questions for the orchestrator

1. No automated check enforces add-only migrations today (only `docs/context/rules.md` line 47). Needed before the precondition is more than a promise: a lint of new `App/migrations_pg/` files for `DROP`, `RENAME`, `SET NOT NULL`, type changes. Plan brief 1845 lints only the contract tables. Write a separate brief for all migrations?
2. `ubyhost-go` has `depends_on: ubyhost: condition: service_healthy`. Compose may recreate a dependent when `ubyhost` is recreated, which would bounce the live Go slot on every Python deploy and defeat the zero-gap goal. Cannot be proven without a run; staging check 3 tests it. If it fails, a follow-up brief must remove that `depends_on` for the slots.
3. Opt-in two-copy for Python on the 8 GB host (env flag, default off)? Not done here.
4. The `extends` keyword inside one file needs Docker Compose v2; the version on the server is not in the files read. Step 1 checks it with `config`.
