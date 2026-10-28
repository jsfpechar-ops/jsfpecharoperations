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

## Reading it

Queries, dashboards and alerts are documented here by brief 0427. The app
metrics answer usage questions without any user data (OPS-3): rate of
`ubyhost_requests_total` per route template, error ratio by `status`, and
request latency from `ubyhost_request_duration_seconds` —
e.g. requests/s per feature: `sum by (route) (rate(ubyhost_requests_total[15m]))`.

## Costs and limits

Grafana Cloud free tier (check the current numbers on the pricing page):
roughly 10 000 active Prometheus series and 50 GB log ingestion per month.
This stack uses about 800–1 500 series at a 30 s interval — inside the free
tier, $0, and no AWS credits are touched.
