# Observability: logs and metrics (Grafana Cloud)

Production runs three opt-in containers (deploy/lightsail/docker-compose.yml,
profile "monitoring"): alloy, node-exporter, cadvisor.

| Container | Sends | Where |
|---|---|---|
| alloy | every compose container's log lines | Grafana Cloud Loki |
| node-exporter | host CPU, memory, disk | Grafana Cloud Prometheus |
| cadvisor | per-container CPU, memory | Grafana Cloud Prometheus |
| ubyhost (app) | request counters + duration histogram per route *template* (`/metrics`, compose-internal only; caddy answers 404 to the world) | Grafana Cloud Prometheus, job `ubyhost` |
| ubyhost-go (Go app, profile `go`) | `ubyhost_go_up` + request counter per route template and status code (`/metrics` on :8081) | Grafana Cloud Prometheus, job `ubyhost-go` |

Both Go slots (`ubyhost-go`, `ubyhost-go-b`) are scraped under job `ubyhost-go`; the idle slot is stopped, so `up == 0` for it is normal. While `COMPOSE_PROFILES` has no `go`, both Go targets are down and caddy logs a failed active health check for `ubyhost-go:8081` every 2 s — expected noise, all traffic still goes to `ubyhost` (Python).

## Privacy boundary

Log lines are exactly the lines the containers already write today (OPS-3:
PII-free, route templates only) plus the numeric host id on the access line
(brief 0426, owner decision). No guest data, no tokens, no query strings
ever reach Grafana Cloud. Grafana Labs is listed in the ROPA as a
subprocessor.

## Setup (owner, once)

1. grafana.com → free account → create the stack in the EU region.
2. Connections → copy the Prometheus URL/username/token and the Loki
   URL/username/token.
3. deploy/lightsail/.env: fill the GRAFANA_* values, keep
   COMPOSE_PROFILES=monitoring.
4. Run ./scripts/deploy.sh.
5. Grafana → Explore → Loki: {container="ubyhost"} must show lines;
   Prometheus: up must be 1 for the node, cadvisor and ubyhost jobs
   (and for the live ubyhost-go slot when the `go` profile is on).

## Watchdog (who watches the watchman?)

`deploy/lightsail/scripts/monitoring-watchdog.sh` is a tiny cron-side script
that checks the monitoring stack itself every 15 minutes:

1. alloy, node-exporter and cadvisor containers are running;
2. Grafana Cloud Prometheus answers the `up` query with the `node`, `cadvisor`
   and `ubyhost` series (i.e. remote-write is actually arriving, not just
   containers being up); when the `go` profile is on, at least one
   `ubyhost-go` slot must be up;
3. no `level=error` lines in alloy's log over the last 15 minutes
   (catches 401/404 auth or URL regressions early).

Prints one line per check and prints no tokens. Exit 0 = healthy.
With `UBYHOST_HEARTBEAT_MONITORING_URL` set (healthchecks.io or anything
with the same ping semantics) it pings the URL on success and `<url>/fail`
on any failure, so a dead monitoring stack emails you instead of going
quietly unnoticed. Cron line on the server:

    */15 * * * * cd /opt/ubyhost/deploy/lightsail && ./scripts/monitoring-watchdog.sh

## Reading it

All queries run in Grafana → Explore (Prometheus or Loki). Everything below is
PII-free by construction (OPS-3): route templates and numeric status codes
only, never a path, token or query string.

### What is where

| Data | Source | Job / stream |
|---|---|---|
| host CPU, memory, disk | node-exporter | Prometheus job `node` |
| per-container CPU, memory, restarts | cAdvisor | Prometheus job `cadvisor` |
| Python app: requests, latency, db time | `/metrics` on `ubyhost:8080` | Prometheus job `ubyhost` |
| Go app: up + requests | `/metrics` on `ubyhost-go:8081` | Prometheus job `ubyhost-go` |
| every container's logs | alloy | Loki, label `container` |

### Host (job `node`)

    # CPU % used, 5 m average
    100 * (1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])))
    # memory % used
    100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)
    # disk % used on /
    100 * (1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})

### Containers (job `cadvisor`)

    # CPU cores per container
    sum by (name) (rate(container_cpu_usage_seconds_total{name!=""}[5m]))
    # memory per container
    sum by (name) (container_memory_usage_bytes{name!=""})
    # restarts in the last hour
    sum by (name) (increase(container_start_time_seconds{name!=""}[1h]))

### Python app (job `ubyhost`)

