# 1201: Compose container hardening (cap_drop, no-new-privileges, monitoring network)

Status: todo
Depends on: none | Base commit: 29f86658 | Branch: task/1201-compose-hardening
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Drop all Linux capabilities and block privilege escalation on the internet-facing containers (ubyhost, worker, ubyhost-go, caddy), and move node-exporter and cadvisor onto a separate internal `monitoring` network so a compromised app container cannot reach them. This limits the damage of an app compromise or SSRF; it changes no app behaviour.

## 2. Context

Only `deploy/lightsail/docker-compose.yml` changes. Production runs `COMPOSE_PROFILES=walg,monitoring,go`. **Merges auto-deploy: the PR stays a draft.**

Capability check already done by the orchestrator (do not redo it):

- `ubyhost` and `worker` (Dockerfile at repo root): `USER ubyhost` (uid 10001) from the image, entrypoint `docker-entrypoint.sh` is plain sh (no chown, no gosu), uvicorn binds 8080 (above 1024), writes only `/data` (owned by ubyhost). Needs NO capability.
- `ubyhost-go` (go/Dockerfile): alpine, `USER ubyhost`, static binary, binds 8081, `/data` is mounted read-only. Needs NO capability.
- `caddy` (official image, runs as root): binds 80/443 -> needs `NET_BIND_SERVICE` (the only cap_add). Writes only `caddy-data` and `caddy-config` volumes (root-owned, it created them). Reads mounted `Caddyfile.active` and `caddy/certs` read-only. Open risk, owner checks it (see Owner steps): with `cap_drop: ALL` root loses DAC_OVERRIDE/DAC_READ_SEARCH, so `origin-key.pem` must be world-readable or owned by uid 0. If it is not, Caddy fails to start. Do NOT add DAC caps; the owner decides.
- Alloy config (`deploy/lightsail/monitoring/config.alloy`): scrapes `node-exporter:9100`, `cadvisor:8080` and `ubyhost:8080`, reads `/var/run/docker.sock`, ships to Grafana Cloud over the internet. So alloy must be on BOTH `web` (reaches ubyhost, has internet) and `monitoring`. node-exporter and cadvisor only need `monitoring`.
- Docker `internal: true` networks have no internet. node-exporter/cadvisor need none. Alloy keeps `web` for egress.

Exact excerpts (each must be found; else STOP, §8). All in `deploy/lightsail/docker-compose.yml`:

A. ubyhost, ends (about line 135-140):
```
        max-size: "10m"
        max-file: "5"
    networks:
      - web

  # WP06: the background scheduler
```
Unique anchor: `    mem_limit: ${UBYHOST_WEB_MEM:-2g}` (about line 125).
B. worker anchor: `    mem_limit: ${UBYHOST_WORKER_MEM:-1g}`.
C. ubyhost-go anchor: `    mem_limit: ${UBYHOST_GO_MEM:-128m}`.
D. caddy anchor: `    mem_limit: ${UBYHOST_CADDY_MEM:-256m}`.
E. existing hardening pattern (walg, lines 86-87), copy this style:
```
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
```
F. Bottom of file:
```
networks:
  web:
    name: ubyhost-web
```

## 3. Files

| Path | Action | What |
|---|---|---|
| deploy/lightsail/docker-compose.yml | edit | cap_drop and no-new-privileges on 4 services; `monitoring` network; reassign 3 monitoring services |

No other file may change. (Not changed on purpose: alloy `--server.http.listen-addr=0.0.0.0:12345`, see Questions in §9; no `read_only`.)

## 4. Steps

1. **ubyhost.** `grep -nF '    mem_limit: ${UBYHOST_WEB_MEM:-2g}' deploy/lightsail/docker-compose.yml`. Insert directly after that line:
```
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
```
2. **worker.** Same with anchor `    mem_limit: ${UBYHOST_WORKER_MEM:-1g}`; insert the same two lines after it.
3. **ubyhost-go.** Same with anchor `    mem_limit: ${UBYHOST_GO_MEM:-128m}`; insert the same two lines after it.
4. **caddy.** Anchor `    mem_limit: ${UBYHOST_CADDY_MEM:-256m}`; insert after it:
```
    # Root image: it only needs to bind 80/443. Everything else is dropped.
    cap_drop: [ALL]
    cap_add: [NET_BIND_SERVICE]
    security_opt: ["no-new-privileges:true"]
```
5. **Networks block.** Replace the file's last lines (excerpt F) with:
```
networks:
  web:
    name: ubyhost-web
  # 1201: scrape side of the monitoring stack. internal = no route to the
  # internet and no published ports; the app containers are not on it.
  # Only alloy joins it besides web (alloy still needs web to reach ubyhost
  # and Grafana Cloud).
  monitoring:
    name: ubyhost-monitoring
    internal: true
```
6. **alloy** (service block starts `  alloy:`; its last lines are `    networks:` / `      - web`). Change that `networks:` list to:
```
    networks:
      - web
      - monitoring
```
7. **node-exporter** (service `  node-exporter:`): change its `networks:` list from `- web` to `- monitoring`.
8. **cadvisor** (service `  cadvisor:`): change its `networks:` list from `- web` to `- monitoring`.

