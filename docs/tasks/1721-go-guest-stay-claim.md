# 1721: Go guest 2: stay overview, claim landing and confirm, demo preview

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
Depends on: 1720 | Base commit: current tip of the working branch | Branch: task/1721-go-guest-stay-claim
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1721 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1721 step'`.

## 1. Objective

Port `stay_overview`, `claim_landing`, `claim_confirm`, `demo_pin_preview`. The claim state machine uses `go/internal/statemachine` and `go/internal/ubyport/claim.go` (already ported).

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `guest.py` 1455-1694; brief 1109/1135 state machine rules.

**Routes in scope (method path, Python function):**

- GET /l/{token}/demo/{reservation_id}
- GET /l/{token}/{reservation_id} (stay_overview)
- GET /l/{token}/{reservation_id}/claim
- POST /l/{token}/{reservation_id}/claim/confirm

**Risk:** Guest pages are public and carry real guest data (passports, signatures). Rule 2 applies line by line; the owner's rule is that guest registration goes last.

**Parity method (same as briefs 1595 and 1580):** a golden script `App/scripts/go_stay_claim_golden.py` seeds a throwaway database with made-up rows, renders the real FastAPI app, and writes `testdata/*_golden.json`; the Go test replays the same seed and must match byte for byte (go-first exception 1). Accepted differences are listed in the report, never silently.

**All implementation code is pre-written.** Sidecars: `docs/tasks/1721-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action |
|---|---|---|
| `2aa46a13a8e872ddd99b86b4738c463c9093471890c0491c6fcd9faeb4f6d13b` | `App/scripts/go_stay_claim_golden.py` | create |
| `d6c9f7e52a76aefe8ca7018cfa40d3191de7ef0070e29678cddbf922453338d8` | `App/tests/test_go_stay_claim_golden.py` | create |
| `65b51185c471549a2ac2be3eb96a0c23a286989a62256170a7986220ff55bb3d` | `go/cmd/ubyhost-web/register_web_guest_stay_claim.go` | create |
| `3dde31853ce145711030ae0dec7c2f6bce5c9b81a943061a34c5d16463b0a1b4` | `go/cmd/ubyhost-web/register_web_guest_stay_claim_test.go` | create |
| `89e79501f3efc5bc33c465a1366245f4c345ee470a8f360e9b83ba00f4afd9d5` | `go/internal/web/guest/stay_claim.go` | create |
| `851eac8410c1d84dc40d736c18cbf926f59cbb32a2bd2f7814646bca9f24fa2c` | `go/internal/web/guest/stay_claim_test.go` | create |
| `0a0a3c9e2da9918cf4ba6859aced6df27055104ab4f0518e47c53d75a528f63a` | `go/internal/web/guest/testdata/stay_claim_golden.json` | create |

Full manifest: `docs/tasks/1721-files/MANIFEST.sha256`.

**Routing note:** Go `ServeMux` cannot register both `GET /l/{token}/demo/{reservation_id}` and `GET /l/{token}/{reservation_id}/claim` without ambiguity. The sidecar uses one `GET /l/{token}/{rest...}` dispatcher (`dispatchGET`) and keeps `POST /l/{token}/{reservation_id}/claim/confirm` explicit. The registration test expects those patterns.

**Verified by the brief writer:** sidecars dry-run on current `main` with step 1 copy — `sha256sum -c docs/tasks/1721-files/MANIFEST.sha256` all OK; `gofmt -l` empty on copied paths; `go vet ./internal/web/guest/...` silent; `go test ./internal/web/guest/... -count=1` OK (confirm race needs `UBYHOST_TEST_DATABASE_URL`); `go test ./cmd/ubyhost-web/... -run TestGuestStayClaimRoutesRegistered` OK; `pytest tests/test_go_stay_claim_golden.py` OK when `App/.venv` exists. Full guest templates, PIN gate, and `ubyhost_claim` cookie ship with brief **1720**; executor waits for 1720 on the same branch before browser/390px gate.



## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/guest/stay_claim.go` | create | stay and claim |
| `go/internal/web/guest/stay_claim_test.go` | create | golden parity and route tests |
| `go/internal/web/guest/testdata/stay_claim_golden.json` | create | golden written by the Python script |
| `go/cmd/ubyhost-web/register_web_guest_stay_claim.go` | create | registers the routes |
| `go/cmd/ubyhost-web/register_web_guest_stay_claim_test.go` | create | route registration test |
| `App/scripts/go_stay_claim_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_stay_claim_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1721-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1721-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). Each `grep -cF` / `ls` anchor prints `1` (see `docs/tasks/1721-files/ANCHORS.txt`):
   - `grep -cF 'def demo_pin_preview(token: str, reservation_id: int, request: Request):' App/app/routes/guest.py | tail -1`
   - `grep -cF 'async def claim_confirm(token: str, reservation_id: int, request: Request):' App/app/routes/guest.py | tail -1`
   - `grep -cF 'def confirm(reservation, secret: str) -> bool:' App/app/claim.py | tail -1`
   - `ls go/internal/web/guest/stay_claim.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls App/scripts/go_stay_claim_golden.py 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls go/cmd/ubyhost-web/register_web_guest_stay_claim.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `find docs/tasks/1721-files -name '*.txt' ! -name 'ANCHORS.txt' | wc -l | tail -1` prints `7`.
1. Copy sidecars and verify (one call, repo root). Never retype or edit them:

   ```bash
   S=docs/tasks/1721-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'ANCHORS.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   Expected: 7 lines ending `: OK`. Commit `1721 step 1`.
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
- `cd App && .venv/bin/python -m pytest tests/test_go_stay_claim_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: `test_layout_lint_browser.py` green plus one 390, 768 and 1280 px screenshot per page in the report (rule 10).

## 7. Acceptance

- A lost claim race gives Python's answer; a claimed stay cannot be claimed twice (test with two concurrent requests).
- The entry-code block placeholder from brief 1666 stays a no-op until 1661 is live.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1721 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1721-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1728.
- **Rollback:** Revert the PR.

## Owner steps

None.
