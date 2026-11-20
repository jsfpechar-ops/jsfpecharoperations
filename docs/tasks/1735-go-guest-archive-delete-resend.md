# 1735: Go stays 6: archive, unarchive, delete, resend guest link

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
Depends on: 1734 | Base commit: current tip of the working branch | Branch: task/1735-go-guest-archive-delete-resend
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1735 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1735 step'`.

## 1. Objective

Port `guest_archive/unarchive`, `guest_delete` (hard delete with retention rules) and `guest_resend` (mail through `go/internal/mail`).

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `admin.py` 4953-5090.

**Routes in scope (method path, Python function):**

- POST /guests/{guest_id}/archive and /unarchive
- POST /guests/{guest_id}/delete
- POST /guests/{guest_id}/resend

**Risk:** Permanent deletion.

**Parity method (same as briefs 1595 and 1580):** a golden script `App/scripts/go_guest_lifecycle_golden.py` seeds a throwaway database with made-up rows, renders the real FastAPI app, and writes `testdata/*_golden.json`; the Go test replays the same seed and must match byte for byte (go-first exception 1). Accepted differences are listed in the report, never silently.

**All implementation code is pre-written.** Sidecars: `docs/tasks/1735-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action |
|---|---|---|
| `31350f36cc03abd54d8a44379c812e248351d9dbd57cd7b5259f8b90dceec723` | `App/scripts/go_guest_lifecycle_golden.py` | create |
| `b80c2e12e2b25395c03e634ed4d2d8922dbe12061ff515adf4b3af43c054b9b9` | `App/tests/test_go_guest_lifecycle_golden.py` | create |
| `d866f392a61896a25938d3fa4100ce719feceb702434cf3c0334d89ca2b45506` | `go/cmd/ubyhost-web/register_web_stays_guest_lifecycle.go` | create |
| `faeb7bd45d7f842317910f1fea98425de68d771c952233ca8703ca219a2c03c8` | `go/cmd/ubyhost-web/register_web_stays_guest_lifecycle_test.go` | create |
| `123a992c7197b2362a3522bba4274856751b7babcff58f0e90ef82684b471f92` | `go/internal/web/stays/guest_lifecycle.go` | create |
| `df5579ae77db472c7e3f0c8de366203d354dc30ced3051465fc2959f41e0d253` | `go/internal/web/stays/guest_lifecycle_test.go` | create |
| `e57e34ca55e87b02213edd631de92920a94ac63fa1663e46531df8d4e98dc680` | `go/internal/web/stays/testdata/guest_lifecycle_golden.json` | create |

Full manifest: `docs/tasks/1735-files/MANIFEST.sha256`.

**Verified by the brief writer:** sidecars dry-run — `sha256sum -c docs/tasks/1735-files/MANIFEST.sha256` all OK; `go vet ./internal/web/stays/...` silent on copied privacy/lifecycle with `guest_edit` on `main`; golden pytest when `App/.venv` exists.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/stays/guest_lifecycle.go` | create | lifecycle POSTs |
| `go/internal/web/stays/guest_lifecycle_test.go` | create | golden parity and route tests |
| `go/internal/web/stays/testdata/guest_lifecycle_golden.json` | create | golden written by the Python script |
| `go/cmd/ubyhost-web/register_web_stays_guest_lifecycle.go` | create | registers the routes |
| `go/cmd/ubyhost-web/register_web_stays_guest_lifecycle_test.go` | create | route registration test |
| `App/scripts/go_guest_lifecycle_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_guest_lifecycle_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1735-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1735-report.md` | create | the report (§9) |

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
- `cd App && .venv/bin/python -m pytest tests/test_go_guest_lifecycle_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: `test_layout_lint_browser.py` green plus one 390, 768 and 1280 px screenshot per page in the report (rule 10).

## 7. Acceptance

- Delete removes the same rows and files as Python and nothing else (photo files included); resend queues the same mail row.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1735 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1735-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1737.
- **Rollback:** Revert the PR.

## Owner steps

None.
