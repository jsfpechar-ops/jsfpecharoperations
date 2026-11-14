# 1615: Go privacy requests: the list page GET /privacy-requests

Status: todo
Depends on: 1370 (merged on main, so on go-wave3) | Base commit: none (one big PR mode: the branch that is checked out, go-wave3) | Branch: the current one
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier A (writer: Opus)

> **One big PR mode.** The owner wants one big pull request for the whole Go port. You work on the branch that is checked out now. Never create a branch, never push, never open a PR, never use `mcp__` tools. After each step that changes a file, commit with the message `1615 step k` (k is the step number) and nothing else in the first line; end the message with the two trailer lines from the session reminder if one is given. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1615 step'` and `git show --stat` on those commits.

## 1. Objective

Port the last Python-only route of `App/app/routes/privacy_requests.py`, `GET /privacy-requests` (`privacy_requests_list`, template `privacy_requests.html`), into the existing Go package `go/internal/web/privacy` and register it, still switched off. After this brief Go serves all three routes of the data-subject request register, so the shared path `/privacy-requests` can be moved to Go as a whole (owner steps).

## 2. Context

Rules (AGENTS.md): 1 filing is untouched (nothing here reads or writes UbyPort data); 2 privacy: no new personal-data field, no new outbound request, the page shows the same columns Python shows, to the same host only; 3 fixtures are made up (`@example.test`, test-only secrets); 4 no new dependency (`go.mod` and `go.sum` stay as they are); 5 plain PostgreSQL through pgx, the existing `ListForOwner` (no new SQL, no schema change); 6 light mode, the forms work without JavaScript (plain `<form method="post">`, as in Python); 7 and 10 (screenshots, UX gate) do not apply yet: the page is not served (no path in `UBYHOST_GO_PATHS`), and the UX gate cannot run on Go pages yet (brief 1412 is paused, no staging server). It is an owner-step condition at the switch below. 11 Go first: the two Python files in §3 are under `App/scripts/` and `App/tests/` only, go-first exception 1 (golden script and parity test); no file under `App/app/` changes.

**PR text (hard rule 2):** no new outbound request and no new personal-data field.

**All code is pre-written, compiled and tested** by the brief writer on a clean checkout of go-wave3. Sidecars live under `docs/tasks/1615-files/<repo path>.txt`; step 1 copies them byte for byte. You write no application code. Never retype or edit a copied file. A sha256 mismatch: STOP (§8).

**Verified by the brief writer** (fresh throwaway worktree of go-wave3 `859d114d5` plus this brief; steps 0 to 7 run exactly as written, toolchain go1.25.14, PostgreSQL 16): gofmt, build and vet silent; `go test ./internal/web/privacy/ ./cmd/ubyhost-web/` two `ok`, the 6 named tests PASS, `--- SKIP` count 0; pytest `3 passed`, none skipped; `go_host_i18n.py --check` exit 0. The parity test was also checked to fail when one golden line is changed. Not run: browser tests (the page is not served).

| sha256 | file (repo path; sidecar = `docs/tasks/1615-files/<path>.txt`) |
|---|---|
| `1b2a2bd22b6a1f84218feb2f294b7474368dc5b3d7bcbe154532f035fc7ca834` | `go/internal/web/privacy/page.go` |
| `b30f8a8aa8a43a6a759f3477755b3f3d23e8a0c5909000a89a374e04b8a867fb` | `go/internal/web/privacy/templates/privacy_requests.tmpl` |
| `7d6a3e4b648b604e588309c4f091b99393063aea3c74556309ad3a2f92d8fdbe` | `go/internal/web/privacy/page_test.go` |
| `fb8ff160ac7a0b3f6d357e343ea806200657020a8729825296c8283bfd5f9393` | `go/internal/web/privacy/testdata/privacy_requests_page_golden.json` |
| `31f8260224b8c66d3b60e2e39433fcf8d26a3f1fc7aab7b46e44aadb3d6d5de8` | `go/internal/web/privacy/i18n_keys.txt` |
| `9eccc88bc4624a2e8f09ef357ad914a95f8a15e03d89a10b09423fb38b788472` | `go/internal/web/privacy/i18n.json` |
| `5ca9bfb8ce1fc049da7908c44599485c1d5e4317ef9b48b8760cbf299e8e1ed3` | `go/cmd/ubyhost-web/register_web_privacy.go` |
| `20f096274f48ab799c1504060cfe46bb03b0a7fae6d893068580f2cde6e32a18` | `go/cmd/ubyhost-web/register_web_privacy_test.go` |
| `aec16c23a07ed26cc086e5bd2743a25009ec0c847fc0262ccdf21b8fb0b4d2aa` | `App/scripts/privacy_requests_page_golden.py` |
| `d2cc491295e319cf2a42793b6e61559c8a4453aba02115d34658475629dc1be9` | `App/tests/test_go_privacy_requests_page.py` |

