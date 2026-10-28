# 0425 report — monitoring pipeline (Alloy + cAdvisor + node-exporter)

Status: review
Branch: task/0425-monitoring-pipeline (PR #549)

## Files changed (the six §3 files, `git diff --stat`)

- `deploy/lightsail/monitoring/config.alloy` — new, verbatim from brief.
- `deploy/lightsail/docker-compose.yml` — alloy, node-exporter, cadvisor inserted before top-level `volumes:`; all profile "monitoring", each with json-file 10m×5 logging + mem_limit.
- `deploy/lightsail/.env.example` — observability block appended (six GRAFANA_* + UBYHOST_ALLOY_MEM + COMPOSE_PROFILES).
- `docs/ENVIRONMENT.md` — new "Observability" section with what-breaks-if-wrong table.
- `docs/OBSERVABILITY.md` — new, verbatim from brief.
- `docs/context/decisions.md` — the two brief lines appended verbatim.

Also restored `docs/tasks/0425-report.md` (belongs to the other 0425 task, PR #542; an earlier stray commit on this branch had replaced it — reverted here).

## Commands (last lines)

- `COMPOSE_PROFILES=monitoring docker compose config -q` → **not run: no docker binary on this machine** (`command not found: docker`), same for the two `config --services` checks. Compose YAML structure was reviewed by inspection (services at 4-space indent, inserted directly before top-level `volumes:`).
- `python3 scripts/context_lint.py` → `next free: task 0428 | migration 0027` / `context lint: OK`.

## §7 Acceptance

- [x] compose config with profile / absent without — verified live on the production deploy (2026-10-28): with `COMPOSE_PROFILES=litestream,monitoring` the three containers start (`docker ps` shows ubyhost-alloy-1, ubyhost-node-exporter-1, ubyhost-cadvisor-1); without the profile they don't. Data confirmed in Grafana Cloud after token/URL fixes. (The earlier indent bug — services nested under `caddy` — was caught in review and fixed pre-merge.)
- [x] every new service has json-file 10m × 5 logging block and a mem_limit
- [x] config.alloy has no literal credentials, only env() references
- [x] `git diff --stat` lists only the six §3 files (plus the report files)
- [x] `scripts/context_lint.py` passes

## Deviations

Done: steps 1–6 and the lint. Left: the three docker compose checks (no docker locally).

Review follow-ups fixed on this branch:

- docker-compose.yml: the three monitoring services were indented 4 spaces (nested as keys of `caddy`); de-indented to 2 spaces so they are real top-level services.
- config.alloy: `loki.source.docker` does not support `relabel_rules`; replaced with a `loki.relabel` stage that sets `container` from `__meta_docker_container_name`, stripping the leading `/` so `{container="ubyhost"}` matches.

## Questions

- `.env.example` had COMPOSE_PROFILES only as a commented example (`# COMPOSE_PROFILES=staging`, line 29); treated as not an active key, so the appended block adds the single active key. Flag if the commented line should have been edited instead.

## Owner steps left

Per the brief: review the compose diff; merge with `scripts/merge-pr-on-green.sh`; create the Grafana Cloud EU free stack and fill the six GRAFANA_* values in `deploy/lightsail/.env`; deploy; verify `{container="ubyhost"}` in Explore; pin the three images by digest in a follow-up.

Status 2026-10-28: all owner steps done. Deployed, verified live (logs in Loki, node/cadvisor `up == 1` in Prometheus). Images pinned by digest in this follow-up (manifest-list digests, same convention as litestream/caddy).
