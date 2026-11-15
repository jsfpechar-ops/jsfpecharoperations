# 1781: Go retire 2: `/webhooks/stripe` stays off `UBYHOST_GO_PATHS` (runbook fix)

Status: todo — scoped (final brief 2026-11-15). Executable only after its exact-diff pass: sidecars in `docs/tasks/1781-files/`, anchors and sha256 table (§2), written to the rules in [workflow](../context/workflow.md#writing-briefs-for-haiku). Until then the executor must not start it.
Depends on: 1350, 1554 | Base commit: current tip of the working branch | Branch: task/1781-stripe-webhook-path-decision
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: C (docs/shell only; Sonnet writes; orchestrator checks file list and tests)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1781 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1781 step'`.

## 1. Objective

Take `/webhooks/stripe` out of the documented `UBYHOST_GO_PATHS` and write the one safe cutover sequence: booking events forwarded via `UBYHOST_PY_WEBHOOK_URL`, then the endpoint moves only with 1554 after Stripe leaves test mode.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** Runbook §5; `go/internal/payments/booking_webhook.go`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/plans/go-cutover-runbook.md` | edit | remove the path, add the sequence |
| `docs/plans/go-cutover-env-commands.md` | edit | remove it from the example value |
| `docs/tasks/1781-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1781-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root): for every file in §3 the exact-diff pass writes a `grep -cF` anchor line and its expected count; anything else: STOP (§8).
1. Apply the change to the files of §3, one step and one commit per file group.
2. Run the commands of §6; fix only what the brief names.
3. Write the report (§9).

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean

## 7. Acceptance

- `grep -n webhooks/stripe docs/plans/go-cutover-*.md | tail -10` shows only the new sequence and the 'keep on Python' text.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1781 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1781-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Owner removes the entry from the live `UBYHOST_GO_PATHS` (55 entries now, 54 after).
- **Rollback:** Add it back.

## Owner steps

1. On the server open `.env`, remove `/webhooks/stripe` from `UBYHOST_GO_PATHS` (paths only).
2. `caddy reload`.
3. Send a Stripe test event; check it arrives in Python logs.
