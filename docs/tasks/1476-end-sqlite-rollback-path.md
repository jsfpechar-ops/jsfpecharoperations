# 1476: SQLite retirement S11: remove the SQLite rollback scripts

Status: todo — scoped (final brief 2026-11-15). Executable only after its exact-diff pass: sidecars in `docs/tasks/1476-files/`, anchors and sha256 table (§2), written to the rules in [workflow](../context/workflow.md#writing-briefs-for-haiku). Until then the executor must not start it.
Depends on: S8 live (`UBYHOST_SCHEMA_APPLY=go`, done 2026-11-14), the section 6 proofs of the plan all recorded (brief 1473 checklist), owner decision 3 date given, 1474 | Base commit: current tip of the working branch | Branch: task/1476-end-sqlite-rollback-path
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1476 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1476 step'`.

## 1. Objective

Remove the SQLite rollback path from the shell tooling: delete `pg-cutover.sh`, the SQLite branches of `restore.sh`, `deploy.sh` (backup and `integrity_check`), `setup-server.sh` (`sqlite3` install) and the `sqlite3` preflight check. The server keeps its archived SQLite copy until step S12 (owner, 30 days later). Python keeps SQLite only as its test database.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `deploy/lightsail/scripts/{pg-cutover,restore,deploy,setup-server,preflight}.sh`, `.github/workflows/deploy-preflight.yml`, `deploy/lightsail/README.md`. Plan step S11 and section 6.

**Risk:** Data loss at the end of the rollback window. Do not start before every proof exists; this is why the brief is blocked on the owner's date.

## 3. Files

| Path | Action | What |
|---|---|---|
| `deploy/lightsail/scripts/pg-cutover.sh` | delete | rollback to SQLite ends |
| `deploy/lightsail/scripts/restore.sh` | edit | PostgreSQL restore only (`pg-restore.sh` stays the tool) |
| `deploy/lightsail/scripts/deploy.sh` | edit | drop SQLite backup and integrity branch |
| `deploy/lightsail/scripts/setup-server.sh` | edit | no `sqlite3` package |
| `deploy/lightsail/scripts/preflight.sh` | edit | no `sqlite3` check |
| `.github/workflows/deploy-preflight.yml` | edit | no `sqlite3` step |
| `deploy/lightsail/README.md` | edit | say PostgreSQL only |
| `docs/tasks/1476-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1476-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root): for every file in §3 the exact-diff pass writes a `grep -cF` anchor line and its expected count; anything else: STOP (§8).
1. Apply the change to the files of §3, one step and one commit per file group.
2. Run the commands of §6; fix only what the brief names.
3. Write the report (§9).

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `bash -n deploy/lightsail/scripts/*.sh 2>&1 | tail -20` prints nothing
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean

## 7. Acceptance

- `grep -rn -i sqlite deploy/ .github/workflows/ | tail -20` lists only comments that say the path was removed (each justified in the report).
- `bash -n` passes on every edited script; `shellcheck` clean if installed.
- The report contains the four proofs from the plan's section 6 (a decrypt test of one `.age` backup, `pg-restore.sh` into staging with matching row counts, the Drive and S3 copies current, the offline age-encrypted SQLite copy) with dates, no secret values.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1476 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1476-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Merge only after the owner has written the cutover date in the thread. The deploy runs the new `deploy.sh`; watch one deploy end to end.
- **Rollback:** Revert the PR; the archived SQLite file is still on the server until S12, so `pg-cutover.sh` can be restored from git. After S12 there is no rollback to SQLite, by decision.

## Owner steps

1. Confirm the four proofs in the checklist from brief 1473 are ticked with dates.
2. Write the cutover date in this thread (decision 3).
3. After merge, run one deploy and check `docker compose ps` shows everything healthy.
