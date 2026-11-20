# 1772: Go jobs 3: Block S, Go enqueues every job kind (Python worker stops)

Status: review — exact-diff sidecars ready (2026-11-20).
Depends on: 1450-1452 (done), 1770, 1771, J-jobs for retention and stay_fee_mail decided | Base commit: current tip of the working branch | Branch: task/1772-go-scheduler-switch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1772 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1772 step'`.

## 1. Objective

Switch `UBYHOST_SCHEDULER=go` so Go's scheduler enqueues all 15 kinds at the intervals and cron times of `scheduler.py`; the Python `worker` container stops. Includes the compose change that removes `worker` only after one quiet week.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `App/app/scheduler.py` (872 lines), `App/app/worker.py`, `go/internal/scheduler`, `register_scheduler.go`.

**Risk:** A missed job is a missed filing deadline or invoice.

**Scheduler parity is on `main` (brief 1450).** Sidecars hold parity test verification plus Block S patches.

| sha256 | file | action |
|---|---|---|
| `07c88a72850b2a7f9b4931ec82e50fd547c4447ef0375d1699b4e500a381addc` | `go/internal/scheduler/parity_test.go` | verify |
| `7b3cd8919104319ac491cca006f0541173b705331d8fc0bfd822612897fcd199` | `deploy/lightsail/docker-compose.yml.worker-removal.patch` | step 2 only |
| `86d18f99aaa2dc9bdb7b747651d944d2dae8fd12a7dae8ccea05731620f671f0` | `docs/plans/go-cutover-runbook.md.block-s.patch` | step 1 |

Manifest: `docs/tasks/1772-files/MANIFEST.sha256`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/scheduler/parity_test.go` | verify | matches Python on `main` |
| `deploy/lightsail/docker-compose.yml` | edit | worker-removal patch in step 2 only |
| `docs/plans/go-cutover-runbook.md` | edit | Block S patch (I3 + row S) |
| `docs/tasks/1772-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1772-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks: `docs/tasks/1772-files/ANCHORS.txt`.
1. Apply runbook Block S patch. Commit `1772 step 1`.
2. Apply compose worker-removal patch only when owner approves second deploy. Commit `1772 step 2`.
3. Verify parity_test sidecar hash; run §6; report.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/web/... ./cmd/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/web/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes, no test skipped
- `cd App && .venv/bin/python -m pytest tests/test_scheduler_go_switch.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
## 7. Acceptance

- The parity test lists all 15 kinds and fails on any difference in schedule.
- With the switch on in staging, no kind is enqueued twice in one window (query in the report).
- `git log --oneline --grep='^1772 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1772-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Two steps: (1) set the variable and stop `worker` in staging for a day; (2) production the same, wait a week, then remove the service.
- **Rollback:** Set `UBYHOST_SCHEDULER=python` and start `worker`.

## Owner steps

Follow the Block S steps in the runbook; check the dashboard for a red 'Background job failed' card after each step.
