# 0475 report: Go G1b container (executor: Haiku 5.5)

Status: review. All steps 1 to 6 done. Nothing pushed.

## Files changed
- `go/Dockerfile` (new, step 1)
- `deploy/lightsail/docker-compose.yml` (service `ubyhost-go`, profile `go`, step 2)
- `deploy/lightsail/scripts/deploy.sh` (Go block after `Health (internal):`, step 3)
- `.github/workflows/ci.yml` (one step after `Build image`, step 4)
- `.github/dependabot.yml` (docker entry for `/go`, step 5)
- `docs/LIGHTSAIL.md` (optional-service line and owner step under Architecture, step 6)
- `docs/tasks/0475-go-g1b-container.md` (Status review)
- `docs/tasks/0475-report.md` (this file)

## Command tails
- `docker build -f go/Dockerfile -t ubyhost-go:test . | tail -5`:
  `ERROR: failed to connect to the docker API at unix:///var/run/docker.sock ... no such file or directory`. No daemon here, so the image was not built. CI builds it (step 4).
- `docker compose -f deploy/lightsail/docker-compose.yml --env-file deploy/lightsail/.env config --quiet`: exit 0 (temporary `.env` copied from `.env.example`, then removed). Without the profile, `ubyhost-go` is absent, as intended.
- `bash -n deploy/lightsail/scripts/deploy.sh`: no output.
- `python3 -c "import yaml; yaml.safe_load(...)"` on `.github/workflows/ci.yml` and `.github/dependabot.yml`: `yaml ok` for both.
- `python3 scripts/context_lint.py | tail -3`:
  `WARN 15 commit(s) touched App/ after the last status.md update...` / `next free: task 0476 | migration 0034` / `context lint: OK`.

## Steps
- [x] 1 go/Dockerfile
- [x] 2 compose service, profile `go`
- [x] 3 deploy.sh block (never exits non-zero by design)
- [x] 4 ci.yml step: `docker build -f go/Dockerfile -t ubyhost-go:ci .`, then `out=$(docker run --rm ubyhost-go:ci 2>&1) && { echo "expected failure"; exit 1; }; echo "$out" | grep -q UBYHOST_DATABASE_URL` (form approved by the coordinator)
- [x] 5 dependabot.yml docker entry, `directory: /go`
- [x] 6 docs/LIGHTSAIL.md

## Deviations
- Step 6: the brief says "the services list". LIGHTSAIL.md has no services list. The closest is the Architecture block, so the service line sits under it. The owner step is in the same place. Move it if the owner wants it elsewhere.
- Step 4 is the coordinator's form, not the brief's pipe form (the pipe fails under `pipefail`).
- The Docker build could not be run locally (no daemon). CI is the first real build of `go/Dockerfile`, and the digests are untested until it runs.

## Questions
None.

## Owner steps left
- Nothing to deploy yet. To turn the Go service on later: add `go` to `COMPOSE_PROFILES` in `.env` (for example `COMPOSE_PROFILES=go`), then deploy. It serves nothing until G2.
