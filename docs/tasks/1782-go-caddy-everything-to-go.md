# 1782: Go retire 3 (X2): Caddy sends everything to Go; `ubyhost` and `worker` leave compose

Status: todo — scoped (final brief 2026-11-15). Executable only after its exact-diff pass: sidecars in `docs/tasks/1782-files/`, anchors and sha256 table (§2), written to the rules in [workflow](../context/workflow.md#writing-briefs-for-haiku). Until then the executor must not start it.
Depends on: every wave done, 1772, one quiet week | Base commit: current tip of the working branch | Branch: task/1782-go-caddy-everything-to-go
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1782 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1782 step'`.

## 1. Objective

Final switch: Caddy default upstream becomes `ubyhost-go`, `UBYHOST_GO_PATHS` is deleted, the `ubyhost` and `worker` services and the Python image leave compose. Keep the last Python image tag 30 days.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `deploy/lightsail/Caddyfile`, `docker-compose.yml`, `deploy.sh`.

**Risk:** Everything. Runs alone.

## 3. Files

| Path | Action | What |
|---|---|---|
| `deploy/lightsail/Caddyfile` | edit | default upstream Go |
| `deploy/lightsail/docker-compose.yml` | edit | remove `ubyhost`, `worker` |
| `docs/LIGHTSAIL.md` | edit | services list |
| `docs/tasks/1782-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1782-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root): for every file in §3 the exact-diff pass writes a `grep -cF` anchor line and its expected count; anything else: STOP (§8).
1. Apply the change to the files of §3, one step and one commit per file group.
2. Run the commands of §6; fix only what the brief names.
3. Write the report (§9).

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `bash deploy/lightsail/scripts/caddy-validate.sh 2>&1 | tail -20` passes

## 7. Acceptance

- `caddy-validate.sh` passes; staging smoke script passes on every page of the completeness tests.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1782 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1782-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** One owner-approved deploy, quiet day.
- **Rollback:** Re-add the services from git and the saved image tag; Caddy default back to `ubyhost`.

## Owner steps

Approve in thread; run smoke-remote.sh after.
