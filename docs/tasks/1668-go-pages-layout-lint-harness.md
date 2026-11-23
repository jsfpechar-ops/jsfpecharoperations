# 1668: Browser harness that runs the layout lint on Go host pages (local Go binary, no staging)

Status: review
Depends on: none | Base commit: bdfaa4d4 | Branch: task/1668-go-pages-layout-lint-harness
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (test harness, no product code)

## 1. Objective

Today `App/tests/test_layout_lint_browser.py` only drives the Python app, so a Go host page has no automatic UX gate (AGENTS rule 10). Add a pytest browser test that builds `go/cmd/ubyhost-web`, starts it on a free port against a throwaway PostgreSQL database seeded with one host and one apartment, signs a host session cookie, and for a list of Go paths runs `App/tests/layout_lint.js` at 390, 768 and 1280, saves a full-page screenshot per path and width, and fails on any finding. First list: the Go guide editor pages (already ported, briefs 1440-1448). Later briefs (1664, 1665, 1666) extend the list and the seed; they do not rebuild the harness. This also lets brief 1412 run without a staging server (note for the plan, 1412 itself is not edited here).

## 2. Context (verified on origin/main bdfaa4d4)

**Starting the Go web binary in tests is possible; every piece below exists.** One piece (the goose check on a Python-built schema, bullet 3) is shown only by CI text, not run by the brief writer: step 3 has the check.

