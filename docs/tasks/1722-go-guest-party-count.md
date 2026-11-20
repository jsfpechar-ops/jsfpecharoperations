# 1722: Go guest 3: party size, head count, add another person

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
Depends on: 1721 | Base commit: current tip of the working branch | Branch: task/1722-go-guest-party-count
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1722 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1722 step'`.

## 1. Objective

Port `set_party_size`, `lead_change_count`, `add_another_person` (guest slots on a reservation; the head-count lead H1 is behind `UBYHOST_HEADCOUNT_LEAD_LIVE`, keep the flag).

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `guest.py` 1694-2081; `go/internal/headcount`.

**Routes in scope (method path, Python function):**

- POST /l/{token}/{reservation_id}/party
- POST /l/{token}/{reservation_id}/count
- POST /l/{token}/{reservation_id}/another

**Risk:** Guest pages are public and carry real guest data (passports, signatures). Rule 2 applies line by line; the owner's rule is that guest registration goes last.

**Parity method (same as briefs 1595 and 1580):** `App/scripts/go_party_golden.py` seeds a throwaway database with made-up rows, renders the real FastAPI app, and writes `go/internal/web/guest/testdata/party_golden.json`; the Go test replays the same seed on PostgreSQL when `UBYHOST_TEST_DATABASE_URL` is set (go-first exception 1). Accepted differences belong in the report, never silently.

**All implementation code is pre-written.** Sidecars: `docs/tasks/1722-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action |
|---|---|---|
| `5c0e163e2b94c352792382694c923007c2af8c3a0b9d6e0fd4e15689d2449227` | `App/scripts/go_party_golden.py` | create |
| `38026a8872ca69887606224ba558ae7e1dc9a69c2c8e0fdc71f85ac44f08f87f` | `App/tests/test_go_party_golden.py` | create |
| `a1f18ae7031084555d7b1f5c55ee0772345d5d37ade732a43851cc2815019607` | `go/cmd/ubyhost-web/register_web_guest_party.go` | create |
| `f2db2dcb26c45d3682f3ad91ca7cf9da7f8555804696dba8ea4efb3244dd0b44` | `go/cmd/ubyhost-web/register_web_guest_party_test.go` | create |
| `0e2f523898816850e8de399b71661c6d8871a67a3ec66a72e52ccbfb8621e7e9` | `go/internal/web/guest/party.go` | create |
| `0fe300297233763a1548b0b0965b604d925ffdf7d67d8606a44423b149f911c1` | `go/internal/web/guest/party_test.go` | create |
| `15203627a81aae2b7c52a4772f99c4b0433f7a0721971a4d250e366baa7e917a` | `go/internal/web/guest/testdata/party_golden.json` | create |

Full manifest: `docs/tasks/1722-files/MANIFEST.sha256`.

**Verified by the brief writer:** sidecars dry-run on current `main` with step 1 copy — `sha256sum -c docs/tasks/1722-files/MANIFEST.sha256` all OK; `gofmt -l` empty on copied paths; `go vet ./internal/web/guest/... ./cmd/ubyhost-web/register_web_guest_party.go` silent; `go test ./internal/web/guest/... -count=1` OK; `go test ./cmd/ubyhost-web/... -run TestGuestPartyRoutesRegistered` OK; `pytest tests/test_go_party_golden.py` OK when `App/.venv` exists.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/guest/party.go` | create | party routes |
| `go/internal/web/guest/party_test.go` | create | golden parity and route tests |
| `go/internal/web/guest/testdata/party_golden.json` | create | golden written by the Python script |
| `go/cmd/ubyhost-web/register_web_guest_party.go` | create | registers the routes |
| `go/cmd/ubyhost-web/register_web_guest_party_test.go` | create | route registration test |
| `App/scripts/go_party_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_party_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1722-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1722-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). Each `grep -cF` / `ls` anchor prints `1` (see `docs/tasks/1722-files/ANCHORS.txt`):
   - `grep -cF '@router.post("/l/{token}/{reservation_id}/party")' App/app/routes/guest.py | tail -1`
   - `grep -cF '@router.post("/l/{token}/{reservation_id}/count")' App/app/routes/guest.py | tail -1`
   - `grep -cF '@router.post("/l/{token}/{reservation_id}/another")' App/app/routes/guest.py | tail -1`
   - `grep -cF 'def change_by_lead(' App/app/headcount.py | tail -1`
   - `grep -cF 'func Expected(override, declared, reduced *int64) *int64' go/internal/headcount/headcount.go | tail -1`
   - `ls go/internal/web/guest/party.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls App/scripts/go_party_golden.py 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls go/cmd/ubyhost-web/register_web_guest_party.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `find docs/tasks/1722-files -name '*.txt' ! -name 'ANCHORS.txt' | wc -l | tail -1` prints `7`.

1. Copy sidecars and verify (one call, repo root). Never retype or edit them:

   ```bash
   S=docs/tasks/1722-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'ANCHORS.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   Expected: 7 lines ending `: OK`. Commit `1722 step 1`.
2. Run `App/scripts/go_party_golden.py` and commit if `party_golden.json` changes; commit `1722 step 2`.
3. Wire any remaining guest-shell hooks from briefs 1720–1721 only if this step already copied them; `gofmt -l` prints nothing; commit `1722 step 3`.
4. Routes are already registered in `register_web_guest_party.go`; confirm nothing is added to `UBYHOST_GO_PATHS`; commit `1722 step 4` if needed.
5. Run the commands in §6; write the report.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/web/... ./cmd/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/web/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes, no test skipped
- `cd App && .venv/bin/python -m pytest tests/test_go_party_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: `test_layout_lint_browser.py` green plus one 390, 768 and 1280 px screenshot per page in the report (rule 10).

## 7. Acceptance

- Slot rows and reservation counters equal Python's after each golden scenario; the head-count flag off and on both match.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1722 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1722-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1728.
- **Rollback:** Revert the PR.

## Owner steps

None.
