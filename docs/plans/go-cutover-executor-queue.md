# Go cutover — executor queue

Written 2026-11-19; copied into the repo 2026-11-20 (was Project Context only). Plans: [go-sqlite-final](go-sqlite-final.md), [python-retirement-plan](python-retirement-plan.md), [go-cutover-runbook](go-cutover-runbook.md) §5–6, [go-full-move-remaining](go-full-move-remaining.md).

## Runnable now (no `docs/tasks/NNNN-files/` sidecar)

| Brief | Why |
|---|---|
| **[1793](../tasks/1793-cleaning-code-run-at-once.md)** | Status: exact-diff pass done §10; cleaning TTLock kick + visible delete |
| **[0852](../tasks/0852-fix-725-regressions.md)** | Orchestrator note: ready for executor (regression fixes) |

Most **17xx** briefs (including **1730**, **1770–1772**) say: *Executable only after exact-diff pass* and need `docs/tasks/NNNN-files/` — **do not start** until a Sonnet/Opus pass lands those sidecars ([workflow](../context/workflow.md#writing-briefs-for-haiku)).

---

## Production snapshot (refresh in [status](../context/status.md))

2026-11-19 baseline: Stays **list** on Go; stay detail/submit mostly Python unless path wave; jobs **mail** + **door_codes** Python; Payments hidden on prod.

---

## Executor order (after Stays 1855–1858 list land)

One Haiku brief at a time; respect [go-sqlite-final](go-sqlite-final.md) file-conflict chains.

### Gate and retirement prep (Phase 0)

| Order | Briefs | Notes |
|---|---|---|
| 1 | **[1790](../tasks/1790-route-completeness-gate.md)** | CI allow-list of Python-only routes |
| 2 | **[1780](../tasks/1780-go-ops-scripts-subcommands.md)**, **[1781](../tasks/1781-stripe-webhook-path-decision.md)** | Backups/deploy off Python |
| 3 | **1474, 1475** | SQLite schema authority |
| 4 | **1750**, **1775** | Utility routes; invoice mail builder |

### Stays / submissions (1730 overlap)

**1730** still lists GET `/reservations` list — **superseded** by Stays list port. After exact-diff: only `GET /submissions`, `GET /submissions/{id}`, `GET /reservations/{id}`.

Chain: **1730** → **1731** → **1732**; guest edit **1733–1737**; **1751** dashboard after 1730.

### Cleaning gaps

**1793** (ready) → **1570–1573** (need exact-diff sidecars).

### Property, filing, guest, jobs

See full table in [go-sqlite-final](go-sqlite-final.md) and [python-retirement-plan](python-retirement-plan.md) §2–3 (gates G1–G9).

**Executor rule:** No widening `UBYHOST_GO_PATHS` in PRs; owner path waves only. No new deps without [decisions](../context/decisions.md).