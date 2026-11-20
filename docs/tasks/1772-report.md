# 1772 report

Status: review

## Commits

- `4ecea8df0` 1772 step 1 — runbook I3 + Block S row
- `f5b9cea43` 1772 step 2 — remove `worker` from `deploy/lightsail/docker-compose.yml`

## Files (§3)

| Path | Action |
|---|---|
| `docs/plans/go-cutover-runbook.md` | Block S patch applied |
| `deploy/lightsail/docker-compose.yml` | worker service removed |
| `go/internal/scheduler/parity_test.go` | verified sha256 `07c88a72850b2a7f9b4931ec82e50fd547c4447ef0375d1699b4e500a381addc` (unchanged) |

## Commands (last 5 lines each)

**gofmt:** (no output)

**go vet:** (no output)

**go test parity:** `ok github.com/.../go/internal/scheduler 0.009s`

**go test ./internal/web/... ./cmd/ubyhost-web/...:** local FAIL — no Postgres on `127.0.0.1:5432`; settings/stays/cmd packages need `UBYHOST_TEST_DATABASE_URL`. CI provides the service.

**pytest test_scheduler_go_switch.py:** `8 passed, 8 skipped` — skips are pre-existing (no test DB / Go watch env).

**context_lint:** `context lint: OK`

## §7 acceptance

- [x] Parity test lists 15 kinds (hash matches sidecar; `go test ./internal/scheduler/... -run TestPlanMatchesPython` OK).
- [ ] Staging duplicate-enqueue query — owner runs after I2 + deploy (not in this executor session).
- [x] `git log --grep='^1772 step'` — steps 1–2; `git diff main --stat` only §3 paths.

## Accepted differences

None.

## Deviations

Step 2 compose change is in the PR for review; production applies per runbook “second deploy only” after one quiet week.

## Questions

None.

## Owner

1. Complete I2 (`UBYHOST_SCHEDULER=go`) and add all kinds to `UBYHOST_GO_JOB_KINDS` before Block S deploy.
2. After one quiet week, deploy step 2 compose (worker already removed in git).
3. Dashboard: no red “Background job failed” card after each step.