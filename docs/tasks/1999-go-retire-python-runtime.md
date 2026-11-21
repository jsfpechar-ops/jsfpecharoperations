# 1999: Retire Python web and worker after full Go parity

Status: todo — **1782** merged on `main` (2026-11-21, PR #1153); `go_parity_check.py --all` is 342/342. Executor stays blocked until §2 items (notably **1772** quiet week) are ticked.
Depends on: **1782**, **1772**, **1780**, all §1A route briefs merged dormant; waves in [go-cutover-runbook](../plans/go-cutover-runbook.md) | Branch: task/1999-go-retire-python-runtime
Executor: **Composer 2.5** (Josef override) | Tier: A (deploy + delete; Josef sign-off)

## 1. Objective

Remove the production Python **`ubyhost`** HTTP process and **`worker`** scheduler from deploy, and stop shipping the Python app image for runtime. Keep `App/` only for CI: golden scripts (go-first exception 1), browser tests, and parity until Josef deletes them in a later brief.

This brief is the **owner checklist** that ties **1772** (scheduler), **1782** (Caddy default → Go, compose trim), and **1780** (ops scripts) into one “Python is gone” milestone.

## 2. Context

Preconditions (all must be true before §4 executor):

Use `python3 scripts/go_parity_check.py --all` and the orchestrator gap inventory (§1 routes, jobs, side flows):

1. **No HTTP** still Python-only (`go_parity_check.py --all` → zero unhandled).
2. **No filing/mail/demo** POSTs still Python-only (**1741**, **1429**, **1597** on `main`).
3. **Guest/booking/host** gaps closed (**1720–1726**, **1629**, **1544**, **1710** split, **1750**, **1805**).
4. **`UBYHOST_PY_WEBHOOK_URL`** empty or removed — Stripe fully on Go (**1781**).
5. **`UBYHOST_GO_JOB_KINDS`** lists every kind the Python worker still ran; Go scheduler green one quiet week (**1772**).
6. **`deploy.sh` / backup / restore** use Go subcommands only (**1780**).
7. Staging soak: **1782** CHECKLIST + `caddy-validate.sh` + `smoke-remote.sh` + owner browser pass.
8. **main** `go` CI green; production filing smoke (mock UbyPort) on staging.

**Rollout:** Draft PR until Josef marks ready; **no** `scripts/start-merge-guard.sh` on the 1999 PR until then (same class as **1782** / **1153**).

## 3. Files

| Path | Action |
|---|---|
| `deploy/lightsail/docker-compose.yml` | via **1782** sidecars (remove `ubyhost`, `worker`) |
| `deploy/lightsail/caddy/*` | via **1782** |
| `docs/LIGHTSAIL.md`, `docs/OPERATIONS.md` | Python runtime removed from operator docs |
| `App/Dockerfile` / render defs | mark deprecated or remove from deploy pipeline (owner decision line) |
| `docs/context/decisions.md` | `[1999]` retirement decision |

Executor copies **1782-files**; does not invent compose edits. **1999** is the merge gate brief Josef marks ready.

## 4. Steps

0. Tick every precondition in §2 in the PR body.
1. Merge **1772** → staging soak → merge **1782** when Josef marks ready.
2. Run **1999** executor (Composer 2.5): docs sync, decision line, verify no production reference to Python upstream.
3. Owner: production deploy with rollback SHA noted.

## 5. Do not touch

`UBYHOST_GO_PATHS` wave flags until **1782**; UbyPort submission code paths without **1741** review.

## 6. Commands

```bash
python3 scripts/go_parity_check.py --all 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -10
curl -sS https://YOUR_DOMAIN/healthz
bash deploy/lightsail/scripts/smoke-remote.sh 2>&1 | tail -30
```

## 7. Acceptance

- Preconditions in §2 ticked in the PR body before executor starts.
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean after any doc edits.

## 8. Stop and ask

Stop when a precondition is false, compose would change outside **1782** sidecars, or production health fails after deploy — revert and ask Josef.

## 9. Report

`docs/tasks/1999-report.md`: precondition table, staging/production command tails, rollback SHA.