- Binary env, `go/cmd/ubyhost-web/main.go`: `UBYHOST_DATABASE_URL` required (`dbURL := os.Getenv("UBYHOST_DATABASE_URL")`); `addr := getenv("UBYHOST_GO_ADDR", "127.0.0.1:8081")`; `migrations := getenv("UBYHOST_MIGRATIONS_DIR", "App/migrations_pg")`; `GET /healthz` answers `{"status":"ok",...}` and 503 when the database is down. `UBYHOST_GO_PATHS` is read only by Caddy (`deploy/lightsail/caddy/Caddyfile.acme:29`), never by the binary: the binary serves every route it registers, so the harness sets no `UBYHOST_GO_PATHS`.
- Startup runs `checkSchema` (`go/cmd/ubyhost-web/register_schema.go:25`): it exits 1 with "goose files pending" unless every goose file in `UBYHOST_MIGRATIONS_DIR` is recorded as applied. CI builds such a database with the Python tool and then `goose ... status`/`up` accepts it (`.github/workflows/ci.yml:224-229`: `UBYHOST_DATABASE_URL="$URL" python scripts/pg_schema.py apply --expect-database ubyhost_test`). The harness uses the same `pg_schema.py apply` on its own throwaway database.
- Test database: CI sets `UBYHOST_TEST_DATABASE_URL: postgresql://postgres:ubyhost@127.0.0.1:5432/ubyhost_test` for Go tests (`.github/workflows/ci.yml:380-381`, job "Format, vet, test and build the Go module"); the Go guide tests derive a throwaway database from that base URL (`go/internal/web/ai/guide_testutil_test.go:56-70`). The harness does the same: `CREATE DATABASE ubyhost_golint_<8 hex>` from that URL, `DROP DATABASE ... WITH (FORCE)` at the end. Use `psycopg` (in `App/requirements.txt`, `psycopg[binary]==3.3.8`) for the admin statements and the seed; no new dependency.
- Env the Go guide tests give the handlers (`guide_testutil_test.go:17-30`): `UBYHOST_SECRET_KEY`, `UBYHOST_PUBLIC_BASE_URL`, `UBYHOST_TERMS_VERSION`, `UBYHOST_PRIVACY_VERSION`, `UBYHOST_DPA_VERSION`; the card tests add `UBYHOST_DATA_DIR` (a temp dir). Use a 40-character fixture secret, `UBYHOST_PUBLIC_BASE_URL=http://127.0.0.1:<port>`, versions `t1`/`p1`/`d1`.
- Seed, copied from the Go tests (`guide_testutil_test.go`): host row `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at, email) VALUES ($1, 'x', 'host', 1, 1, '2026-01-01T00:00:00+00:00', $2)`, then three `legal_acceptance` rows (`document` terms/privacy/dpa, `version` t1/p1/d1, `method` 'backfill', `accepted_at` the same stamp), then `INSERT INTO apartment (owner_user_id, internal_name, created_at) VALUES (...)` (`guideSeedApartment`, `:138-146`). Fixture data only: `@example.test`, made-up names.
- Session cookie: Go accepts the Python cookie format (`go/internal/session/session.go:94-99`, "itsdangerous URLSafeTimedSerializer(secret, salt="ubyhost-session").dumps(payload)"; cookie name `session.CookieName = "ubyhost_session"`, `:24`). The Go tests sign `{"uid": uid, "sv": 1, "iat": <unix>}` (`guide_testutil_test.go:210`). In pytest: `itsdangerous.URLSafeTimedSerializer(secret, salt="ubyhost-session").dumps({"uid": uid, "sv": 1, "iat": int(time.time())})`. A session without `rm` lasts 12 hours from `iat` (`session.go:96-97`).
- **Static files:** the Go binary serves no `/static/` (`git grep -n "FileServer\|StripPrefix" -- go` finds nothing); the shell links `/static/tokens.css` and `/static/app2.css` (`go/internal/hostweb/layout/shell.html:24-25`) and Caddy/Python serve them in production. Without them every lint result is meaningless. The harness answers `**/static/**` itself with Playwright `context.route`, reading `App/static/<path>` (reject `..`, 404 for a missing file). Do not start Python for this.
- Lint and shots reuse the existing pieces: `LINT = (Path(__file__).parent / "layout_lint.js").read_text()` (`test_layout_lint_browser.py:42`), `SHOT_WIDTHS = (390, 768, 1280)` (`:44`), `_out_dir()` (`:70-72`, `UBYHOST_SHOTS_DIR`, folder `layout-lint`), `chromium_launch_kwargs`, `settle_motion` (`tests.browser_support`), `REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"` import pattern (`test_host_wide_geometry_browser.py:21-25`). Findings are lists `[rule, element, detail...]`; zero allowed for host pages. No `ALLOW` entry may be added for a Go page without an owner decision line.
- First paths (the guide editor, ported in 1440-1448; routes in `go/internal/web/ai/guide*.go`). Verified on origin/main: `guideAdd("GET", "/apartments/{id}/leon", (*guideServer).leonPage)` in `guide_leon.go`; the index route `GET /apartments/{id}/guide` is built by `buildIndex` (`guide_index.go`, `d := guideIndexData{Apartment: a, Base: q.base(), Progress: guideProgressOf(rows), NextID: guideNextOpen(rows, 0)}`); `guide_index.tmpl` has `{{guide_section_open "leon" (t "guest_guide.leon.title") ""}}`. The first visit creates the 17 default cards and a token (`ensureDefaults`), so the index needs no extra seed. Verified route lines (`grep -n 'guideAdd("GET"' go/internal/web/ai/*.go`): `/apartments/{id}/guide`, `/apartments/{id}/leon`, `/apartments/{id}/guide/qr`, `/apartments/{id}/guide/quick`, `/apartments/{id}/guide/{item}` (card editor; after the first GET of `/guide`, read the id with `SELECT id FROM guide_item WHERE apartment_id = %s AND kind = 'wifi'`, `guide_data.go:156`). `GO_PATHS` = these five; re-run the grep in step 0 and STOP if a line is missing. `/questions` is not a Go route: leave it out.
- UX gate text this serves: `docs/context/workflow.md#ux-gate`; `docs/design/design-system.md`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/go_web_harness.py` | new | fixtures: `go_web` (build, database, seed, start, stop), `go_cookie`, static routing, `lint_go_paths(...)` |
| `App/tests/test_go_pages_layout_lint_browser.py` | new | the test over `GO_PATHS` |
| `docs/context/test-map.md` | edit | one row for the new test |
| `docs/context/workflow.md` | edit | under `## UX gate`, one line: Go host pages use `tests/test_go_pages_layout_lint_browser.py` |
| `docs/tasks/1668-report.md` | new | the report (§9) |

