# 1480: SQLite retirement S12: owner runbook to archive and delete the SQLite file

Status: todo — scoped (final brief 2026-11-15). Executable only after its exact-diff pass: sidecars in `docs/tasks/1480-files/`, anchors and sha256 table (§2), written to the rules in [workflow](../context/workflow.md#writing-briefs-for-haiku). Until then the executor must not start it.
Depends on: 1476 merged plus 30 days (decision 5); date fixed by the owner decision: 2027-01-14 | Base commit: current tip of the working branch | Branch: task/1480-sqlite-archive-delete-runbook
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: C (docs/shell only; Sonnet writes; orchestrator checks file list and tests)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1480 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1480 step'`.

## 1. Objective

Write the click-by-click owner runbook for step S12 into `docs/OPERATIONS.md`: make one age-encrypted offline copy of the last SQLite file and the old snapshots, verify the copy opens with the owner's key, then delete the SQLite file and old snapshots from the server and the S3/Drive copies of them; set a calendar date 30 days later to delete the offline copy. No secret values in the file.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `docs/OPERATIONS.md` backup section, `docs/LIGHTSAIL.md`. Plan step S12 and decision 5.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/OPERATIONS.md` | edit | new section: end of the SQLite window, numbered owner steps |
| `docs/context/status.md` | edit | one line: SQLite window end date |
| `docs/tasks/1480-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1480-report.md` | create | the report (§9) |

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

- The runbook has numbered steps with exact commands and the expected output of each, a verify step before every delete, and a stop line if a check fails.
- `python3 scripts/context_lint.py` is clean.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1480 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1480-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Docs only; the owner runs it on the date.
- **Rollback:** Not applicable (deletion by the owner is final after the offline copy window).

## Owner steps

Run the new section by hand on the date the thread states. Nothing else.
