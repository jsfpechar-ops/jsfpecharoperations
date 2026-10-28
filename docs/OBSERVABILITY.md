# Observability: logs and metrics (Grafana Cloud)

Production runs three opt-in containers (deploy/lightsail/docker-compose.yml,
profile "monitoring"): alloy, node-exporter, cadvisor.

| Container | Sends | Where |
|---|---|---|
| alloy | every compose container's log lines | Grafana Cloud Loki |
| node-exporter | host CPU, memory, disk | Grafana Cloud Prometheus |
| cadvisor | per-container CPU, memory | Grafana Cloud Prometheus |
| ubyhost (app) | request counters + duration histogram per route *template* (`/metrics`, compose-internal only; caddy answers 404 to the world) | Grafana Cloud Prometheus, job `ubyhost` |

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
   COMPOSE_PROFILES=litestream,monitoring.
4. Run ./scripts/deploy.sh.
5. Grafana → Explore → Loki: {container="ubyhost"} must show lines;
   Prometheus: up must be 1 for the node and cadvisor jobs.

## Watchdog (who watches the watchman?)

`deploy/lightsail/scripts/monitoring-watchdog.sh` is a tiny cron-side script
that checks the monitoring stack itself every 15 minutes:

1. alloy, node-exporter and cadvisor containers are running;
2. Grafana Cloud Prometheus answers the `up` query with both the `node` and
   `cadvisor` series (i.e. remote-write is actually arriving, not just
   containers being up);
3. no `level=error` lines in alloy's log over the last 15 minutes
   (catches 401/404 auth or URL regressions early).

Prints one line per check and prints no tokens. Exit 0 = healthy.
With `UBYHOST_HEARTBEAT_MONITORING_URL` set (healthchecks.io or anything
with the same ping semantics) it pings the URL on success and `<url>/fail`
on any failure, so a dead monitoring stack emails you instead of going
quietly unnoticed. Cron line on the server:

    */15 * * * * cd /opt/ubyhost/deploy/lightsail && ./scripts/monitoring-watchdog.sh

## Reading it

Queries, dashboards and alerts are documented here by brief 0427. The app
metrics answer usage questions without any user data (OPS-3): rate of
`ubyhost_requests_total` per route template, error ratio by `status`, and
request latency from `ubyhost_request_duration_seconds` —
e.g. requests/s per feature: `sum by (route) (rate(ubyhost_requests_total[15m]))`.

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
lines, and Explore → Prometheus: `up` must be 1 for job="node" and
job="cadvisor".

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