No other file may change (no Go, no `layout_lint.js`, no existing test).

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints `task/1668-go-pages-layout-lint-harness`.
   - `grep -cF 'addr := getenv("UBYHOST_GO_ADDR", "127.0.0.1:8081")' go/cmd/ubyhost-web/main.go | tail -1` prints `1`; same for `migrations := getenv("UBYHOST_MIGRATIONS_DIR", "App/migrations_pg")`.
   - `grep -cF 'LINT = (Path(__file__).parent / "layout_lint.js").read_text()' App/tests/test_layout_lint_browser.py | tail -1` prints `1`.
   - `grep -cF 'func guideSeedApartment(' go/internal/web/ai/guide_testutil_test.go | tail -1` prints `1`.
   - `command -v go psql | tail -3` lists `go`; `echo "${UBYHOST_TEST_DATABASE_URL:+set}" | tail -1` prints `set`. Not set or no `go`: STOP (§8), this is the owner's local setup.
1. `go_web_harness.py`: module-scoped fixture `go_web`:
   1. Skip rule: if `go` is not on `PATH` or `UBYHOST_TEST_DATABASE_URL` is unset: `pytest.fail(...)` when `UBYHOST_REQUIRE_BROWSER == "1"`, else `pytest.skip(...)`.
   2. `subprocess.run(["go", "build", "-o", str(tmp / "ubyhost-web"), "./cmd/ubyhost-web"], cwd=REPO / "go", timeout=300)`.
   3. Create the throwaway database from the base URL (`psycopg.connect(base_url, autocommit=True)`, `CREATE DATABASE`), build its URL, then `subprocess.run([sys.executable, "scripts/pg_schema.py", "apply", "--expect-database", name], cwd=APP_DIR, env={**os.environ, "UBYHOST_DATABASE_URL": url})`; a non-zero exit fails the fixture with the last 30 output lines.
   4. Seed (bullet "Seed" above), return ids.
   5. Start `subprocess.Popen([binary], env=..., stdout=log_file, stderr=subprocess.STDOUT)` with the env of §2 plus `UBYHOST_DATABASE_URL`, `UBYHOST_GO_ADDR=127.0.0.1:<free port>`, `UBYHOST_MIGRATIONS_DIR=<abs App/migrations_pg>`, `UBYHOST_DATA_DIR=<tmp>`. Poll `GET /healthz` up to 20 s; on timeout or early exit fail with the last 30 log lines (the log never holds the database URL; do not print it).
   6. Teardown (finally): terminate the process (kill after 5 s), `DROP DATABASE ... WITH (FORCE)`.
