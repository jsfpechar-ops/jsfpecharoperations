# 1790: Go gate: CI test that every Python route has a Go handler

Status: todo — scoped (final brief 2026-11-15). Executable only after its exact-diff pass: sidecars in `docs/tasks/1790-files/`, anchors and sha256 table (§2), written to the rules in [workflow](../context/workflow.md#writing-briefs-for-haiku). Until then the executor must not start it.
Depends on: none (do this first) | Base commit: current tip of the working branch | Branch: task/1790-route-completeness-gate
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: B (Sonnet writes the exact-diff pass; orchestrator reads the diff of the risk-listed files)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1790 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1790 step'`.

## 1. Objective

Turn the one-off route inventory of `go-full-move-remaining.md` into a CI test: it reads every Python route (AST), asks the real Go mux, and fails when a route is missing that is not on an allow-list (`docs/plans/go-route-allowlist.txt`, one line per route with a reason). The list starts as the 244 routes and shrinks with every brief.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `docs/plans/go-full-move-remaining.md` §1 (method).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/route_inventory.py` | create | AST inventory, prints JSON |
| `go/cmd/ubyhost-web/route_inventory_test.go` | create | asks `newMux` |
| `docs/plans/go-route-allowlist.txt` | create | routes allowed to be missing, with reason |
| `docs/tasks/1790-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1790-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root): for every file in §3 the exact-diff pass writes a `grep -cF` anchor line and its expected count; anything else: STOP (§8).
1. Apply the change to the files of §3, one step and one commit per file group.
2. Run the commands of §6; fix only what the brief names.
3. Write the report (§9).

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `cd go && go test ./cmd/ubyhost-web/... -run RouteInventory -count=1 2>&1 | tail -30` passes

## 7. Acceptance

- Remove one route from the list in a scratch commit: the test fails naming it; put it back: green.
- The count printed equals 341 Python routes (±new ones) and the Go hits.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1790 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1790-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** CI only.
- **Rollback:** Revert the PR.

## Owner steps

None.
