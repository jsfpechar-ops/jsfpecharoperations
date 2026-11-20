# 1706: Go smart locks 1: TTLock client in Go

Status: todo — ready for executor (exact-diff pass 2026-11-20). `go/internal/ttlock` is already on `main` (commit 027ed0cc1); sidecars snapshot that tree for step 1 verify-only on a clean worktree.
Depends on: none (TTLock plan section 11/12 for live use) | Base commit: current tip of the working branch | Branch: task/1706-go-ttlock-client
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1706 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1706 step'`.

## 1. Objective

Write `go/internal/ttlock`: OAuth token exchange and refresh, lock list, passcode create/delete, with the 30,000-calls-a-month budget guard and secret handling of `ttlock.py` (741 lines). No route uses it yet.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `App/app/ttlock.py`, `docs/plans/ttlock-door-codes.md` sections 3, 7, 8; `docs/TTLOCK.md`.

**Risk:** Door access for real guests; never test against a real lock in CI.

**Parity:** `go/internal/ttlock/client_test.go` and `budget_test.go` exercise a fake TTLock server (`httptest`); no route golden for this brief.

**All implementation code is pre-written on `main`.** Sidecars: `docs/tasks/1706-files/<repo path>.txt`. Step 1 copies them on a branch that lacks the package (or runs `sha256sum -c` only when the tree already matches).

| sha256 | file | action |
|---|---|---|
| `77cafb37fe0eec46191cfadaa46a92a1e4d227f08d93ec0d02a0d81d25f7208d` | `go/internal/ttlock/api.go` | keep |
| `15284fe400698bb232e38fb6f14b438b0b27d2da0f1e7e4883f5906ef299c952` | `go/internal/ttlock/budget.go` | keep |
| `7f155fb45de6d85f3d7ab5e98d79893cf5456a4904c816eaa3520d371dbea426` | `go/internal/ttlock/budget_test.go` | keep |
| `b022ea289528cb008e2de5dd70fd3c4c5fc41bd2fe44ba1f3d25521915078836` | `go/internal/ttlock/client.go` | keep |
| `812fc403250fa71d2bde32f5963ecfcb297925c967721df567a1b618e646f2de` | `go/internal/ttlock/client_test.go` | keep |
| `29a1faf1d7d3a9f3695995bc6e8ba9406649c5acf0bcdf23ab01021c15d78eb5` | `go/internal/ttlock/tokens.go` | keep |

Full manifest: `docs/tasks/1706-files/MANIFEST.sha256`.

**Verified by the brief writer:** `sha256sum -c docs/tasks/1706-files/MANIFEST.sha256` OK against live `main`; `cd go && go test ./internal/ttlock/... -count=1` OK; `go vet ./internal/ttlock/...` silent.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/ttlock/api.go` | keep | TTLock API (create account, list locks, codes) |
| `go/internal/ttlock/budget.go` | keep | monthly call budget |
| `go/internal/ttlock/budget_test.go` | keep | budget tests |
| `go/internal/ttlock/client.go` | keep | HTTP client |
| `go/internal/ttlock/client_test.go` | keep | tests against an `httptest` server, no real account |
| `go/internal/ttlock/tokens.go` | keep | token refresh |
| `docs/tasks/1706-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1706-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). See `docs/tasks/1706-files/ANCHORS.txt` (`grep -cF` lines return `1`; `find … | wc -l` returns `6`).
1. If any §3 path is missing, copy sidecars to repo paths; then `sha256sum -c docs/tasks/1706-files/MANIFEST.sha256`: all OK.
2. Run the commands in §6; write the report.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/ttlock/... ./cmd/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/ttlock/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes, no test skipped
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: `test_layout_lint_browser.py` green plus one 390, 768 and 1280 px screenshot per page in the report (rule 10).

## 7. Acceptance

- Every call in `ttlock.py` has a Go function with the same URL, form fields and error mapping, proved by tests against a fake server.
- Tokens are encrypted at rest through the existing `secure` package; none logged.
- No new outbound host beyond the one `ttlock.py` already calls.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1706 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1706-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** No rollout: the client is dead code until 1707 and 1771.
- **Rollback:** Revert the PR.

## Owner steps

None.
