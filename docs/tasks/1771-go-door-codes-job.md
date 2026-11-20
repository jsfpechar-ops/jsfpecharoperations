# 1771: Go jobs 2: port the `door_codes` job (and cleaning codes)

Status: review — exact-diff sidecars ready (2026-11-20).
Depends on: 1706, 1707, 1573, TTLock live acceptance | Base commit: current tip of the working branch | Branch: task/1771-go-door-codes-job
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1771 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1771 step'`.

## 1. Objective

Port the `door_codes` job kind of `door_codes.py` (1,699 lines): issue, revoke, reissue with the state machine, host notices (1168), cleaning-event codes. Register it behind `UBYHOST_GO_JOB_KINDS`.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `App/app/door_codes.py`, `ttlock.py`, briefs 1107, 1116, 1141, 1149, 1155, 1156, 1160, 1168; plan `ttlock-door-codes.md`.

**Risk:** Door access for real guests.

**All implementation code is pre-written on `main`.** Sidecars: `docs/tasks/1771-files/<repo path>.txt`. Step 1 copies them. Sample checksums (73 paths in manifest):

| sha256 | file | action |
|---|---|---|
| `27d6128e8915cd857a300cbdf7234e8bea45878b9b79b0cda8cf8b637c0b93b5` | `go/cmd/ubyhost-web/register_job_door_codes.go` | create |
| `4aed53ea40af92c42920b498198537d9ed26f5f5c9dc5ca0c8f28a41647bd515` | `go/cmd/ubyhost-web/door_codes_wire.go` | create |
| `63c923315179a7d01a087fcccd4769e8ec5d5385f7698f1ce646e2173f742c34` | `App/scripts/go_door_codes_golden.py` | create |

Full manifest: `docs/tasks/1771-files/MANIFEST.sha256`. Verified: `go test ./internal/doorcodes/... ./cmd/ubyhost-web/ -run DoorCodes -count=1` OK; golden wrapper pytest OK when copied.

**Parity:** `go_door_codes_golden.py` runs mailnotify goldens; state machines covered in `go/internal/doorcodes/*_test.go`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/doorcodes/**` | create | package + cleaning + wire (manifest) |
| `go/cmd/ubyhost-web/door_codes_wire.go` | create | job wiring |
| `go/cmd/ubyhost-web/register_job_door_codes*.go` | create | register + tests |
| `App/scripts/go_door_codes_golden.py` | create | runs mailnotify goldens |
| `App/tests/test_go_go_door_codes_job_golden.py` | create | freshness test |
| `docs/tasks/1771-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1771-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks: `docs/tasks/1771-files/ANCHORS.txt` (`wc -l` prints 73).
1. Copy sidecars (1770-style loop); `sha256sum -c docs/tasks/1771-files/MANIFEST.sha256` all OK after copy. Commit `1771 step 1`.
2. Run `go_door_codes_golden.py` when JSON stale. Commit `1771 step 2` if needed.
3. Run §6 commands; write the report.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/doorcodes/... ./cmd/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/doorcodes/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes, no test skipped
- `cd App && .venv/bin/python -m pytest tests/test_go_go_door_codes_job_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
## 7. Acceptance

- Every state transition of the Python table has a Go test; ambiguous deletes, lost races and re-cancel behave as briefs 1149/1155/1155b describe.
- API call budget guard identical (30,000 a month).
- `git log --oneline --grep='^1771 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1771-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Per the TTLock plan section 12; then add `door_codes` to both job variables.
- **Rollback:** Remove it from both variables; Python worker resumes.

## Owner steps

Section 12 acceptance test of the TTLock plan with one real lock.
