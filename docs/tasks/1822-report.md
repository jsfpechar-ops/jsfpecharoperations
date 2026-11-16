# 1822 report: Docker prune and log limits

Status: review

## Files changed

- `deploy/lightsail/scripts/deploy.sh`: prune now runs `docker image prune -f` and `docker builder prune -f` (no age filter). Comment and echo updated. Never `-a`, `:previous` untouched.
- `deploy/lightsail/docker-compose.yml`: `max-file: "5"` changed to `max-file: "3"` in all 10 `logging:` blocks. Nothing else.
- `docs/LIGHTSAIL.md`: prune sentence now matches the command; one sentence on the 10 MB x 3 cap; owner journald steps added.
- `docs/tasks/1822-report.md`: this file.

Not committed or pushed (orchestrator instruction). Other working-tree changes (Caddyfiles) belong to other executors and were not touched.

## Checks

- Step 0 greps: prune line found (deploy.sh:473); `max-file: "5"` count 10; no `x-` anchor; no test references `max-file` (`grep -rn "max-file" App/tests` empty).
- `grep -cF 'max-file: "3"'` on compose: 10. `grep -cF 'max-file: "5"'`: 0.
- `bash -n deploy/lightsail/scripts/deploy.sh`: ok.
- `python3 -c "import yaml; yaml.safe_load(...)"`: `yaml ok`.
- `docker compose -f deploy/lightsail/docker-compose.yml config -q`: NOT a pass. Prints `env file .../deploy/lightsail/.env not found` (sandbox has no env file, and UBYHOST_DOMAIN/ACME_EMAIL unset). YAML parse above is the fallback.
- `shellcheck -S error deploy/lightsail/scripts/*.sh`: NOT RUN, shellcheck not installed (exit 127). CI command: `shellcheck -S error deploy/lightsail/scripts/*.sh`.
- `App/.venv/bin/python -m pytest tests/test_wp32_container_sizing.py tests/test_go_compose_mail_env.py -q --tb=short -x`: NOT RUN, `App/.venv` does not exist and system pytest is unusable here. CI command: the same line.
- `python3 scripts/context_lint.py`: last line `context lint: OK`.

## Acceptance (section 7)

- [x] `max-file: "5"` count 0; `max-file: "3"` in all 10 former places.
- [x] deploy.sh prune lines: only `image prune -f` and `builder prune -f`, no `-a`, no `system prune`.
- [x] LIGHTSAIL.md has the five journald owner steps.
- [x] Diff of §3 paths only, one commit per step: NOT done (no commits, per orchestrator).

## Deviations

- Line numbers moved: prune block at deploy.sh 469-474 (brief said 469-475); compose logging blocks at 58, 93, ... (brief said 54, 89, ...). Text matched, so edits were made by anchor.
- Brief section 9 asks to open a PR and to set `Status: review` in the brief. Not done: orchestrator said no push. The brief file itself was not edited (it is outside section 3); status is recorded in this report.

## Questions

- Open question 2 (services without `logging:`): none. All 10 services in `services:` have a logging block. `web` and `monitoring` are networks, not services.
- Open question 1 (under 1 GB after one deploy) cannot be measured from files. Owner should paste `docker system df -v | head -40` after the next deploy.

## Owner steps left

1. Merge and deploy through the normal path.
2. After the deploy, on the server: `docker system df` (RECLAIMABLE total under 1 GB) and `docker images | grep previous` (expect `ubyhost:previous` and `ubyhost-go:previous`).
3. Once per server: the five journald steps in `docs/LIGHTSAIL.md` ("cap the system journal at 100 MB").
