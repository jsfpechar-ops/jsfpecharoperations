# 1773: Go jobs 4: enable `retention` and `stay_fee_mail` (owner checklist)

Status: todo — scoped (final brief 2026-11-15). Executable only after its exact-diff pass: sidecars in `docs/tasks/1773-files/`, anchors and sha256 table (§2), written to the rules in [workflow](../context/workflow.md#writing-briefs-for-haiku). Until then the executor must not start it.
Depends on: three matching retention dry-run mornings, stay-fee wave 10 steps 1-3 | Base commit: current tip of the working branch | Branch: task/1773-go-jobs-retention-staymail-enable
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: C (docs/shell only; Sonnet writes; orchestrator checks file list and tests)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1773 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1773 step'`.

## 1. Objective

Write the exact owner checklist for runbook section 5: how to compare three dry-run counts, then add the two kinds to the variables, with the rollback line. Docs only.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** Runbook §5, `go-cutover-env-commands.md`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/plans/go-cutover-runbook.md` | edit | section 5 steps with commands |
| `docs/plans/go-cutover-env-commands.md` | edit | exact variable lines |
| `docs/tasks/1773-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1773-report.md` | create | the report (§9) |

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

- Every step has a command and the expected output; a stop line if counts differ.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1773 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1773-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Owner runs it.
- **Rollback:** Variable lines removed.

## Owner steps

None.
