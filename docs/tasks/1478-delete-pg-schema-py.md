# 1478: SQLite retirement S9: delete `pg_schema.py` and Python's schema apply

Status: todo — scoped (final brief 2026-11-15). Executable only after its exact-diff pass: sidecars in `docs/tasks/1478-files/`, anchors and sha256 table (§2), written to the rules in [workflow](../context/workflow.md#writing-briefs-for-haiku). Until then the executor must not start it.
Depends on: 1474, S8 live and two goose migrations applied by Go on production (owner check) | Base commit: current tip of the working branch | Branch: task/1478-delete-pg-schema-py
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: B (Sonnet writes the exact-diff pass; orchestrator reads the diff of the risk-listed files)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1478 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1478 step'`.

## 1. Objective

Delete `App/scripts/pg_schema.py`, `apply_postgresql_schema` and the CI `test-postgres` steps that call it; Go (`ubyhost-web migrate`) is the only schema applier. Update every document and script that tells the owner to run `pg_schema.py apply` (grep first).

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `App/scripts/pg_schema.py`, `App/app/db.py`, `.github/workflows/ci.yml`, `deploy/lightsail/scripts/deploy.sh`, `docs/` mentions. Plan step S9 / lane D1 end.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/pg_schema.py` | delete | Python apply tool |
| `App/app/db.py` | edit | remove `apply_postgresql_schema` and its helpers; keep `validate_postgres_schema` |
| `.github/workflows/ci.yml` | edit | CI builds the database with `ubyhost-web migrate apply --init` |
| `deploy/lightsail/scripts/deploy.sh` | edit | only the Go apply remains |
| `docs/tasks/1478-files/mentions.txt` | create | the grep list of docs that named `pg_schema.py`, each edited in this PR |
| `docs/tasks/1478-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1478-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root): for every file in §3 the exact-diff pass writes a `grep -cF` anchor line and its expected count; anything else: STOP (§8).
1. Apply the change to the files of §3, one step and one commit per file group.
2. Run the commands of §6; fix only what the brief names.
3. Write the report (§9).

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `cd App && .venv/bin/python -m pytest tests/test_goose_equivalence.py tests/test_sqlite_migrations_frozen.py -q --tb=short -x 2>&1 | tail -30` passes

## 7. Acceptance

- `grep -rn pg_schema App deploy .github docs --include=* | grep -v 'docs/tasks\|docs/archive' | tail -20` prints nothing.
- CI `test-postgres` and `test-postgres-full` green on the final commit (they now depend on 1475).
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1478 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1478-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Merge; green merges auto-deploy. The deploy already uses the Go apply.
- **Rollback:** Revert the PR; `UBYHOST_SCHEMA_APPLY=python` is still readable in `deploy.sh` only if the revert is merged first.

## Owner steps

None.
