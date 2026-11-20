# 1750: Go misc 1: robots, sitemap, manifest, service worker, offline, favicon, language, tdmrep

Status: todo — ready for executor (exact-diff pass 2026-11-20).
Depends on: none | Base commit: current tip of the working branch | Branch: task/1750-go-main-utility-routes
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: B (Sonnet writes the exact-diff pass; orchestrator reads the diff of the risk-listed files)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1750 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1750 step'`.

## 1. Objective

Port the small `main.py` routes. `/sample-airbnb.ics` is brief 1650; `/healthz` and `/metrics` stay as they are. `/dev/ui` is not ported: owner decision 2026-11-15, it is deleted with Python.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `App/app/main.py` 495-628, `static/sw.js`.

**Routes in scope (method path, Python function):**

- GET /robots.txt
- GET /.well-known/tdmrep.json
- GET /manifest.webmanifest
- GET /sw.js
- GET /offline
- GET /sitemap.xml
- POST /language
- GET /favicon.ico

**Parity method (same as briefs 1595 and 1580):** a golden script `App/scripts/go_go_main_utility_routes_golden.py` seeds a throwaway database with made-up rows, renders the real FastAPI app, and writes `go/internal/web/public/testdata/utility_golden.json`; `utility_test.go` replays the seed on PostgreSQL when `UBYHOST_TEST_DATABASE_URL` is set and must match byte for byte (go-first exception 1). Accepted differences are listed in the report, never silently.

**All implementation code is pre-written.** Sidecars: `docs/tasks/1750-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action |
|---|---|---|
| `bc436cb22f48037c365e5a5c912395a33eded47eb8e0a64ceb672e2b253e519e` | `App/scripts/go_go_main_utility_routes_golden.py` | create |
| `ef7c895f80210ee5df884bacb284ffdb60c988fdd2376952ec5c196690e85cfc` | `App/tests/test_go_go_main_utility_routes_golden.py` | create |
| `c20675da98d71e8b2630a4d7575eee71653940ab2de45c455982f45513459a17` | `go/cmd/ubyhost-web/register_web_public_utility.go` | create |
| `d0a41bb3f6cc245e9b052b73dea85e9daf7c8c55245bccf6b363689936320030` | `go/cmd/ubyhost-web/register_web_public_utility_test.go` | create |
| `0c3bdb52eebda6ca08871cf352bf2da86fbe85d7be1afff6361d1ee5a1027fc8` | `go/internal/web/public/seo_util.go` | create |
| `42112646867accf07612b5daeab6b487c80f0d3d8994f284cb0bb9d09ec21cbe` | `go/internal/web/public/utility.go` | create |
| `2c73fe97bb0b6d34a50f797eaf8455910479e04127777efacb66718184eca16a` | `go/internal/web/public/utility_test.go` | create |
| `58814620c750ed1833a9780e262909d938f57076b14b9b73b3d633de188f70e1` | `go/internal/web/public/testdata/utility_golden.json` | create |

Full manifest: `docs/tasks/1750-files/MANIFEST.sha256`.

**Verified by the brief writer:** sidecars dry-run on current `main` with step 1 copy — `sha256sum -c docs/tasks/1750-files/MANIFEST.sha256` all OK; `gofmt -l` empty; `go vet ./internal/web/public/... ./cmd/ubyhost-web/...` silent; `go test ./internal/web/public/... ./cmd/ubyhost-web/... -count=1` OK (DB parity runs when `UBYHOST_TEST_DATABASE_URL` is set); `pytest tests/test_go_go_main_utility_routes_golden.py` OK when `App/.venv` exists.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/public/seo_util.go` | create | robots and sitemap text (`seo.py`) |
| `go/internal/web/public/utility.go` | create | routes (offline HTML inline) |
| `go/internal/web/public/utility_test.go` | create | golden parity and route tests |
| `go/internal/web/public/testdata/utility_golden.json` | create | golden written by the Python script |
| `go/cmd/ubyhost-web/register_web_public_utility.go` | create | registers the routes |
| `go/cmd/ubyhost-web/register_web_public_utility_test.go` | create | route registration test |
| `App/scripts/go_go_main_utility_routes_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_go_main_utility_routes_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1750-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1750-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). Each anchor in `docs/tasks/1750-files/ANCHORS.txt` must print `1`.
1. Copy sidecars and verify (one call, repo root). Never retype or edit them:

   ```bash
   S=docs/tasks/1750-files && for f in $(cd "$S" && find . -name '*.txt' | sed 's|^\./||; s|\.txt$||' | grep -v ANCHORS); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && (cd "$S" && sha256sum -c MANIFEST.sha256) 2>&1 | tail -20
   ```

   Expected: 8 lines ending `: OK`. Commit `1750 step 1`.
2. Format, vet and test from `go/` (one call); `gofmt -l` prints nothing. Commit `1750 step 2` if only golden timestamp noise.
3. Run `cd App && .venv/bin/python scripts/go_go_main_utility_routes_golden.py` and commit when stale (should already match after step 1). Commit `1750 step 3`.
4. Confirm routes are dormant: `register_web_public_utility.go` from step 1 only calls `registerRoutes`; nothing is added to `UBYHOST_GO_PATHS`. Commit `1750 step 4` when satisfied.
5. Run the commands in §6; write the report (`1750 step 5`).

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/web/... ./cmd/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/web/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes, no test skipped
- `cd App && .venv/bin/python -m pytest tests/test_go_go_main_utility_routes_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: `test_layout_lint_browser.py` green plus one 390, 768 and 1280 px screenshot per page in the report (rule 10).

## 7. Acceptance

- Bytes equal Python's golden; `sw.js` keeps its `Cache-Control` and `Service-Worker-Allowed` headers; `/sitemap.xml` lists the same public URLs.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1750 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1750-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Wave U: add `/robots.txt /.well-known/* /manifest.webmanifest /sw.js /offline /sitemap.xml /language /favicon.ico` in one deploy; one day.
- **Rollback:** Trim the line.

## Owner steps

None.