**What Go serves today (brief 1370, `go/cmd/ubyhost-web/register_web_privacy.go`):** `POST /privacy-requests` (`CreateHandler`) and `POST /privacy-requests/{id}` (`UpdateHandler`). `go/internal/web/privacy/store.go` already has `ListForOwner` (dsr.list_for_owner, golden-pinned by 1370) and the lists `Channels`, `RequestTypes`, `SubjectKinds`, `Statuses`. Missing: the GET page (`docs/plans/go-full-move-remaining.md` section 3, "Privacy request pages 1 / 3", and section 4, path collision `/privacy-requests`). The other privacy-area routes are already Go (`GET /privacy` public legal page, `POST /settings/privacy/ad-consent` in `go/internal/web/auth`) or are guest pages that stay last (`GET /l/{token}/privacy`, out of scope). No brief 1371 exists, although 1370's owner step names one: this brief is that page.

**Parity (Python -> Go):**

| Python | Go |
|---|---|
| `routes/privacy_requests.py` `privacy_requests_list` 19-35: `auth.require_login`, then `dsr.list_for_owner(access.owner_id(request))` | `ListHandler` in `page.go`: `hostweb.Login`, then `ListForOwner(ctx, pool, &h.Workspace.ID)` (the same owner the two POSTs use) |
| context `channels`, `request_types`, `subject_kinds`, `statuses` | `listData` with the four store lists |
| `privacy_requests.html` (extends `host_page.html`, `v2`, `nav='privacy_requests'`, `body_kind='list'`, empty `page_title`, title `privacy_requests.title`) | `templates/privacy_requests.tmpl` on the shared layout: `layout.Page{Title, Nav: "privacy_requests", BodyKind: "list", V2: true}`, an empty `privacy_requests.title` slot (no page header, as the empty `page_title` block), the partial `settings_back_header.html` written out as its markup (back link to `/settings`, no help, no actions) |
| filters `date_cz` (validation.fmt_date), `datetime_local` | `dateCZ` (page func, same as `properties.dateCZ`), the layout's `datetime_local` |
| strings `privacy_requests.*` from `host_i18n.py` | `i18n_keys.txt` gains the line `privacy_requests.*`; `i18n.json` regenerated by `App/scripts/go_host_i18n.py` (checked by the existing `test_privacy_catalog_matches_host_i18n`) |

**Parity test:** `App/scripts/privacy_requests_page_golden.py` seeds a SQLite database, signs three hosts in through the real `/login/link`, renders the real Python page for 6 cases (en, cs, vi; seven requests of every status, a naive, offset, fractional and unparsable date, an outcome note with quotes, `<`, `&` and non-ASCII; a host with one request; two hosts with none, where the create form is `open`) and keeps the visible lines of `div.ui-page`: every text run and every tag with `id href action method name value type selected checked required for aria-current aria-label open inputmode class` (class normalised, the CSRF value masked). `page_test.go` seeds PostgreSQL from the same JSON, renders `ListHandler` and compares line by line; it also checks that a signed-out visitor is redirected to `/login`. Requests with no owner (49) and of another host (70) must not show, and they do not. `App/tests/test_go_privacy_requests_page.py` fails when the JSON is stale. The navigation, alerts and toasts outside `div.ui-page` are the layout's and are pinned by its own golden test.