Metric families: `ubyhost_requests_total{method,route,status}`,
`ubyhost_request_duration_seconds` (histogram),
`ubyhost_request_db_queries_total{method,route}`,
`ubyhost_request_db_seconds_total{method,route}`.

    # requests/s per route template
    sum by (route) (rate(ubyhost_requests_total[15m]))
    # 5xx ratio per route, last hour
    sum by (route) (rate(ubyhost_requests_total{status=~"5.."}[1h]))
      / sum by (route) (rate(ubyhost_requests_total[1h]))
    # p95 latency per route
    histogram_quantile(0.95, sum by (route, le) (rate(ubyhost_request_duration_seconds_bucket[15m])))
    # db seconds per request, per route
    sum by (route) (rate(ubyhost_request_db_seconds_total[15m]))
      / sum by (route) (rate(ubyhost_request_duration_seconds_count[15m]))

### Go app (job `ubyhost-go`)

Metric families: `ubyhost_go_up`, `ubyhost_go_http_requests_total{route,code}`.
Both slots are scraped; the idle slot is stopped, so `up == 0` for it is normal.

    # a live slot is up
    max(up{job="ubyhost-go"})
    # 5xx rate per route template
    sum by (route) (rate(ubyhost_go_http_requests_total{code=~"5.."}[15m]))

### Logs (Loki)

Access lines are logfmt (`method=GET route=/dashboard status=200 ms=12 db_ms=4 host=42`):

    # 5xx by route template, last hour
    sum by (route) (count_over_time({container="ubyhost"} |= "method=" | logfmt | status >= 500 [1h]))
    # requests per host, last 24 h
    sum by (host) (count_over_time({container="ubyhost"} |= "method=" | logfmt | host != "0" [24h]))
    # worker alive (no /metrics; it logs when it runs jobs)
    count_over_time({container="worker"}[1h]) > 0

### Deliberate gaps (do not "fix" without an owner decision)

- Caddy request metrics are not collected: brief 1808 is a planned win, OPS-3
  keeps caddy access logs off, and the admin endpoint stays container-local.
  Traffic by status is measured at the app (`ubyhost_requests_total`,
  `ubyhost_go_http_requests_total`).
- Postgres has no exporter (new dependency, owner decision): per-container
  CPU/RAM comes from cAdvisor, db time from `ubyhost_request_db_seconds_total`
  and the `db_ms` log field.

## Verifying the pipeline (post-deploy health check)

On the Lightsail host, in `deploy/lightsail/`:

```bash
# Alloy is up and error-free
docker compose --profile monitoring ps
docker logs ubyhost-alloy-1 --since 15m 2>&1 | grep -Ei 'error|401|403' || echo none

# Loki: entries read and forwarded, nothing stalled at relabel
IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ubyhost-alloy-1)
curl -s http://$IP:12345/metrics | grep -E '^loki_(source_docker|relabel|write)'
# loki_source_docker_target_entries_total climbing,
# loki_relabel_entries_written climbing (0 here = entries rejected downstream),
# loki_write_dropped_entries_total absent or 0.
```

Then in Grafana, Explore → Loki: `{container=~".+"}` (last 15m) must show
lines, and Explore → Prometheus: `up` must be 1 for job="node",
job="cadvisor" and job="ubyhost" (plus the live slot of job="ubyhost-go"
when the `go` profile is on).

Gotcha: Grafana Cloud Loki rejects any push containing an entry older than
its 7-day ingestion window, discarding the whole batch. The config drops
entries older than 168h (`loki.process "drop_old"`), so a long-lived host's
old container logs cannot poison the batches. If logs still fail to arrive,
check `GRAFANA_LOKI_TOKEN` with a one-line smoke push:

```bash
set -a; source ./.env; set +a
curl -sS -u "$GRAFANA_LOKI_USER:$GRAFANA_LOKI_TOKEN" \
  -H 'Content-Type: application/json' -X POST "$GRAFANA_LOKI_URL" \
  --data '{"streams":[{"stream":{"container":"smoke-test"},"values":[["'"$(python3 -c 'import time; print(int(time.time()*1e9))')"'","hello"]]}' \
  -w '\n--- HTTP %{http_code} ---\n'
```

204 = credentials and URL good; 401 = bad token (needs logs:write scope);
400 = read the error body — a `too old` timestamp means the 7-day window.

## Costs and limits

Grafana Cloud free tier (check the current numbers on the pricing page):
roughly 10 000 active Prometheus series and 50 GB log ingestion per month.
This stack uses about 800–1 500 series at a 30 s interval — inside the free
tier, $0, and no AWS credits are touched.