2. Same file, `lint_go_paths(go_web, paths, cookie, *, extra=None)`: for each width in `(390, 768, 1280)` one `browser.new_context(viewport={"width": w, "height": 1000})`, `add_cookies` (`ubyhost_session`, and `ubyhost_lang=en`), `context.route("**/static/**", handler)` (§2 static bullet), then per path `page.goto(base + path)`, assert status < 400, wait for network idle, `settle_motion(page)`, scroll to top, `page.evaluate(LINT)`, save `<name>-<width>.png` full page into `_out_dir()` (import `_out_dir` and `LINT` from `tests.test_layout_lint_browser`; if that import runs its fixtures' module code with a side effect, copy the two small definitions instead). Return the findings as `{"route", "width", "finding"}` dicts like the existing test. `extra` is an optional per-path callable `(page) -> None` run before the lint, so later briefs can open a state (fill a field, submit a form) and name the screenshot (`<name>+<state>-<width>.png`).
3. `test_go_pages_layout_lint_browser.py`: same `REQUIRE_BROWSER` import block as `test_host_wide_geometry_browser.py:19-25`; `GO_PATHS = {"guide": "/apartments/{apt}/guide", "leon": "...", ...}` from step 0's verified list, `{apt}` filled from the seed; one test `test_go_host_pages_pass_the_layout_lint` that calls `lint_go_paths` and asserts no findings with the same message format as `test_layout_lint_browser.py:187`; one test `test_go_harness_signs_in_and_loads_css` that loads `/apartments/{apt}/guide` and asserts the response is 200, the page has `body` text of the apartment name, and `getComputedStyle(document.body).fontFamily` is not the browser default serif (proves `app2.css` loaded); one test `test_go_harness_rejects_a_signed_out_request` (no cookie: status is a redirect to `/login` or 401/403, never 200 with the editor). If the binary exits with "goose files pending" (the only unproven link): STOP and report, do not edit migrations or `register_schema.go`.
4. Docs: one test-map row `go-pages-layout-lint` mapping `go/internal/web/**/templates/**`, `go/internal/hostweb/**` → the new test; one line in workflow.md under `## UX gate` item 1: "Go host pages: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_go_pages_layout_lint_browser.py -q -rs 2>&1 | tail -30`, 0 skipped; screenshots in `$UBYHOST_SHOTS_DIR/layout-lint/`." Use `grep -n '^## \|^|' docs/context/test-map.md | head -20` to copy the row format.
5. Run §6, commit per step (`1668 step k`), write the report.

## 5. Do not touch

`go/**`, `App/app/**`, `App/tests/layout_lint.js`, `test_layout_lint_browser.py`, `test_host_wide_geometry_browser.py`, `.github/workflows/ci.yml` (running the new test in CI is an owner decision, listed in Owner steps), `docs/tasks/1412-*`, `UBYHOST_GO_PATHS`.

## 6. Commands

From `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots UBYHOST_TEST_DATABASE_URL="$UBYHOST_TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_go_pages_layout_lint_browser.py -q -rs --tb=short -x 2>&1 | tail -30`
From the repo root: `ls /tmp/shots/layout-lint | head -30`; `python3 scripts/context_lint.py 2>&1 | grep -v WARN | tail -3`

## 7. Acceptance

- [ ] The three tests pass with `-rs`: 0 skipped.
- [ ] `/tmp/shots/layout-lint/` holds `<name>-390.png`, `-768.png`, `-1280.png` for every path of `GO_PATHS`; the executor opens the 390 px image of `guide` once and says in the report what it shows (CSS loaded, sidebar/shell present).
- [ ] If the lint reports findings on the existing guide pages: do not fix Go code here and do not allow-list; list them in the report under "Findings" (rule, element, width) and set `Status: review`; the orchestrator writes fix briefs.
- [ ] No leftover database or process (`psql "$UBYHOST_TEST_DATABASE_URL" -Atc "select datname from pg_database where datname like 'ubyhost_golint_%'" | tail -3` prints nothing; `pgrep -f ubyhost-web | tail -1` prints nothing).
- [ ] Docs rows added; context lint OK.

## 8. Stop and ask

Stop if: `go` or `UBYHOST_TEST_DATABASE_URL` is missing in the environment; an anchor of step 0 is not found; the binary exits with "goose files pending" or any other start failure after one fix; the signed-in guide page redirects to login or answers 403 after one fix of the cookie (the account may need a field the Go gate checks: read `go/internal/hostweb/gate.go:82-120` for the reason, do not guess); a path of `GO_PATHS` is not a Go route; 25 tool calls or ~50k tokens; a file outside §3 needs a change.

## 9. Report

`docs/tasks/1668-report.md` (600 tokens at most), `Status: review`, one PR. The PR body states: no new dependency (psycopg, itsdangerous and Playwright are already pinned), no outbound request, fixtures only.

## Risk list (for the reviewer)

`go_web_harness.py` environment handling (never print or log the database URL or the secret), the static route handler (path traversal), teardown always dropping the database.

## Owner steps

1. Optional, after merge: ask the orchestrator for a CI job that runs this test (it needs the `postgres` service and Go, which the Go job already has). Without it the test runs on the machine of whoever changes a Go host page, as rule 10 requires.
2. Briefs 1664, 1665 and later Go host pages use this harness for their 390/768/1280 evidence; it also covers what brief 1412 asked for without a staging server (decision for the plan, not changed here).
