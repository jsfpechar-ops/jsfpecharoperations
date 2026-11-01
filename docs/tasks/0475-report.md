# 0475 report: Go G1b container (executor: Haiku 5.5)

Status: blocked. Steps 1 to 3 done. Stopped at step 4 (question below). Steps 5 and 6 not started.

## Files changed
- `go/Dockerfile` (new, step 1), commit 0475 step 1
- `deploy/lightsail/docker-compose.yml` (service `ubyhost-go` after `worker`, profile `go`, step 2), commit 0475 step 2
- `deploy/lightsail/scripts/deploy.sh` (Go block after `Health (internal):`, step 3), commit 0475 step 3
- `docs/tasks/0475-go-g1b-container.md` (Status set to blocked)
- `docs/tasks/0475-report.md` (this file)

## Command tails
- `docker build -f go/Dockerfile -t ubyhost-go:test . | tail -5`:
  `ERROR: failed to connect to the docker API at unix:///var/run/docker.sock ... no such file or directory`. The daemon is not running here, so the image was not built. CI must build it.
- `docker compose -f deploy/lightsail/docker-compose.yml --env-file deploy/lightsail/.env config --quiet`: exit 0 with a temporary copy of `.env.example` (removed afterwards). With no profile, `ubyhost-go` is absent from the config, as intended.
- `bash -n deploy/lightsail/scripts/deploy.sh`: no output (syntax OK).
- `python3 scripts/context_lint.py | tail -3`:
  `WARN 15 commit(s) touched App/ after the last status.md update...` / `next free: task 0476 | migration 0034` / `context lint: OK`.

## Steps
- [x] 1 go/Dockerfile (build not run: no daemon)
- [x] 2 compose service, profile `go`
- [x] 3 deploy.sh block (never exits non-zero by design)
- [ ] 4 ci.yml docker job step: NOT APPLIED (see Questions)
- [ ] 5 dependabot.yml entry
- [ ] 6 docs/LIGHTSAIL.md line

## Deviations
Done: steps 1 to 3. Left: steps 4 to 6.

## Questions
Step 4 command as written: `docker run --rm ubyhost-go:ci 2>&1 | grep -q UBYHOST_DATABASE_URL`.
`go/cmd/ubyhost-web/main.go` line 126 logs `UBYHOST_DATABASE_URL is required` and returns 1, so `docker run` exits 1. GitHub Actions runs `run:` steps with `bash -eo pipefail`, so the pipeline returns 1 and the CI step fails even when the binary behaves correctly. Proposed fix (needs owner or orchestrator OK): capture the output and check the exit code explicitly, e.g.
`out=$(docker run --rm ubyhost-go:ci 2>&1) && { echo "expected failure"; exit 1; }; echo "$out" | grep -q UBYHOST_DATABASE_URL`
Confirm this form, or give a different one, and I will apply step 4 to 6.

## Owner steps left
None yet. The brief's step 6 owner line is still to be added to `docs/LIGHTSAIL.md`.
