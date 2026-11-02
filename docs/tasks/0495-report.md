# 0495 report: cAdvisor v0.55.1 for Docker 29

Status: review

## Files changed
- `deploy/lightsail/docker-compose.yml` line 320: image now `gcr.io/cadvisor/cadvisor:v0.55.1@sha256:3de2bd5203120b866d74a9b283b2ffb8ec382fbf9dc321814700c6ea6f44ec57`. Comment, flags and mounts unchanged.
- `README.md` line 76: monitoring row `v0.52.1` changed to `v0.55.1`.
- `docs/tasks/0495-report.md` (this file).

## Commands
- `cd deploy/lightsail && docker compose --profile monitoring config -q 2>&1 | tail -5`
  - Output: two `level=warning` lines for unset `UBYHOST_DOMAIN` and `ACME_EMAIL`, and `env file .../deploy/lightsail/.env not found`. No YAML or schema error. These warnings come from the missing local `.env`, not from this change.
- `python3 scripts/context_lint.py 2>&1 | tail -30`
  - Result: `context lint: FAIL`. The failures are all in the brief, not in the edited files: `docs/tasks/0495-cadvisor-docker29.md` lacks `## 7. Acceptance`, `## 8. Stop and ask` and `## 9. Report`. The brief numbers its sections 1 to 7 with `## 7` as the owner check. The remaining WARN lines are pre-existing and unrelated.

## Section 7 (owner check)
Not run here. Owner runs after deploy: `cd /opt/ubyhost/deploy/lightsail && sudo docker logs --since 1m ubyhost-cadvisor-1 2>&1 | grep -c '^E'` should print 0.

## Deviations
- No commit made, as instructed by the orchestrator. The brief's step-level commits (`0495 step k`) were skipped.
- The digest `sha256:3de2bd52...` was taken from the brief and not re-checked against gcr.io in this session.
- Done: steps 1 to 2. Left: none.

## Owner steps left
- After merge and deploy, run the section 7 check above.