**Known differences from Python (not fixed here, listed in the report):**

- D1. `date_cz` of `received_at`: Python's `strptime("%Y-%m-%d")` also takes one-digit months and days (`2026-1-5`); Go needs two digits and shows such a value unchanged. The create route never stores one (its `fromisoformat` refuses it), so only a hand-edited row could differ.
- D2. A wrong method on `/privacy-requests` answers Go's plain-text 405; Python answers JSON `{"detail":"Method Not Allowed"}` (as every Go area).
- D3. A paused workspace: `hostweb.Login` lets the GET through as Python's read-only mode does; the two POSTs keep 1370's behaviour (redirect to `/predplatne`, as Python, because `/privacy-requests` is not one of Python's exempt prefixes).
- D4. The parity test compares visible lines and the attributes listed above, not bytes (whitespace and the arrow icon's SVG are not compared).
- D5. Not visually checked: the UX gate cannot run on Go pages yet (owner steps).

**Outbound requests:** none. **Audit rows:** none (a GET writes nothing).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/privacy/page.go` | create | `ListHandler`, `dateCZ`, the parsed templates |
| `go/internal/web/privacy/templates/privacy_requests.tmpl` | create | privacy_requests.html on the layout |
| `go/internal/web/privacy/page_test.go` | create | Python parity of 6 cases, signed-out redirect, `dateCZ` |
| `go/internal/web/privacy/testdata/privacy_requests_page_golden.json` | create | written by the golden script from the Python page |
| `go/internal/web/privacy/i18n_keys.txt` | replace (created by 1370) | adds `privacy_requests.*` |
| `go/internal/web/privacy/i18n.json` | replace (generated) | the catalog with the `privacy_requests.*` strings |
| `go/internal/web/privacy/store.go` | edit, one comment line | the package comment names the GET page |
| `go/cmd/ubyhost-web/register_web_privacy.go` | replace (created by 1370) | registers `GET /privacy-requests` |
| `go/cmd/ubyhost-web/register_web_privacy_test.go` | create | the three routes reach their patterns |
| `App/scripts/privacy_requests_page_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_privacy_requests_page.py` | create | the golden is not stale (go-first exception 1) |
| `docs/tasks/1615-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1615-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `grep -cF 'func ListForOwner(ctx context.Context, db DB, owner *int64) ([]Request, error) {' go/internal/web/privacy/store.go | tail -1` prints `1`.
   - `grep -cF 'mux.Handle("POST /privacy-requests", m.wrap("/privacy-requests", privacy.CreateHandler(pool, os.Getenv, time.Now)))' go/cmd/ubyhost-web/register_web_privacy.go | tail -1` prints `1`.
   - `ls go/internal/web/privacy/page.go 2>&1 | tail -1` says "No such file".
   - `grep -cF 'def privacy_requests_list(request: Request):' App/app/routes/privacy_requests.py | tail -1` prints `1`.
   - `find docs/tasks/1615-files -name '*.txt' | wc -l | tail -1` prints `10`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1615-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   1b2a2bd22b6a1f84218feb2f294b7474368dc5b3d7bcbe154532f035fc7ca834  go/internal/web/privacy/page.go
   b30f8a8aa8a43a6a759f3477755b3f3d23e8a0c5909000a89a374e04b8a867fb  go/internal/web/privacy/templates/privacy_requests.tmpl
   7d6a3e4b648b604e588309c4f091b99393063aea3c74556309ad3a2f92d8fdbe  go/internal/web/privacy/page_test.go
   fb8ff160ac7a0b3f6d357e343ea806200657020a8729825296c8283bfd5f9393  go/internal/web/privacy/testdata/privacy_requests_page_golden.json
   31f8260224b8c66d3b60e2e39433fcf8d26a3f1fc7aab7b46e44aadb3d6d5de8  go/internal/web/privacy/i18n_keys.txt
   9eccc88bc4624a2e8f09ef357ad914a95f8a15e03d89a10b09423fb38b788472  go/internal/web/privacy/i18n.json
   5ca9bfb8ce1fc049da7908c44599485c1d5e4317ef9b48b8760cbf299e8e1ed3  go/cmd/ubyhost-web/register_web_privacy.go
   20f096274f48ab799c1504060cfe46bb03b0a7fae6d893068580f2cde6e32a18  go/cmd/ubyhost-web/register_web_privacy_test.go
   aec16c23a07ed26cc086e5bd2743a25009ec0c847fc0262ccdf21b8fb0b4d2aa  App/scripts/privacy_requests_page_golden.py
   d2cc491295e319cf2a42793b6e61559c8a4453aba02115d34658475629dc1be9  App/tests/test_go_privacy_requests_page.py
   EOF
   ```

   Every line must end with `: OK` (10 lines). Then commit "1615 step 1".

2. Edit one comment line in `go/internal/web/privacy/store.go`. Anchor: `grep -nF "// of App/app/dsr.py they use. The GET page comes in a later brief." go/internal/web/privacy/store.go | tail -2` prints line 3. Replace that whole line with:

   ```go
   // of App/app/dsr.py they use, and the GET list page (page.go, brief 1615).
   ```

   Change nothing else. Check: `sha256sum go/internal/web/privacy/store.go | tail -1` prints `30a68e7dbcda2a359f74d4f02d0aa42589b38412a3de526ecc8e04fb3301efc0`. Commit "1615 step 2".

3. Format, build and vet (one call, repo root):

   ```bash
   cd go && gofmt -l internal/web/privacy cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/privacy/ ./cmd/ubyhost-web/ 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). No commit.

4. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one on your own port (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1615x && chown postgres /var/tmp/pg1615x && su postgres -c 'cd /tmp && /usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1615x/data -A trust -U postgres >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1615x/data -o "-p 55616 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1615x" -l /var/tmp/pg1615x/log -w start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55616/postgres` in step 5. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only step 6, and STOP before step 5.

5. Run the Go tests of this brief (one call, repo root):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55616/postgres go test ./internal/web/privacy/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
   ```

   Expected: two `ok` lines (`.../go/internal/web/privacy` and `.../go/cmd/ubyhost-web`). Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55616/postgres go test ./internal/web/privacy/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestListPageMatchesPython$|^TestVisibleLines$|^TestDateCZ$|^TestPrivacyRequestsGolden$|^TestListForOwnerDatabase$|^TestPrivacyRoutesRegistered$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -20
   ```

   Expected: one `--- PASS` line for each of the 6 tests, then two `ok` lines; no `--- SKIP`, no `--- FAIL`. Count: `... 2>&1 | grep -c -- '--- SKIP'` on the same command prints `0`; write that count in the report.

6. Python parity checks (one call, from `App/`). If `App/.venv` is missing, create it first: `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3`. Then:

   ```bash
   cd App && .venv/bin/python -m pytest tests/test_go_privacy_requests_page.py tests/test_go_privacy_requests.py -q --tb=short -rs 2>&1 | tail -8; .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -3; echo "i18n check exit ${PIPESTATUS[0]}"
   ```

   Expected: `3 passed`, no `SKIPPED` line, and `i18n check exit 0` with nothing printed before it. No commit.

7. Stop and delete the throwaway server (skip if you used a server you did not start):

   ```bash
   su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1615x/data -m fast stop' 2>&1 | tail -2; rm -rf /var/tmp/pg1615x
   ```

   Expected: `server stopped`.

8. Write the report (§9), set `Status: review` and commit "1615 step 8".

## 5. Do not touch

`App/app/` (no Python application change: the Python page stays as it is and keeps serving production), `App/tests/conftest.py`, `go/internal/hostweb/` (layout, catalogs), `go/internal/session/`, `go/internal/web/privacy/handler.go`, `handler_test.go`, `store_test.go`, `testdata/privacy_requests_golden.json`, `go/internal/web/exports/` (another thread), `go/cmd/ubyhost-web/main.go` and every other `register_*.go`, `go.mod`, `go.sum`, Caddy, compose and env files, `docs/context/*`, and every file not in §3. AGENTS.md rules that apply: 2, 3, 4, 5, 8, 11.

## 6. Commands

Exactly the commands of §4 (steps 0, 1, 2, 3, 5, 6). Never the full suite, never `go test ./...`, never `pytest tests`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 10 files, and step 2 printed the stated `store.go` hash.
- [ ] Step 3 printed nothing.
- [ ] Step 5 printed two `ok` lines and each of the 6 named tests printed `--- PASS`; the SKIP count is `0`.
- [ ] Step 6 printed `3 passed`, no skipped test, and `i18n check exit 0`.
- [ ] `git log --oneline --grep='^1615 step' | tail -5` lists the commits of steps 1, 2 and 8, and `git show --stat --format=%h <hash>` of each lists only paths of §3.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or `App/app/` file changed; nothing was pushed.
- [ ] UI: no screenshot (the page is not served; the UX gate cannot run on Go pages yet, D5). The report says so.

## 8. Stop and ask

Stop, and write the report, if:

- a check, hash or file count of step 0, 1 or 2 is not as stated;
- a test fails twice (read the last 30 lines, fix nothing in the sidecar files yourself: report);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1615-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git log --oneline --grep='^1615 step' | tail -10`, then one `git show --stat --format=%h <hash> | tail -20` per commit).
2. Each command, with the last 5 lines of its output, and the SKIP count of step 5.
3. §7 ticked.
4. Deviations, and the known differences D1 to D5 of §2.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `page.go` (login first, then the list for `h.Workspace.ID` only; a database error is the 500 text, never a partial page) and `templates/privacy_requests.tmpl` against `App/app/templates/privacy_requests.html` (every field name, `action` and the CSRF field must match the two POST handlers of 1370; the outcome note is an attribute value and must stay auto-escaped). `page_test.go` must keep `visibleLines` in step with `visible_lines` in the golden script.

## Owner steps

Nothing is switched on by this brief. After the PR with this brief is merged and deployed:

1. Check first whether `/privacy-requests` is already in `UBYHOST_GO_PATHS` on the server (`grep UBYHOST_GO_PATHS .env` in the app folder). If it is (it should not be: brief 1370 said to wait for this page), production has been answering the list page with Go's 405 since then: either remove it now (`caddy-validate.sh`, `docker compose up -d caddy`) or leave it, as this deploy fixes it.
2. UX gate before the switch (AGENTS.md rule 10, the orchestrator's job, not yours): once a Go-served build can be screenshotted (brief 1412 is paused for lack of a staging server), run `test_layout_lint_browser.py` against it for `/privacy-requests` (a host with requests and one without), open the 390, 768 and 1280 px screenshots and write what was seen in the PR.
3. Then add both entries together, `/privacy-requests` and `/privacy-requests/*`, to `UBYHOST_GO_PATHS` (space-separated, double quotes, as in `docs/ENVIRONMENT.md`), run `caddy-validate.sh`, `docker compose up -d caddy`. Never one without the other: GET and POST share `/privacy-requests` (Caddy routes by path, not method), and the list's forms post to `/privacy-requests/<id>`. Python serves no other method on these paths.
4. Check without writing anything (production holds real data): open `/privacy-requests` signed in as yourself and see the same requests, in the same order, as before the switch; `curl -sI https://<your domain>/privacy-requests` while signed out answers `303` to `/login`. Do not record a test request there.
5. Rollback: remove both entries from `UBYHOST_GO_PATHS`, `caddy-validate.sh`, `docker compose up -d caddy`. The Python routes stay until a later removal PR after one clean production week.
6. Coordinator lines (send to the orchestrator): `docs/plans/go-full-move-remaining.md` sections 3 and 4: "Privacy request pages 3 / 3" and the `/privacy-requests` collision row removed; test-map row for `go/internal/web/privacy/**`: `go test ./internal/web/privacy/ ./cmd/ubyhost-web/` (database tests need `UBYHOST_TEST_DATABASE_URL`) and from `App/` `pytest tests/test_go_privacy_requests.py tests/test_go_privacy_requests_page.py`.
