# 0427: Observability runbook — queries, dashboards, alerts

Status: todo
Depends on: 0425, 0426 | Base commit: 05a69e244bbf5a17478afb9cbe7a5c4a87159c9e | Branch: task/0427-observability-runbook
Executor: GLM Flash (owner's choice for this task) | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Complete docs/OBSERVABILITY.md so the owner answers, from a browser: server load, per-container CPU/RAM, disk headroom, per-user request volume and DB time, per-host storage — and gets alerts for high CPU, filling disk, a down container and a silent worker. All inside the Grafana Cloud free tier.

## 2. Context

Briefs 0425 and 0426 landed: logs ship to Loki (label container; access lines are key=value pairs ending in host=<id>; the worker logs a daily storage_report line), and metrics ship to Prometheus (jobs: node, cadvisor).

Log format facts the queries rely on (docs/OBSERVABILITY.md, brief 0426):

    method=GET route=/dashboard status=200 ms=12 q=3 db_ms=4 lock_ms=0 host=42

    storage_report total_bytes=… free_bytes=… db_bytes=… photos_bytes=… hosts=[{"host":1,…}]

Grafana LogQL parses key=value lines with | logfmt. Prometheus jobs are named node and cadvisor.

Excerpt (verbatim; if not found, STOP §8) — docs/OBSERVABILITY.md, the section brief 0425 created:

    ## Reading it

    Queries, dashboards and alerts are documented here by brief 0427.

## 3. Files

| Path | Action | What |
|---|---|---|
| docs/OBSERVABILITY.md | edit | replace the "Reading it" section with the full runbook below |
| docs/LIGHTSAIL.md | edit | add one line under "Day-to-day commands": logs and metrics are read in Grafana Cloud — see OBSERVABILITY.md |

No other file may change.

## 4. Steps

Step 1 — replace the "Reading it" section in docs/OBSERVABILITY.md with exactly:

    ## Reading it

    All queries run in Grafana → Explore (Loki or Prometheus), or in a panel.

    ### Requests and compute per user (Loki)

    Requests per host, last 24 h:

        sum by (host) (count_over_time({container="ubyhost"} |= "method=" | logfmt | host != "0" [24h]))

    Total request time per host (the compute proxy), top 10:

        topk(10, sum by (host) (sum_over_time(({container="ubyhost"} |= "method=" | logfmt | unwrap ms [24h]))))

    DB time per host, top 10:

        topk(10, sum by (host) (sum_over_time(({container="ubyhost"} |= "method=" | logfmt | unwrap db_ms [24h]))))

    Errors by route template, last hour:

        sum by (route) (count_over_time({container="ubyhost"} |= "method=" | logfmt | status >= 500 [1h]))

    Guest permalink traffic (no session): filter host="0".

    ### Storage (Loki, daily at 02:41 UTC)

        {container="worker"} |= "storage_report" | logfmt

    Per-host counts are in the hosts= JSON field; the byte totals are top-level.

    ### Server load (Prometheus)

    Host CPU %:

        100 * (1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])))

    Memory % used:

        100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)

    Disk % used on /:

        100 * (1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})

    Per-container CPU (cores):

        sum by (name) (rate(container_cpu_usage_seconds_total{name!=""}[5m]))

    Per-container memory:

        sum by (name) (container_memory_usage_bytes{name!=""})

    ### Dashboards (owner, once)

    1. Dashboards → Import → grafana.com id 1860 (Node Exporter Full) → Prometheus data source.
    2. New dashboard "UbyHost": one panel per query above (per-user, storage, container CPU/RAM).
    3. New dashboard "Containers": the two cadvisor queries.

    ### Alerts (owner, once; Grafana Cloud alerting is in the free tier)

    | Rule | Query | For |
    |---|---|---|
    | HighLoad | 100 * (1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m]))) > 85 for 10 m | e-mail the operator |
    | DiskFilling | 100 * (1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) > 85 for 30 m | e-mail |
    | ContainerDown | up{job="node"} == 0 for 5 m, or no method= line from ubyhost for 5 m | e-mail |
    | WorkerSilent | count_over_time({container="worker"} |= "storage_report" [26h]) < 1 | e-mail |

    Set the contact point to the operator e-mail and send one test alert.

Step 2 — docs/LIGHTSAIL.md: under "Day-to-day commands", after the logs.sh rows, add one line to the table:

    | Grafana Cloud (browser) | All logs, metrics and per-user queries — see [OBSERVABILITY.md](OBSERVABILITY.md) |

## 5. Do not touch

App/, deploy/, .github/workflows, any other doc. Never push, merge or deploy.

## 6. Commands

    python3 scripts/context_lint.py 2>&1 | tail -30

→ passes. (Docs-only brief; no test-map row.)

    grep -c "unwrap\|logfmt" docs/OBSERVABILITY.md

→ at least 5 (sanity: the queries landed).

## 7. Acceptance

- [ ] every named query in §4 step 1 appears in docs/OBSERVABILITY.md under Reading it
- [ ] the LIGHTSAIL.md table gains exactly one row
- [ ] git diff --stat lists only the two §3 files
- [ ] scripts/context_lint.py passes

## 8. Stop and ask

Standard template items, plus: the "Reading it" section from 0425 is missing or was already rewritten.

## 9. Report

Write docs/tasks/0427-report.md (600 tokens at most), Status: review, per the template.

## Risk list (for the reviewer)

docs/OBSERVABILITY.md, docs/LIGHTSAIL.md.

## Owner steps

1. Merge on green.
2. In Grafana: import dashboard 1860, build the two small dashboards, create the four alert rules with the operator e-mail.
3. Send a test alert once, then the runbook is complete.
4. Optional housekeeping (your call, not this brief): AGENTS.md still names Haiku 5.5 as the only executor while these briefs ran on GLM Flash — if that stays, record a [workflow] decision and update the AGENTS.md executor line.
