# 1479: SQLite retirement S14 (lane X3): delete the SQLite runtime together with `App/`

Status: todo — scoped (final brief 2026-11-15). Executable only after its exact-diff pass: sidecars in `docs/tasks/1479-files/`, anchors and sha256 table (§2), written to the rules in [workflow](../context/workflow.md#writing-briefs-for-haiku). Until then the executor must not start it.
Depends on: Go brief 1782 (X2: Caddy sends everything to Go, `ubyhost` and `worker` leave compose) merged and one quiet week in production; 1477; 1478 | Base commit: current tip of the working branch | Branch: task/1479-delete-sqlite-runtime
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: B (Sonnet writes the exact-diff pass; orchestrator reads the diff of the risk-listed files)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1479 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1479 step'`.

## 1. Objective

Delete `App/` (SQLite connections, `adapt_sql` translation, `App/app/migrations/` 0002-0045, transfer and encrypt scripts, `sqlite_only` tests, golden scripts) after moving the parity fixtures to `go/testdata`. CI runs Go only on a PostgreSQL service. Docs drop the last SQLite mention.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** Whole `App/`, `.github/workflows/ci.yml`, `Dockerfile`, `requirements*.txt`, `go/**/testdata` (fixture move). Plan step S14 and go-full-move lane X3.

**Risk:** Runs alone: touches everything. Do not run beside any other brief.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/**/testdata/**` | move | golden fixtures that today come from `App/scripts/*_golden.py` |
| `App/**` | delete | the Python application |
| `.github/workflows/ci.yml` | edit | Go jobs only |
| `Dockerfile, requirements.txt` | delete | Python image inputs |
| `docs/**` | edit | remove Python-only guidance; rules, architecture, glossary |
| `docs/tasks/1479-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1479-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root): for every file in §3 the exact-diff pass writes a `grep -cF` anchor line and its expected count; anything else: STOP (§8).
1. Apply the change to the files of §3, one step and one commit per file group.
2. Run the commands of §6; fix only what the brief names.
3. Write the report (§9).

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `cd go && go test ./... -count=1 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean (the lint itself moves to Go or is deleted in this brief)

## 7. Acceptance

- `cd go && go test ./... -count=1 2>&1 | tail -30` passes with the moved fixtures.
- `grep -rn -i sqlite . --include=* -l | grep -v 'docs/archive\|docs/tasks\|\.git/' | tail` prints nothing but history notes.
- A fresh clone builds the image and `docker compose up` on staging passes `/healthz` and the smoke script.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1479 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1479-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Single owner-approved deploy on a quiet day; the Python containers are already gone from compose (1782).
- **Rollback:** Revert the PR. Because `App/` returns from git, a rollback to Python is possible only while the images from before 1782 still exist; keep the last Python image tag for 30 days.

## Owner steps

1. Approve the deletion in this thread (it removes the last Python code).
2. Keep the last Python image tag and the offline SQLite copy for 30 days.
3. After the deploy run `scripts/smoke-remote.sh` and open three pages.
