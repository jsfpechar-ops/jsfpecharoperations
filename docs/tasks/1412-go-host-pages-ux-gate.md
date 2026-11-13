# 1412: UX gate for the Go host pages added in PR #1003

Status: blocked — the browser UX tooling can only start the Python app (in-process uvicorn on SQLite, Python session and fixtures); nothing in the repo starts the Go service for a host page, so the 390/768/1280 screenshots and zero-finding lint of the Go host pages cannot be produced. Owner decision needed (see §4).
Depends on: owner decision on the tooling in §4 | Base commit: 3d75651dd | Branch: cursor/1412-go-host-pages-ux-gate-4de2
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Run the UX gate (AGENTS.md hard rule 10, [workflow](../context/workflow.md#ux-gate)) on the Go host pages that PR #1003 added and record per page what the 390, 768 and 1280 px screenshots show. No code is fixed here: every finding becomes the input of a later fix brief. The pages are dormant until their paths are added to `UBYHOST_GO_PATHS`, so the gate must pass before the owner does that.

## 2. Context

Pages that need the gate (all merged by PR #1003, Go-served, host pages):

- Customer admin pages: `go/internal/web/customers/`.
- Property pages and lists: `go/cmd/ubyhost-web/register_web_properties.go`, `go/internal/web/properties/` (`pages.go`, `lists.go`, `templates/`).
- Layout shell used by every Go host page: `go/internal/hostweb/layout/`.

Why this brief is blocked (checked by the brief writer, with the commands to re-check):

1. `App/tests/test_layout_lint_browser.py` takes its server from `wide_host` and `wide_base` in `App/tests/test_host_wide_geometry_browser.py` (`grep -n 'def wide_host\|def wide_base' App/tests/test_host_wide_geometry_browser.py`). `wide_base` starts `uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", ...))` on a thread, where `app` is `from app.main import app`, the Python FastAPI app. It seeds data through `app.db` helpers and logs in with Python sessions.
2. Which paths go to Go is decided by Caddy through `UBYHOST_GO_PATHS` (`deploy/lightsail/caddy/Caddyfile.*`, `docs/ENVIRONMENT.md` row `UBYHOST_GO_PATHS`). The Python app has no proxy to Go (`git grep -n 'UBYHOST_GO_PATHS' -- App` prints nothing), and the tests run no Caddy.
3. The Go binary needs `UBYHOST_DATABASE_URL` (Postgres; `go/cmd/ubyhost-web/main.go` lines 137-139) and listens on `UBYHOST_GO_ADDR` (default `127.0.0.1:8081`). The Python browser fixtures use SQLite, and no script or CI job starts the Go service with seeded host data and a logged-in session for a browser run (`git grep -l 'ubyhost-web' -- scripts .github` lists only `.github/workflows/ci.yml`, which builds the binary and checks the missing-variable error).
4. The only Go screenshot helper is `go/internal/web/public/shots_test.go` (`TestServeForScreenshots`, started with `PUBLIC_LEGAL_SHOTS_ADDR`). It serves the five public legal pages, which need no login and no database. It does not cover host pages.
5. `tests/layout_lint.js` is plain JavaScript that Playwright injects into any page, so it could run against a Go page. `App/tests/test_layout_lint_browser.py` hard-wires the Python route map, the Python fixtures and `ALLOW`, so it cannot be pointed at a Go URL by an environment variable (`grep -n 'wide_base' App/tests/test_layout_lint_browser.py` shows every page goes through `wide_base`).

Tooling that would be needed (a description for the owner; nothing here is built or invented by this brief):

- A way to run `ubyhost-web` for a browser: Postgres with the host data the pages need (a workspace, apartments, customers, reservations), a seeded host session, and the static files from `App/app/static`, like `shots_test.go` does for the public pages.
- A Playwright driver that opens each Go host page at 390, 768 and 1280, injects `layout_lint.js`, and writes screenshots to `/tmp/shots/layout-lint/<page>-<width>.png` (the folder the UX gate reads).
- Either that driver in a new test file, or a parameter on `test_layout_lint_browser.py` for the base URL and route map. Which one is the owner's decision, since it adds test code to `App/tests/` and a Go test or script to `go/`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/tasks/1412-report.md` | create | per-page findings (once unblocked) |

Nothing else may change. If the owner approves tooling, the tooling gets its own brief and this brief depends on it.

## 4. Steps

1. Do not run this brief while `Status:` is `blocked`. If you were handed it anyway: write `docs/tasks/1412-report.md` with the single line `blocked: see Status line of 1412`, change nothing else, and STOP.

When the owner has decided, the orchestrator rewrites this section with these steps (not executable yet, listed so the decision is clear):

- Start the Go service with the seeded data and a host session using the tooling from the new brief; command and expected output go here.
- Run the lint and screenshot driver for each page of §2 and open the 12 or more PNGs (`/tmp/shots/layout-lint/<page>-{390,768,1280}.png`).
- In the report write, per page: `390: ...; 768: ...; 1280: ...` plus every lint finding verbatim. Tick the [design-system checklist](../design/design-system.md). Fix nothing.

Owner decision options:

- A. Approve building the harness (a new brief for the Go-serving fixture and the Playwright driver).
- B. Run the gate by hand on the staging server after adding the paths to `UBYHOST_GO_PATHS` there, and give the orchestrator the screenshots.
- C. Keep the Go host paths out of `UBYHOST_GO_PATHS` until A or B is done (the current state; nothing ships to users).

## 5. Do not touch

- `App/`, `go/`, `deploy/`, `scripts/`, `tests/`, `.github/`.
- `UBYHOST_GO_PATHS` in any environment file.
- No new tooling: hard rule 4 and the "no invented tooling" instruction of this brief.

## 6. Commands

None while blocked. Re-check commands for the reasons in §2:

- `grep -n 'def wide_host\|def wide_base' App/tests/test_host_wide_geometry_browser.py | tail -5`
- `git grep -n 'UBYHOST_GO_PATHS' -- App | wc -l` (expected `0`)
- `git grep -l 'ubyhost-web' -- scripts .github | tail -5`

## 7. Acceptance

- [ ] (Once unblocked) per page of §2: one line `390: ...; 768: ...; 1280: ...` in `docs/tasks/1412-report.md`.
- [ ] (Once unblocked) the lint run is green or every finding is listed with its element text.
- [ ] (Once unblocked) no file other than the report changed (`git diff --stat origin/main...HEAD | tail -5`).

## 8. Stop and ask

Stop, and write the report, if:

- `Status:` is `blocked`;
- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1412-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Not applicable while blocked. Once unblocked: the screenshots themselves, read at 390 px first.

## Owner steps

1. Pick option A, B or C from §4 and tell the orchestrator in the chat.
2. For B: add the property and customer paths to `UBYHOST_GO_PATHS` on staging only, open each page at phone width, and send the screenshots to the orchestrator.
