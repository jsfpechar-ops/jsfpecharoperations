# 1730: Go stays 1 (shrunk): submissions list/detail and stay read parity

Status: todo — ready for executor (exact-diff pass NL-24, 2026-11-20).
Depends on: 1380/1381; **GET /reservations/{id}** already on `main` via briefs 1860/1861 (`staydetail`) — this brief adds no stay-detail Go | Base commit: current tip of the working branch | Branch: task/1730-go-submissions-reservations-read
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split only if the executor hits the cap)
Tier: B (Sonnet exact-diff pass; orchestrator read the risk-listed diff)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1730 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1730 step'`.

## 1. Objective

Port **GET /submissions** and **GET /submissions/{submission_id}** to a new Go package `go/internal/web/submissions`, dormant until wave H. **GET /reservations/{reservation_id}** is not re-ported here (list was briefs 1855–1858; detail is briefs 1860–1861 on `main`); the golden script still renders that URL so the combined parity test covers all three read routes the Stays lane needs before 1731.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness (submission detail shows UbyPort outcomes; use `ubyport.LoadCodebook` and `ubyport.Classify` exactly as Python); 2 privacy first (no new personal-data field, no new outbound request); 3 fixtures `@example.test`; 4 no new dependency; 5 PostgreSQL through `pgxpool`, `$n` placeholders; 6 light mode, forms carry `_csrf` where Python forms exist; 11 Go first.

**Shrunk scope (owner / NL-24):** drop **GET /reservations** from this brief. Do not edit `go/internal/web/stays` list code.

**Python source of truth (read-only):** `App/app/routes/admin.py` `submissions_list` and `submission_detail` (anchors below); templates `App/app/templates/submissions.html`, `submission_detail.html`.

**Routes in scope:**

| Method | Path | Go owner |
|---|---|---|
| GET | `/submissions` | new `submissions` package (this brief) |
| GET | `/submissions/{submission_id}` | new `submissions` package (this brief) |
| GET | `/reservations/{reservation_id}` | existing `staydetail` (verify only; golden case) |

**Parity method:** `App/scripts/go_go_submissions_reservations_read_golden.py` seeds a throwaway database, renders the real FastAPI app, writes `go/internal/web/submissions/testdata/submissions_read_golden.json`; `visible_text_test.go` replays the seed on PostgreSQL and compares visible lines (go-first exception 1). Accepted differences belong in the report, never silently.

**All implementation code is pre-written.** Sidecars: `docs/tasks/1730-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action |
|---|---|---|
| `63161a72a031d1a46be2221cb7260f012c19c5b5ceeefd1c2807a38790fb8b53` | `App/scripts/go_go_submissions_reservations_read_golden.py` | create |
| `cadbf5e3fbdb55f0cac238504fa0c8cdfdde4cf990108b97d034a1b1319f6e22` | `App/tests/test_go_go_submissions_reservations_read_golden.py` | create |
| `5d9dcf5904d575157b056fc08ca780f57327871753fde7c857233081da800927` | `go/cmd/ubyhost-web/register_web_submissions.go` | create |
| `302d1463c381ff8b2b7600353dc4bbfc3d2df6c555aa9e0fa345c62c469fb8f6` | `go/cmd/ubyhost-web/register_web_submissions_test.go` | create |
| `53d7997e1625a2d8bc38b9bf721dea675a38d80a19f36876b81199ce811885b5` | `go/internal/web/submissions/data.go` | create |
| `390b021d625fcd79aa45f234c812e6de8a5b5ff09b243859277de9792c581203` | `go/internal/web/submissions/db_test.go` | create |
| `f42952f61dfa1894694c199e1e357d68220e236f54b869ab66559479cfd731d3` | `go/internal/web/submissions/handlers.go` | create |
| `2ab3e62f56cc5207a4349f2392c545ec8ba4373f21cb4310988688facfac61de` | `go/internal/web/submissions/i18n.json` | create |
| `d41e02e09a33a11f31c3f1dbe4c90af1e62f17ca5b859c5ada022672c10dfd98` | `go/internal/web/submissions/i18n_keys.txt` | create |
| `8769f90079b97e6a3fad6bf4aacfd67b6ac40dd50c255a2307bd8a11109f8cbd` | `go/internal/web/submissions/templates/submission_detail.tmpl` | create |
| `0bdb519b4c655c07c18a5a672393f2ec23bd2d3372a44293e7066a93330d458d` | `go/internal/web/submissions/templates/submissions_list.tmpl` | create |
| `1b4eb126e12ee0861d377cd071728b9e0340dd9ef8ccad718420f902fba51480` | `go/internal/web/submissions/testdata/submissions_read_golden.json` | create |
| `92c4be8d050842aa5708f5feda4e4241802e6a1bb6d07f5cb28108a60c6d6cc4` | `go/internal/web/submissions/tpl.go` | create |
| `9d136059ba3dfbfa8379f126dc175687cee4999df6258375ace9c64ac6b27f83` | `go/internal/web/submissions/visible_text.go` | create |
| `ff4ab8277e886f4633f81641e52e1e9c4a9acf72d1e7ef68cb67a4582695c0c1` | `go/internal/web/submissions/visible_text_test.go` | create |

Full manifest: `docs/tasks/1730-files/MANIFEST.sha256`.

**Verified by the brief writer:** sidecars dry-run on current `main` with step 1 copy — `sha256sum -c docs/tasks/1730-files/MANIFEST.sha256` all OK; `gofmt -l` empty; `go vet ./internal/web/submissions/... ./cmd/ubyhost-web/...` silent; `go test ./internal/web/submissions/... -count=1` OK (DB parity skips without `UBYHOST_TEST_DATABASE_URL`); `pytest tests/test_go_go_submissions_reservations_read_golden.py` OK when `App/.venv` exists.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/submissions/data.go` | create | list/detail SQL and guest rows for detail |
| `go/internal/web/submissions/handlers.go` | create | GET handlers and `Register` |
| `go/internal/web/submissions/tpl.go` | create | templates and filter funcs |
| `go/internal/web/submissions/visible_text.go` | create | visible-line normaliser (golden parity) |
| `go/internal/web/submissions/templates/submissions_list.tmpl` | create | list template |
| `go/internal/web/submissions/templates/submission_detail.tmpl` | create | detail template |
| `go/internal/web/submissions/i18n_keys.txt` | create | catalog keys |
| `go/internal/web/submissions/i18n.json` | create | catalog (checked by `go_host_i18n.py`) |
| `go/internal/web/submissions/db_test.go` | create | SQL/unit tests |
| `go/internal/web/submissions/visible_text_test.go` | create | golden parity (submissions + stay head case) |
| `go/internal/web/submissions/testdata/submissions_read_golden.json` | create | golden from Python script |
| `go/cmd/ubyhost-web/register_web_submissions.go` | create | dormant route registration |
| `go/cmd/ubyhost-web/register_web_submissions_test.go` | create | route registration test |
| `App/scripts/go_go_submissions_reservations_read_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_go_submissions_reservations_read_golden.py` | create | golden freshness test |
| `docs/tasks/1730-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1730-report.md` | create | the report (§9) |

