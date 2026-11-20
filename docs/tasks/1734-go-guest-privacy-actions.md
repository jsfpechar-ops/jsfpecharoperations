# 1734: Go stays 5: restrict, verify identity, passport photo, reveal identity

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
Depends on: 1733 | Base commit: current tip of the working branch | Branch: task/1734-go-guest-privacy-actions
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1734 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1734 step'`.

## 1. Objective

Port `guest_restrict/unrestrict`, `guest_verify_identity`, `guest_passport_photo` (decrypted image read) and `guest_reveal_identity` (audited reveal).

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `admin.py` 4797-4953.

**Routes in scope (method path, Python function):**

- POST /guests/{guest_id}/restrict and /unrestrict
- POST /guests/{guest_id}/verify-identity
- GET /guests/{guest_id}/passport-photo
- POST /guests/{guest_id}/reveal-identity

**Risk:** Identity documents. Rule 2.

**Parity method (same as briefs 1595 and 1580):** a golden script `App/scripts/go_guest_privacy_golden.py` seeds a throwaway database with made-up rows, renders the real FastAPI app, and writes `testdata/*_golden.json`; the Go test replays the same seed and must match byte for byte (go-first exception 1). Accepted differences are listed in the report, never silently.

**All implementation code is pre-written.** Sidecars: `docs/tasks/1734-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action |
|---|---|---|
| `943e97508f4c657eaf863bca090dff73d9c39b015fbea6612213f3ea359b32d9` | `App/scripts/go_guest_privacy_golden.py` | create |
| `f9eb3796bedc4f3f0999938b2242727a3b2b2bada790d8e3dcf07054c3d86177` | `App/tests/test_go_guest_privacy_golden.py` | create |
| `fdee0c63d56be8a633406385bda08781005212d48bcbf4a28937dc425e75513c` | `go/cmd/ubyhost-web/register_web_stays_guest_privacy.go` | create |
| `e0e2e1e17e3fb25c6ac7b787e6c08c282ac9fc67c9f8e3532df570aec3066cb1` | `go/cmd/ubyhost-web/register_web_stays_guest_privacy_test.go` | create |
| `63f55b60469a867b3ff494fc9e9a3f684acaaab11207ac66321678d7ce97e914` | `go/internal/web/stays/guest_privacy.go` | create |
| `71e8e5426567724400456063527151fe751d325286ce0413833d9e037fa076cb` | `go/internal/web/stays/guest_privacy_test.go` | create |
| `3879d22afff63ea29f4bef693845bb3c06d39a7548cb056ce7b9e5fb858644e7` | `go/internal/web/stays/testdata/guest_privacy_golden.json` | create |

Full manifest: `docs/tasks/1734-files/MANIFEST.sha256`.

**Verified by the brief writer:** sidecars dry-run — `sha256sum -c docs/tasks/1734-files/MANIFEST.sha256` all OK; `go vet ./internal/web/stays/...` silent on copied privacy/lifecycle with `guest_edit` on `main`; golden pytest when `App/.venv` exists.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/stays/guest_privacy.go` | create | privacy actions |
| `go/internal/web/stays/guest_privacy_test.go` | create | golden parity and route tests |
| `go/internal/web/stays/testdata/guest_privacy_golden.json` | create | golden written by the Python script |
| `go/cmd/ubyhost-web/register_web_stays_guest_privacy.go` | create | registers the routes |
| `go/cmd/ubyhost-web/register_web_stays_guest_privacy_test.go` | create | route registration test |
| `App/scripts/go_guest_privacy_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_guest_privacy_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1734-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1734-report.md` | create | the report (§9) |

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
- `cd App && .venv/bin/python -m pytest tests/test_go_guest_privacy_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: `test_layout_lint_browser.py` green plus one 390, 768 and 1280 px screenshot per page in the report (rule 10).

## 7. Acceptance

- Every reveal and photo read writes the same audit row; response headers forbid caching (`no-store`); an unauthorised user gets Python's 404.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1734 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1734-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1737.
- **Rollback:** Revert the PR.

## Owner steps

None.
