# Observability: logs and metrics (Grafana Cloud)

Production runs three opt-in containers (deploy/lightsail/docker-compose.yml,
profile "monitoring"): alloy, node-exporter, cadvisor.

| Container | Sends | Where |
|---|---|---|
| alloy | every compose container's log lines | Grafana Cloud Loki |
| node-exporter | host CPU, memory, disk | Grafana Cloud Prometheus |
| cadvisor | per-container CPU, memory | Grafana Cloud Prometheus |

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

Queries, dashboards and alerts are documented here by brief 0427.

## Costs and limits

Grafana Cloud free tier (check the current numbers on the pricing page):
roughly 10 000 active Prometheus series and 50 GB log ingestion per month.
This stack uses about 800–1 500 series at a 30 s interval — inside the free
tier, $0, and no AWS credits are touched.
