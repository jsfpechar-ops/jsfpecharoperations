# 0425: Monitoring pipeline — Alloy + cAdvisor + node-exporter → Grafana Cloud

Status: todo
Depends on: none | Base commit: 05a69e244bbf5a17478afb9cbe7a5c4a87159c9e | Branch: task/0425-monitoring-pipeline
Executor: GLM Flash (owner's choice for this task) | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add three opt-in compose services (Grafana Alloy, cAdvisor, node-exporter) that ship all container logs plus host and per-container CPU/memory/disk metrics to the Grafana Cloud free tier (EU region). The owner then reads logs and server load in a browser instead of SSH. No App/ change, no new Python dependency, $0 cost, no AWS credits.

## 2. Context

Owner decisions from chat (2026-10-27), recorded in docs/context/decisions.md in step 6:

- Grafana Cloud free tier, EU region, is the destination for operational logs and metrics. Grafana Labs becomes a subprocessor (ROPA entry comes with brief 0426). Logs stay PII-free (OPS-3) — the only identifier (numeric host id) is added by brief 0426 as its own owner decision.
- New monitoring containers: grafana/alloy, gcr.io/cadvisor/cadvisor, prom/node-exporter (hard rule 4: no new dependency without an owner decision line).

Rules that apply (AGENTS.md): never push to main; no secrets in the public repo; new env vars documented in docs/ENVIRONMENT.md; deploy flow in docs/LIGHTSAIL.md stays untouched; every new service keeps the json-file 10m × 5 log bound (OPS-3).

Excerpts (verbatim; if any is not found, STOP §8).

deploy/lightsail/docker-compose.yml — end of file:

    volumes:
      ubyhost-data:
        name: ubyhost-data
      caddy-data:
        name: ubyhost-caddy-data
      caddy-config:
        name: ubyhost-caddy-config

    networks:
      web:
        name: ubyhost-web

deploy/lightsail/docker-compose.yml — the profile pattern to copy (litestream):

    litestream:
      profiles: ["litestream"]

and the pass-only-needed-vars pattern (litestream environment block; never the whole .env, which holds the secret key):

    environment:
      LITESTREAM_DB_PATH: ${UBYHOST_DB:-/data/ubyhost.db}

deploy/lightsail/.env.example — last line:

    # UBYHOST_META_GRAPH_VERSION=v26.0

## 3. Files

| Path | Action | What |
|---|---|---|
| deploy/lightsail/monitoring/config.alloy | create | Alloy pipeline: docker logs → Loki, node/cadvisor metrics → Prometheus |
| deploy/lightsail/docker-compose.yml | edit | add services alloy, cadvisor, node-exporter, profile "monitoring" |
| deploy/lightsail/.env.example | edit | GRAFANA_* variables + COMPOSE_PROFILES note |
| docs/ENVIRONMENT.md | edit | one section for the GRAFANA_* variables |
| docs/OBSERVABILITY.md | create | what ships where, privacy boundary, owner setup runbook |
| docs/context/decisions.md | edit | two decision lines, matching the file's existing format |

No other file may change.

## 4. Steps

Step 1 — create deploy/lightsail/monitoring/config.alloy with exactly this content:

    // UbyHost observability pipeline (brief 0425).
    // Logs: every compose container's stdout/stderr → Grafana Cloud Loki.
    // Metrics: node-exporter (host) + cAdvisor (containers) → Prometheus.
    // Credentials arrive as env from compose (deploy/lightsail/.env), never here.

    discovery.docker "containers" {
      host             = "unix:///var/run/docker.sock"
      refresh_interval = "60s"
    }

    loki.source.docker "containers" {
      host       = "unix:///var/run/docker.sock"
      targets    = discovery.docker.containers.targets
      forward_to = [loki.write.grafanacloud.receiver]

      relabel_rules {
        rule {
          source_labels = ["__meta_docker_container_name"]
          target_label  = "container"
        }
      }
    }

    loki.write "grafanacloud" {
      endpoint {
        url = env("GRAFANA_LOKI_URL")
        basic_auth {
          username = env("GRAFANA_LOKI_USER")
          password = env("GRAFANA_LOKI_TOKEN")
        }
      }
    }

    prometheus.scrape "node" {
      targets         = [{ "__address__" = "node-exporter:9100", "job" = "node" }]
      scrape_interval = "30s"
      forward_to      = [prometheus.remote_write.grafanacloud.receiver]
    }

    prometheus.scrape "cadvisor" {
      targets         = [{ "__address__" = "cadvisor:8080", "job" = "cadvisor" }]
      scrape_interval = "30s"
      forward_to      = [prometheus.remote_write.grafanacloud.receiver]
    }

    prometheus.remote_write "grafanacloud" {
      endpoint {
        url = env("GRAFANA_PROM_URL")
        basic_auth {
          username = env("GRAFANA_PROM_USER")
          password = env("GRAFANA_PROM_TOKEN")
        }
      }
    }

Step 2 — deploy/lightsail/docker-compose.yml: insert the three services between the end of the caddy service block and the final volumes: section (excerpt above). Exact YAML:

    # OBS-1 (brief 0425): observability stack, started only with
    # COMPOSE_PROFILES=monitoring (combine: COMPOSE_PROFILES=litestream,monitoring).
    # Ships container logs to Grafana Cloud Loki and host/container metrics to
    # Prometheus — see docs/OBSERVABILITY.md.
    alloy:
      profiles: ["monitoring"]
      # TODO(owner): pin by digest after the first green deploy (repo convention).
      image: grafana/alloy:v1.10.1
      restart: unless-stopped
      command: ["run", "/etc/alloy/config.alloy", "--server.http.listen-addr=0.0.0.0:12345"]
      # Same pattern as litestream: only the variables this service needs.
      environment:
        GRAFANA_PROM_URL: ${GRAFANA_PROM_URL:-}
        GRAFANA_PROM_USER: ${GRAFANA_PROM_USER:-}
        GRAFANA_PROM_TOKEN: ${GRAFANA_PROM_TOKEN:-}
        GRAFANA_LOKI_URL: ${GRAFANA_LOKI_URL:-}
        GRAFANA_LOKI_USER: ${GRAFANA_LOKI_USER:-}
        GRAFANA_LOKI_TOKEN: ${GRAFANA_LOKI_TOKEN:-}
      volumes:
        - ./monitoring/config.alloy:/etc/alloy/config.alloy:ro
        - /var/run/docker.sock:/var/run/docker.sock:ro
      mem_limit: ${UBYHOST_ALLOY_MEM:-512m}
      logging:
        driver: json-file
        options:
          max-size: "10m"
          max-file: "5"
      networks:
        - web

    node-exporter:
      profiles: ["monitoring"]
      # TODO(owner): pin by digest after the first green deploy.
      image: prom/node-exporter:v1.9.1
      restart: unless-stopped
      pid: host
      volumes:
        - /proc:/host/proc:ro
        - /sys:/host/sys:ro
        - /:/rootfs:ro
      command:
        - --path.procfs=/host/proc
        - --path.sysfs=/host/sys
        - --path.rootfs=/rootfs
        - --collector.filesystem.mount-points-exclude=^/(dev|proc|sys|var/lib/docker/.+)($|/)
      mem_limit: 128m
      logging:
        driver: json-file
        options:
          max-size: "10m"
          max-file: "5"
      networks:
        - web

    cadvisor:
      profiles: ["monitoring"]
      # TODO(owner): pin by digest after the first green deploy.
      image: gcr.io/cadvisor/cadvisor:v0.52.1
      restart: unless-stopped
      privileged: true
      devices:
        - /dev/kmsg:/dev/kmsg
      volumes:
        - /:/rootfs:ro
        - /var/run:/var/run:ro
        - /sys:/sys:ro
        - /var/lib/docker/:/var/lib/docker:ro
        - /dev/disk/:/dev/disk:ro
      command:
        - --docker_only=true
        - --housekeeping_interval=30s
        - --store_container_labels=false
      mem_limit: 256m
      logging:
        driver: json-file
        options:
          max-size: "10m"
          max-file: "5"
      networks:
        - web

Step 3 — deploy/lightsail/.env.example: first check for an existing key:

    grep -n "COMPOSE_PROFILES" deploy/lightsail/.env.example | head -10

If COMPOSE_PROFILES is already there, edit that one line; never add a second key. Then append after the last line (excerpt above):

    # --- Observability (brief 0425; see docs/OBSERVABILITY.md) ---
    # Grafana Cloud free tier, EU stack. Copy the Prometheus and Loki
    # URL/username/token from Grafana Cloud → Connections. Remove
    # "monitoring" from COMPOSE_PROFILES to keep the whole stack off.
    COMPOSE_PROFILES=litestream,monitoring
    GRAFANA_PROM_URL=
    GRAFANA_PROM_USER=
    GRAFANA_PROM_TOKEN=
    GRAFANA_LOKI_URL=
    GRAFANA_LOKI_USER=
    GRAFANA_LOKI_TOKEN=
    UBYHOST_ALLOY_MEM=512m

Step 4 — docs/ENVIRONMENT.md: list the sections first and match the style:

    grep -n "^## " docs/ENVIRONMENT.md | head -50

Append one section: COMPOSE_PROFILES, the six GRAFANA_* variables and UBYHOST_ALLOY_MEM, each with "what breaks if wrong": with "monitoring" in the profile and empty credentials, alloy restarts and logs auth errors (nothing else breaks; the app is untouched).

Step 5 — create docs/OBSERVABILITY.md with exactly:

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

    ## Reading it

    Queries, dashboards and alerts are documented here by brief 0427.

    ## Costs and limits

    Grafana Cloud free tier (check the current numbers on the pricing page):
    roughly 10 000 active Prometheus series and 50 GB log ingestion per month.
    This stack uses about 800–1 500 series at a 30 s interval — inside the free
    tier, $0, and no AWS credits are touched.

Step 6 — docs/context/decisions.md: read the existing line format first (grep -n "^- |^* |^## " docs/context/decisions.md | head -30) and append two lines in that format:

- Grafana Cloud free tier (EU) is the subprocessor for operational logs and metrics; logs stay PII-free per OPS-3 (owner, 2026-10-27).
- Monitoring containers grafana/alloy, gcr.io/cadvisor/cadvisor and prom/node-exporter added behind compose profile "monitoring" (owner, 2026-10-27).

## 5. Do not touch

App/ (this brief changes no application code), Dockerfile, caddy/, litestream.yml, scripts/, .github/workflows, AGENTS.md, docs/LIGHTSAIL.md. Never push, merge or deploy — that is the owner's.

## 6. Commands

    cd deploy/lightsail && COMPOSE_PROFILES=monitoring docker compose config -q

→ exit 0, no output.

    cd deploy/lightsail && COMPOSE_PROFILES=litestream,monitoring docker compose config --services 2>&1 | tail -30

→ lists alloy, cadvisor, node-exporter, ubyhost, worker, litestream, caddy.

    cd deploy/lightsail && docker compose config --services 2>&1 | tail -30

→ no alloy, cadvisor or node-exporter.

    python3 scripts/context_lint.py 2>&1 | tail -30

→ passes. (No test-map row: no App/ file changes.)

## 7. Acceptance

- [ ] compose config -q exits 0 with the profile; the three services are absent without it
- [ ] every new service has the json-file 10m × 5 logging block and a mem_limit
- [ ] config.alloy contains no literal credentials, only env() references
- [ ] git diff --stat lists only the six files in §3
- [ ] scripts/context_lint.py passes

## 8. Stop and ask

Standard template items, plus: docker compose rejects the profile syntax; ENVIRONMENT.md or decisions.md has no recognizable line format to follow; a GRAFANA_* variable name collides with an existing one.

## 9. Report

Write docs/tasks/0425-report.md (600 tokens at most), Status: review, per the template.

## Risk list (for the reviewer)

deploy/lightsail/docker-compose.yml, deploy/lightsail/monitoring/config.alloy, docs/OBSERVABILITY.md, deploy/lightsail/.env.example.

## Owner steps

1. Review the compose diff: three new services, all profile-gated.
2. Merge with scripts/merge-pr-on-green.sh.
3. Create the Grafana Cloud free stack (EU region) and copy the six credentials into deploy/lightsail/.env.
4. Keep COMPOSE_PROFILES=litestream,monitoring and run ./scripts/deploy.sh on the server.
5. Verify in Grafana → Explore: {container="ubyhost"} shows lines; up is 1 for node and cadvisor.
6. Pin the three images by digest (repo convention, see caddy and litestream) in a follow-up commit.
