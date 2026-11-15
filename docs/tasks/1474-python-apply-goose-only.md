# 1474: SQLite retirement S6: Python's PostgreSQL schema apply uses the goose files only

Status: todo — scoped (final brief 2026-11-15). Executable only after its exact-diff pass: sidecars in `docs/tasks/1474-files/`, anchors and sha256 table (§2), written to the rules in [workflow](../context/workflow.md#writing-briefs-for-haiku). Until then the executor must not start it.
Depends on: 1472 and 1473 merged (done: reports exist), 1471 (00017), owner step S4 done (production schema dump diffed clean by the S3 check) | Base commit: current tip of the working branch | Branch: task/1474-python-apply-goose-only
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1474 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1474 step'`.

## 1. Objective

Make `apply_postgresql_schema` and `bootstrap_empty_postgresql_schema` in `App/app/db.py` run only the goose files `App/migrations_pg/00001`..`N` on PostgreSQL. The translated SQLite path (`_postgres_schema_ddl`, `db_postgres.render_ddl`, `ADDED_COLUMNS` replay) is no longer run on PostgreSQL. SQLite as the Python test database is untouched (decision 4).

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `App/app/db.py` (`apply_postgresql_schema` ~1809, `bootstrap_empty_postgresql_schema` ~1844, `validate_postgres_schema`), `App/app/db_postgres.py`, `App/scripts/pg_schema.py`, `App/tests/conftest.py`, `App/tests/test_goose_equivalence.py` (1472). Plan [sqlite-retirement](../plans/sqlite-retirement.md) step S6.

**Risk:** A goose file that depends on a column the translated path used to create would fail on an empty database; 1472's diff is the guard and must run on the final commit.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/db.py` | edit | PostgreSQL apply and bootstrap run goose files only; keep the SQLite code path |
| `App/app/db_postgres.py` | edit | stop calling `render_ddl` for the apply path (function stays for `adapt_sql`) |
| `App/scripts/pg_schema.py` | edit | `apply` runs goose only; `check` unchanged |
| `App/tests/conftest.py` | edit | PostgreSQL test databases are built from goose files |
| `App/tests/test_pg_apply_goose_only.py` | create | empty database gets 00001..N and the same dump as 1472's database B; a database that already has every row runs nothing |
| `docs/tasks/1474-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1474-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root): for every file in §3 the exact-diff pass writes a `grep -cF` anchor line and its expected count; anything else: STOP (§8).
1. Apply the change to the files of §3, one step and one commit per file group.
2. Run the commands of §6; fix only what the brief names.
3. Write the report (§9).

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `cd App && .venv/bin/python -m pytest tests/test_pg_apply_goose_only.py tests/test_goose_equivalence.py tests/test_sqlite_migrations_frozen.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean

## 7. Acceptance

- On an empty PostgreSQL database `pg_schema.py apply` creates the schema from goose files alone and `test_goose_equivalence.py` (1472) still passes with database A built the new way.
- On a database that already has every goose row (production's state) `apply` reports zero pending files and changes nothing (row counts of `schema_migrations` and `goose_db_version` equal before and after).
- `test-postgres-full` (CI) is green on the final commit; the default SQLite suite is unchanged.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1474 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1474-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Merge; green merges auto-deploy. Production already has every goose row, so the deploy-time apply is a no-op. `UBYHOST_SCHEMA_APPLY=go` is already live, so Python's apply is not on the production path at all.
- **Rollback:** Revert the PR. No data change anywhere.

## Owner steps

None. (Prerequisite already on the owner list: S4 production schema dump handed over.)