Use `grep -n 'networks:' deploy/lightsail/docker-compose.yml` and `sed -n` ranges of 40 lines to place steps 6-8; each service's `networks:` is the last key of its block. Do not change `privileged: true` on cadvisor (it needs it). Commit `1201 step k` after each step.

## 5. Do not touch

- Any other file (Dockerfiles, Caddyfiles, alloy config, docs, tests).
- `read_only`, `privileged`, volumes, ports, `profiles:` lines, `postgres`, `walg`, `mock-ubyport` (leave as is).
- AGENTS.md hard rules: 3 (no secrets), 4 (no dependency), 8 (never push to main, never merge; keep the PR a draft).

## 6. Commands

Run from the repo root. `.env` is gitignored and required by compose, so create an empty one, run, delete it.

```
touch deploy/lightsail/.env
COMPOSE_PROFILES=walg,monitoring,go UBYHOST_DOMAIN=x.test ACME_EMAIL=a@x.test docker compose -f deploy/lightsail/docker-compose.yml config -q 2>&1 | tail -30
COMPOSE_PROFILES=walg,monitoring,go UBYHOST_DOMAIN=x.test ACME_EMAIL=a@x.test docker compose -f deploy/lightsail/docker-compose.yml config 2>&1 | grep -nE '^  [a-z-]+:$|cap_drop|cap_add|no-new-privileges|ubyhost-monitoring|ubyhost-web' | tail -60
rm deploy/lightsail/.env
```
Expected: first command prints nothing. Second: ubyhost, worker, ubyhost-go, caddy, walg each show cap_drop and no-new-privileges; caddy also shows NET_BIND_SERVICE; alloy lists both networks; node-exporter and cadvisor only `monitoring`. (If docker is missing, use: `python3 -c "import yaml;d=yaml.safe_load(open('deploy/lightsail/docker-compose.yml'));print(d['networks'])"` and read the services' keys.)

Repo checks (from `App/`):
```
.venv/bin/python -m pytest tests/test_wp32_container_sizing.py tests/test_pg_cutover_script.py tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30
```
(these three files read `docker-compose.yml`.) From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] `docker compose config -q` (profiles `walg,monitoring,go`) exits 0 with no output.
- [ ] ubyhost, worker, ubyhost-go, caddy: `cap_drop: [ALL]` and `no-new-privileges:true`; caddy alone has `cap_add: [NET_BIND_SERVICE]`.
- [ ] node-exporter and cadvisor are only on `monitoring`; alloy on `web` and `monitoring`; `monitoring` is `internal: true`.
- [ ] The three pytest files and `context_lint.py` pass.
- [ ] `git diff --stat` shows only `deploy/lightsail/docker-compose.yml` (plus the task/report files).
- [ ] The PR is a draft and its text has the rollback line and the post-deploy list below.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or anchor is not found, or appears twice;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1201-report.md` (600 tokens at most) and set `Status: review`. Open ONE **draft** PR (`gh pr create --draft`). The PR text must include these lines:

- `Rollback: revert this PR, then on the server run docker compose up -d (compose recreates the changed containers).`
- Post-deploy list for the owner (copy the "Owner steps" section below).
- `Why no new outbound request / no personal data: config only.`

The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions. Always include: "Alloy still listens on 0.0.0.0:12345 on `web`, so the app container can still reach it. Decision needed: bind to 127.0.0.1 (then docs/OBSERVABILITY.md line 70-71 curl-by-container-IP check must change)."
6. Owner steps left.

## Risk list (for the reviewer)

- `deploy/lightsail/docker-compose.yml`: caddy cap changes (cert readability, see Owner step 1), the `monitoring` network (alloy must keep both networks, or scraping of node-exporter/cadvisor or Grafana shipping breaks).

## Owner steps

Do this at a quiet time. Merging auto-deploys.

1. Before merging, on the server run `ls -l /opt/ubyhost/deploy/lightsail/caddy/certs/ /opt/ubyhost/deploy/lightsail/caddy/Caddyfile.active`. Both `.pem` files and the Caddyfile must show `r` for "others" (like `-rw-r--r--`) or the owner `root`. If `origin-key.pem` is `-rw-------` owned by another user, run `chmod 644` on it first (or tell the orchestrator before merging).
2. In the PR, click "Ready for review", then merge with `scripts/merge-pr-on-green.sh`.
3. After the deploy, run `docker compose --profile monitoring ps` in `/opt/ubyhost/deploy/lightsail`. Every container must say `running` or `healthy`; none may say `restarting`.
4. Open `https://<your domain>/healthz`. It must answer OK.
5. Run `docker logs ubyhost-caddy-1 --since 10m 2>&1 | tail -20`. No "permission denied" and no "bind" errors.
6. Open Grafana Cloud, Explore, Prometheus: wait 5 minutes, then check `up{job="node"}`, `up{job="cadvisor"}` and `up{job="ubyhost"}` all show 1. In Loki, container logs of the last 5 minutes must appear.
7. If anything fails: revert the PR on GitHub, merge the revert, run `docker compose up -d` in `/opt/ubyhost/deploy/lightsail`, and tell the orchestrator.
