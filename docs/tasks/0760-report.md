# 0760 report

Status: review

## Files changed

- `deploy/lightsail/docker-compose.yml`: `ubyhost-go` gets `env_file: .env`, `UBYHOST_DATA_DIR: /data`, `ubyhost-data:/data:ro`; comment updated.
- `deploy/lightsail/scripts/deploy.sh`: before "Starting stack", rebuilds `ubyhost-go` when listed; on failure prints `Go image build failed.` and exits 1.
- `go/internal/jobs/heartbeat.go` (new): `Ping(ctx, url, job)`; empty URL = no request; 5 s client; failure logs `heartbeat ping failed` with job only.
- `go/internal/jobs/heartbeat_test.go` (new): pinged once, empty URL no request, failing server no panic.
- `go/cmd/ubyhost-web/main.go`: `submit` and `ical` handlers ping on nil error (`UBYHOST_HEARTBEAT_URL`, `UBYHOST_HEARTBEAT_ICAL_URL`); return values unchanged.
- `go/internal/jobs/queue.go`: `jobLevels` (submit = critical, default warning) used in UPDATE and INSERT; `jobNames` adds submit ("automatic filing") and push ("urgent alerts"), from `App/app/host_i18n.py` English block.
- `go/internal/jobs/queue_test.go`: `TestRaiseFailedSubmitIsCritical` (DB test, skips without `UBYHOST_TEST_DATABASE_URL`).

## Checks

- `cd go && go vet ./...`: no output (pass).
- `go test ./internal/jobs/ ./cmd/...`: `ok` for both packages (DB tests skipped, no test DB URL).
- `gofmt -l` on changed Go packages: clean.
- `bash -n deploy/lightsail/scripts/deploy.sh`: exit 0.
- `docker compose --env-file .env.example config` with `COMPOSE_PROFILES=go`: exit 0. A temporary empty `deploy/lightsail/.env` was needed (service `env_file: .env`); it was removed afterwards. Rendered go service shows `UBYHOST_DATA_DIR: /data` and the `ubyhost-data` mount on `/data`.
- `python3 scripts/context_lint.py`: FAIL, only on the brief itself: `docs/tasks/0760-go-cutover-prereqs.md` lacks `## 7. Acceptance`, `## 8. Stop and ask` and `## 9. Report`. The report file error is resolved by this file.

## Deviations

- Brief refers to §6, §7, §8 that do not exist in it (it has §1 to §4). Followed the step list in §1 and the checks in §3.
- Single commit at the end (brief message), not per-step commits, as requested. Brief file left uncommitted.
- Not pushed. No PR opened.
- Heartbeat ping does not check HTTP status (matches Python, which only logs transport failures).

## Questions

- Add `## 7`, `## 8` and `## 9` to the brief so the lint passes.

## Owner steps left

- Review and merge via `scripts/merge-pr-on-green.sh` (after push, which was not done here).
- Run a real `docker compose build ubyhost-go` on the server, and set `UBYHOST_HEARTBEAT_URL` / `UBYHOST_HEARTBEAT_ICAL_URL` in `.env` if they are not set yet.
