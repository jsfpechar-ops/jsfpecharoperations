# 1477: SQLite retirement S13: docs say PostgreSQL only

Status: todo — scoped (final brief 2026-11-15). Executable only after its exact-diff pass: sidecars in `docs/tasks/1477-files/`, anchors and sha256 table (§2), written to the rules in [workflow](../context/workflow.md#writing-briefs-for-haiku). Until then the executor must not start it.
Depends on: 1476 merged | Base commit: current tip of the working branch | Branch: task/1477-docs-postgresql-only
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: C (docs/shell only; Sonnet writes; orchestrator checks file list and tests)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1477 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1477 step'`.

## 1. Objective

Update the 38 docs that name SQLite as a runtime: `ENVIRONMENT` (`UBYHOST_DB` removed from the production section), `LIGHTSAIL` (13 mentions), `OPERATIONS` backup section, `SECURITY` (4), `rules` (4). SQLite stays described only as the Python suite's test database (decision 4) until brief 1479.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `docs/ENVIRONMENT.md`, `docs/LIGHTSAIL.md`, `docs/OPERATIONS.md`, `docs/SECURITY.md`, `docs/context/rules.md`. Plan step S13. Find them with `grep -n -i sqlite <file> | head -40`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/ENVIRONMENT.md` | edit | one section: `UBYHOST_DATABASE_URL` required in production |
| `docs/LIGHTSAIL.md` | edit | backup and restore are PostgreSQL (`pg_dump`, WAL-G) |
| `docs/OPERATIONS.md` | edit | backup-and-restore section |
| `docs/SECURITY.md` | edit | four SQLite mentions |
| `docs/context/rules.md` | edit | database rule: PostgreSQL-portable SQL stays; SQLite only for tests |
| `docs/tasks/1477-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1477-report.md` | create | the report (§9) |

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

- `grep -c -i sqlite` per edited file is listed in the report with each remaining mention explained (test database, history).
- `python3 scripts/context_lint.py` is clean; no link broken.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1477 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1477-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Merge with 1476. Docs only.
- **Rollback:** Revert the PR.

## Owner steps

None.
