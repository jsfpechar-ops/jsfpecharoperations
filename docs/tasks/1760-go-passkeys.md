# 1760: Go login 1: passkeys (go-webauthn)

Status: todo — scoped (final brief 2026-11-15). Executable only after its exact-diff pass: sidecars in `docs/tasks/1760-files/`, anchors and sha256 table (§2), written to the rules in [workflow](../context/workflow.md#writing-briefs-for-haiku). Until then the executor must not start it.
Depends on: 1501, owner decision made 2026-11-15: go-webauthn (v0.18.0 on Go 1.25); this PR adds the decision line to `docs/context/decisions.md` | Base commit: current tip of the working branch | Branch: task/1760-go-passkeys
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1760 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1760 step'`.

## 1. Objective

Port the passkey routes with `github.com/go-webauthn/webauthn` (needs a decision line, hard rule 4). Same credential table, same challenge handling and counters.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `App/app/routes/passkeys.py` (253 lines).

**Routes in scope (method path, Python function):**

- POST /account/passkeys/options
- POST /account/passkeys
- POST /account/passkeys/{passkey_id}/rename
- POST /account/passkeys/{passkey_id}/delete
- POST /login/passkey/options
- POST /login/passkey
- POST /account/security-prompt/seen

**Risk:** Login security.

**Parity method (same as briefs 1595 and 1580):** a golden script `App/scripts/go_go_passkeys_golden.py` seeds a throwaway database with made-up rows, renders the real FastAPI app, and writes `testdata/*_golden.json`; the Go test replays the same seed and must match byte for byte (go-first exception 1). Accepted differences are listed in the report, never silently.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/auth/passkeys.go` | create | routes |
| `go/internal/web/auth/passkeys_test.go` | create | golden parity and route tests |
| `go/internal/web/auth/testdata/passkeys_golden.json` | create | golden written by the Python script |
| `go/cmd/ubyhost-web/register_web_auth_passkeys.go` | create | registers the routes |
| `go/cmd/ubyhost-web/register_web_auth_passkeys_test.go` | create | route registration test |
| `App/scripts/go_passkeys_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_passkeys_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1760-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1760-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). The exact-diff pass fills in the `grep -cF` anchor lines for every file this brief edits and the `ls` line proving the new files do not exist yet.
1. Copy the sidecars to their repo paths and run `sha256sum -c` on the table in §2: all OK.
2. Add the golden script and its freshness test; run the script and commit the golden.
3. Add the handlers, templates and i18n keys (`App/scripts/go_host_i18n.py` writes the catalog); `gofmt -l` prints nothing.
4. Register the routes in one new `go/cmd/ubyhost-web/register_web_*.go` file (`init()` through `registerRoutes`); the routes stay dormant: nothing is added to `UBYHOST_GO_PATHS`.
5. Run the commands in §6; write the report.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/web/... ./cmd/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/web/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes, no test skipped
- `cd App && .venv/bin/python -m pytest tests/test_go_go_passkeys_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: `test_layout_lint_browser.py` green plus one 390, 768 and 1280 px screenshot per page in the report (rule 10).

## 7. Acceptance

- A passkey registered in Python logs in on Go and the reverse (cross-language fixture with a software authenticator in the test).
- Sign counter regressions are refused.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1760 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1760-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1761.
- **Rollback:** Revert the PR.

## Owner steps

Decided 2026-11-15; nothing to do.
