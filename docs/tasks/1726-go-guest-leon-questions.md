# 1726: Go guest 7: guest Leon chat and host question pages

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
Depends on: 1720, 1436 (Go Leon) | Base commit: current tip of the working branch | Branch: task/1726-go-guest-leon-questions
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: B (Sonnet writes the exact-diff pass; orchestrator reads the diff of the risk-listed files)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1726 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1726 step'`.

## 1. Objective

Port `guest_leon.py` (4 routes) and `guest_questions.py` (5 routes). Brief 1629 (guest guide view) is unblocked by 1720 and runs here as a dependency.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `App/app/routes/guest_leon.py`, `guest_questions.py`; `go/internal/anthropic`, AI budget vars (`UBYHOST_AI_MONTHLY_USD_*`).

**Routes in scope (method path, Python function):**

- GET/POST /l/{token}/{reservation_id}/guide/leon
- GET/POST /g/{token}/leon
- GET /apartments/{apartment_id}/guide/questions
- GET/POST /apartments/{apartment_id}/guide/questions/{question_id}
- POST /apartments/{apartment_id}/guide/questions/{question_id}/dismiss and /card

**Risk:** AI cost and guest text sent to an outside model (existing disclosure).

**Parity method (same as briefs 1595 and 1580):** `App/scripts/go_leon_questions_golden.py` seeds a throwaway database, renders the real FastAPI app when `App/.venv` is available, and writes `go/internal/web/guest/testdata/leon_questions_golden.json`; `leon_questions_test.go` replays on PostgreSQL when `UBYHOST_TEST_DATABASE_URL` is set (go-first exception 1). Accepted differences belong in the report, never silently.

**All implementation code is pre-written.** Sidecars: `docs/tasks/1726-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action |
|---|---|---|
| `abc53aa5187524b9be268dfca5843e1b5b38aba34db76b0ead03f9d5ef785de1` | `App/scripts/go_leon_questions_golden.py` | create |
| `70a792c358a714c74d1e778cc6cd46da52353123654152bece32bb2299ce554a` | `App/tests/test_go_leon_questions_golden.py` | create |
| `b3a694ee7df26b7f36401d96aefc25fb1eb2fe19021dfe4c35d2fb508e1711f4` | `go/cmd/ubyhost-web/register_web_guest_leon_questions.go` | create |
| `a7f16f60877edadb84834c8db972f34beb19ffd33b30c8b93f15d911209d41e0` | `go/cmd/ubyhost-web/register_web_guest_leon_questions_test.go` | create |
| `72b32c05c3ffc0fa1722770c849c349a80b852b6db8b3947686247a5cce3b21b` | `go/internal/web/guest/leon_questions.go` | create |
| `d1910dd28fab44289661e61e3c8f9aea6f248b79aa7ed00c139a7ed84ddf81f4` | `go/internal/web/guest/leon_questions_test.go` | create |
| `724b6a63a457f35651bc57bdb8204c65a7b9c1c729e07960f4eea732bab06beb` | `go/internal/web/guest/testdata/leon_questions_golden.json` | create |

Full manifest: `docs/tasks/1726-files/MANIFEST.sha256`.

**Verified by the brief writer:** sidecars dry-run on current `main` with step 1 copy — `sha256sum -c docs/tasks/1726-files/MANIFEST.sha256` all OK; `gofmt -l` empty on copied paths; `go test ./internal/web/guest/... ./cmd/ubyhost-web/... -run LeonQuestions` OK; `pytest tests/test_go_leon_questions_golden.py` OK when `App/.venv` exists.

**Executor note:** step 1 is one copy of all seven paths (brief 1726 step 2–4 text is folded into the sidecars). Host question templates and catalog strings live inside `leon_questions.go` (no separate template files). Full FastAPI golden replay and DB parity tests ship in the report when the executor runs §6 with `UBYHOST_TEST_DATABASE_URL`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/guest/leon_questions.go` | create | routes |
| `go/internal/web/guest/leon_questions_test.go` | create | golden parity and route tests |
| `go/internal/web/guest/testdata/leon_questions_golden.json` | create | golden written by the Python script |
| `go/cmd/ubyhost-web/register_web_guest_leon_questions.go` | create | registers the routes |
| `go/cmd/ubyhost-web/register_web_guest_leon_questions_test.go` | create | route registration test |
| `App/scripts/go_leon_questions_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_leon_questions_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1726-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1726-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). Each `grep -cF` / `ls` anchor prints `1` (see `docs/tasks/1726-files/ANCHORS.txt`):
   - `grep -cF '@router.get("/l/{token}/{reservation_id}/guide/leon")' App/app/routes/guest_leon.py | tail -1`
   - `grep -cF '@router.get("/apartments/{apartment_id}/guide/questions")' App/app/routes/guest_questions.py | tail -1`
   - `grep -cF 'def reply(chat: Dict[str, Any], text: str' App/app/leon.py | tail -1`
   - `grep -cF 'MAX_ANSWER_CHARS = 1000' App/app/guest_handoff.py | tail -1`
   - `ls go/internal/web/guest/leon_questions.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls App/scripts/go_leon_questions_golden.py 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls go/cmd/ubyhost-web/register_web_guest_leon_questions.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `find docs/tasks/1726-files -name '*.txt' ! -name 'ANCHORS.txt' | wc -l | tail -1` prints `7`.

1. Copy sidecars and verify (one call, repo root). Never retype or edit them:

   ```bash
   S=docs/tasks/1726-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'ANCHORS.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   Expected: 7 lines ending `: OK`. Commit `1726 step 1`.
2. Run `App/scripts/go_leon_questions_golden.py` when FastAPI replay is needed; commit golden if it changes. Commit `1726 step 2`.
3. `gofmt -l` on `go/internal/web/guest` and the register file prints nothing. Commit `1726 step 3` if needed.
4. Run the commands in §6; write the report.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/web/... ./cmd/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/web/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes, no test skipped
- `cd App && .venv/bin/python -m pytest tests/test_go_leon_questions_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: `test_layout_lint_browser.py` green plus one 390, 768 and 1280 px screenshot per page in the report (rule 10).

## 7. Acceptance

- Budget caps and the 'AI is off' answer match Python; no model name is hard-coded outside config.
- No guest message is stored beyond the existing retention line.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1726 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1726-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1728.
- **Rollback:** Revert the PR.

## Owner steps

None.
