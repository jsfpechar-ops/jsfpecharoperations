# 0760 brief: make the Go service ready to switch on in production

Status: done (code on main and live in production, server on #928, 2026-11-12; closed in bulk by the orchestrator)
Executor: Haiku 5.5, alone, on branch `claude/project-thread-9so0lg` in `/home/claude/jsfpecharoperations` (checked out; do not switch branches, do not push). Commit at the end with message `0760: Go cutover prerequisites`.

## 1. Objective

The Go container (`ubyhost-go`) is merged but has never run in production. Four gaps stop it from taking over jobs safely. Close them, nothing else.

1. **Env and secret.** In `deploy/lightsail/docker-compose.yml`, service `ubyhost-go` gets only four env vars, so Go has no `UBYHOST_SECRET_KEY`, data keys, VAPID, heartbeat or Stripe secret key. Give it the same `env_file: .env` as `ubyhost`/`worker`, add `UBYHOST_DATA_DIR: /data` to its `environment`, and mount `ubyhost-data:/data:ro` (read-only: Go never writes there; `secure.loadSecret` reads `/data/secret_key`). Keep the four existing `environment` lines (they keep the safe defaults when `.env` lacks them). Update the comment above the service (it now runs jobs; HTTP only via `UBYHOST_GO_PATHS`).
2. **Stale image.** `deploy/lightsail/scripts/deploy.sh` pulls only the Python image from GHCR, so `ubyhost-go:local` would be built once and never rebuilt. Right before `echo "==> Starting stack"`, add: when `docker compose config --services` lists `ubyhost-go` (that is, the `go` profile is on), run `docker compose build ubyhost-go`; on failure print `Go image build failed.` to stderr and `exit 1` (this is before `up`, so the running stack is untouched). Keep the post-deploy Go health block report-only.
3. **Heartbeats.** Python pings `UBYHOST_HEARTBEAT_URL` after every successful `submit` run and `UBYHOST_HEARTBEAT_ICAL_URL` after every successful `ical` run (`App/app/scheduler.py` lines ~150-182: `requests.get(url, timeout=5)`, a failure is only logged, empty URL = no ping). Go does not, so switching those kinds to Go would fire the external dead-man alert. In `go/cmd/ubyhost-web/main.go` `goHandlers`, after a nil error from the `submit` and `ical` handlers, GET the URL from the env (`os.Getenv`) with a 5 s timeout client; log `heartbeat ping failed` with the job name only (never the URL) on error; never change the handler's return value. Put the ping helper in `go/internal/jobs` (e.g. `jobs.Ping(ctx, url, job string)`), with a unit test using `httptest.Server` (pinged once; empty URL makes no request; a failing server does not return an error).
4. **Alert parity.** `go/internal/jobs/queue.go` `RaiseFailed` always uses level `warning` and knows only three job names. Python (`App/app/scheduler.py` `_JOB_LEVELS`, lines 46-63) uses `critical` for `submit`. Add a `jobLevels` map (`submit` -> `critical`, everything else `warning`) and use it in both the UPDATE and the INSERT. Add English names to `jobNames` for `submit` and `push`, copied exactly from the English host i18n values `notification.job_name.submit` / `notification.job_name.push` (find them with `grep -rn '"notification.job_name' App/app | head`). Extend `queue_test.go` with one test that `RaiseFailed(ctx, pool, "submit")` writes level `critical`.

## 2. Context

See section 1; each gap names its file and lines.

## 3. Files

`deploy/lightsail/docker-compose.yml`, `deploy/lightsail/scripts/deploy.sh`, `go/cmd/ubyhost-web/main.go`, `go/internal/jobs/`.

## 4. Steps

Do gaps 1-4 of section 1 in order.

## 5. Do not touch

No change to Python app code, Caddyfiles, `UBYHOST_GO_PATHS`, job kinds, or any handler logic. No new dependency.

## 6. Commands

- `cd go && go vet ./... 2>&1 | tail -5 && go test ./internal/jobs/ ./cmd/... 2>&1 | tail -15` (DB tests skip without `UBYHOST_TEST_DATABASE_URL`; that is fine, CI runs them).
- `cd deploy/lightsail && UBYHOST_DOMAIN=x ACME_EMAIL=x COMPOSE_PROFILES=go docker compose --env-file .env.example config >/dev/null 2>&1; echo $?` if docker is available, else `bash -n scripts/deploy.sh`.
- From the repo root: `python3 scripts/context_lint.py | tail -5`.

## 7. Acceptance

All commands in section 6 pass.

## 8. Stop and ask

If a gap needs a Python change or a new dependency.

## 9. Report

Write `docs/tasks/0760-report.md`: files changed, the check output tails, anything you could not do.