No other file may change. Do **not** add or edit `go/internal/web/staydetail/**` or `go/internal/web/stays/**` for this brief.

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). Each `grep -cF` / `ls` anchor prints `1` (see `docs/tasks/1730-files/ANCHORS.txt`):
   - `grep -cF 'func Register(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler, doorCodes ...DoorCodeViewer)' go/internal/web/staydetail/handlers.go | tail -1`
   - `grep -cF 'func LoadCodebook(ctx context.Context, pool *pgxpool.Pool) (map[string]string, map[string]int, error)' go/internal/ubyport/sweep.go | tail -1`
   - `grep -cF 'def submissions_list(request: Request):' App/app/routes/admin.py | tail -1`
   - `grep -cF "{% set how_key = 'reports' %}" App/app/templates/submissions.html | tail -1`
   - `ls go/internal/web/submissions 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls App/scripts/go_go_submissions_reservations_read_golden.py 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls go/cmd/ubyhost-web/register_web_submissions.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `find docs/tasks/1730-files -name '*.txt' ! -name 'ANCHORS.txt' | wc -l | tail -1` prints `15`.

1. Copy sidecars and verify (one call, repo root). Never retype or edit them:

   ```bash
   S=docs/tasks/1730-files && for f in $(cd "$S" && find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   Expected: 15 lines ending `: OK`. Commit `1730 step 1`.

2. Format, build and vet from `go/` (one call):

   ```bash
   cd go && gofmt -l internal/web/submissions cmd/ubyhost-web/register_web_submissions.go 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/submissions/... ./cmd/ubyhost-web/... 2>&1 | tail -30
   ```

   Expected: no output. Commit `1730 step 2` only if gofmt changed a file.

3. Python golden and i18n (from `App/` when `.venv` exists; else note “CI only” in the report):

   ```bash
   cd App && .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -5; .venv/bin/python scripts/go_go_submissions_reservations_read_golden.py --check 2>&1 | tail -10; .venv/bin/python -m pytest tests/test_go_go_submissions_reservations_read_golden.py -q --tb=short -x 2>&1 | tail -10
   ```

   Expected: i18n check quiet, golden not stale, `1 passed`. If golden stale, run without `--check`, commit updated json, commit `1730 step 3`.

4. PostgreSQL tests when `UBYHOST_TEST_DATABASE_URL` is set (one call):

   ```bash
   cd go && go test ./internal/web/submissions/... -count=1 2>&1 | tail -30
   ```

   Expected: `ok`; no test skipped for DB parity when the URL is set. Commit `1730 step 4` if tests or golden changed.

5. Layout lint and screenshots for **submissions list and submission detail** (rule 10); stay detail screenshots optional (already gated on 1861). Write the report (§9); set `Status: review`.

## 5. Do not touch

`UBYHOST_GO_PATHS`; `go/internal/web/staydetail/**` and `go/internal/web/stays/**`; filing send code; anything under `App/app/` except what §3 lists.

## 6. Commands

- `cd go && gofmt -l internal/web/submissions | tail -5` prints nothing
- `cd go && go vet ./internal/web/submissions/... ./cmd/ubyhost-web/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/web/submissions/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes
- `cd App && .venv/bin/python -m pytest tests/test_go_go_submissions_reservations_read_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: `test_layout_lint_browser.py` green plus 390/768/1280 screenshots for **submissions** pages in the report

## 7. Acceptance

- [ ] Golden parity for seeded cases (submission states, list empty/non-empty, one stay-detail head case); submissions screenshots at 390/768/1280; layout lint green on those pages
- [ ] GET `/submissions` and GET `/submissions/{id}` answer on Go in tests with the same visible lines as the golden; signed-out gets the same redirect as Python
- [ ] `git log --oneline --grep='^1730 step'` shows one commit per step; `git diff --stat` lists only §3 paths

## 8. Stop and ask

Stop and write the report when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; retention or outbound work is needed; tests need a skip.

## 9. Report

`docs/tasks/1730-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots, what was left undone.

## Rollout wave and rollback

- **Rollout:** Dormant until wave H (brief 1737); nothing is added to `UBYHOST_GO_PATHS` here.
- **Rollback:** Revert the PR.

## Owner steps

None.