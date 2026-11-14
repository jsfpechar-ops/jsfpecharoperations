# 1608: Go data exports, part 4: the archive page

Status: review
Depends on: 1607 | Base commit: none (one big PR mode: the branch that is checked out) | Branch: the current one
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** The owner wants one big pull request for the whole Go port. You work on the branch that is checked out now. Never create a branch, never push, never open a PR. After each step that changes a file, commit with the message `1608 step k` (k is the step number) and nothing else in the first line; end the message with the two trailer lines from the session reminder if one is given. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1608 step'` and `git show --stat` on those commits.

## 1. Objective

Port `GET /settings/archived`: the page that lists the workspace's archived stays, properties, house-book entries and legal entities with their restore buttons, with its template inside the Go host layout.

## 2. Context

Rules (AGENTS.md): 1 filing is not touched; 2 privacy: no new personal-data field and no outbound request, the exports contain the columns Python exports; 3 test data is made up (`@example.test`, test-only secrets and keys); 4 no new dependency (`go.mod` and `go.sum` stay as they are); 5 plain PostgreSQL through pgx with the Python SQL; 8 never push to `main`; 11 Go first: the only `App/` files are golden scripts and their parity tests, which go-first.md allows.

**PR text (hard rule 2):** no new outbound request and no new personal-data field.

**All code is pre-written, compiled and tested.** Sidecars are `docs/tasks/1608-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Write nothing outside §3. A file marked "replace" is replaced by the plain `cp` of step 1; there is nothing to merge, and step 0 checks by hash that it is the version this brief expects.

**The thread (briefs 1605 to 1609).** Port the last five routes of `App/app/routes/exports.py` into the existing Go package `go/internal/web/exports` (package `exports`, briefs 1320 and 1321 ported the other 8 of its 13 routes). Nothing routes to them until the owner adds the paths to `UBYHOST_GO_PATHS`.

| Brief | Route (method path, Python function) | Adds |
|---|---|---|
| 1605 | `GET /guests/{guest_id}/form.pdf` (guest_form_pdf, exports.py 94-113) | `form_pdf.go` (the port of `housebook.registration_form_pdf`), its golden script, the shared test set-up `more_env_test.go` |
| 1606 | `GET /housebook/pdfs.zip` (housebook_pdfs_download, 380-416) | `housebook_zip.go`; `housebook.go` replaced (shared house-book query); the route golden `exports_routes_golden` for 1606 to 1609 |
| 1607 | `POST /settings/workspace-export` (settings_workspace_export, 418-446) | `workspace.go` with the exported API `BuildWorkspaceZip` (for brief 1510) |
| 1608 | `GET /settings/archived` (settings_archived_view, 448-537) | `archived.go`, `templates/archived.tmpl`; `hostweb/layout` gains `Page.BodyAlerts` and the `host_alerts` func |
| 1609 | `POST /settings/purge-expired` (purge_expired_records, 539-571) | `purge.go`; `retention.RunAs`; `photosweep.PurgeStalePhotos` and `PurgeSubmissionPayloads` for one workspace |

**Order:** 1605, 1606, 1607, 1608, 1609, each `Depends on` the one before. Five files (`routes.go`, `i18n_keys.txt`, `i18n.json`, `routes_inventory_test.go`, `go/cmd/ubyhost-web/register_web_exports_test.go`) are named by all five briefs: each brief replaces them with the version for its stage (a plain `cp`, nothing to merge), so the order above is the only valid one. `register_web_exports.go` already mounts every pattern of `exports.Routes`; it is not changed.

Caddy routes by path; in `UBYHOST_GO_PATHS` a `*` in the middle of a path never crosses `/`. The entries of this thread: `/guests/*/form.pdf` (1605), `/housebook/pdfs.zip` (1606), `/settings/workspace-export` (1607), `/settings/archived` (1608), `/settings/purge-expired` (1609). Each path has one method and none collides with a Go pattern of another package. The writer could not read the server's `UBYHOST_GO_PATHS` and assumes none of them (and no `/settings*` or `/guests/*` prefix) is in it; if one is, that route goes live the moment its brief deploys.

**Every handler** starts as briefs 1320/1321 do: `Cache-Control: no-store, private`, then for a POST `hostweb.CSRF` (missing or bad token: `/login?notice=form_expired`), then `hostweb.Login` (signed out: `/login?next=<path>`). The host is `h.Workspace.ID` (Python `access.owner_id`); audit rows carry the signed-in user and the impersonating admin (Python `db.set_current_actor`). Python lists `/settings` in `_READ_ONLY_OPEN_PREFIXES`, so the two POST routes call `hostweb.Login` with the method masked to GET, as billing did for `/predplatne` (finding F1).

**Known differences from Python (not fixed here, listed in every report):**

- E1 (F1). `hostweb.Login` redirects every POST of a paused workspace to `/predplatne?paused=1`; Python exempts `/settings`. The two POST routes of this thread mask the method to GET for `hostweb.Login` only (`deps.beginPost`, brief 1607), so a paused workspace still exports and purges, as in Python. Other Go areas that post under an exempt prefix keep the gap.
- E2. A non-integer guest id (`/guests/abc/form.pdf`) answers Go's `404`; Python answers FastAPI's JSON `422`.
- E3. A wrong method answers Go's mux `405` (plain text); Python answers JSON `{"detail":"Method Not Allowed"}`.
- E4. The workspace zip writes the guest forms in guest-id order (`ORDER BY g.id`); Python leaves the order to the database. The entries and their bytes are the same; the test compares the workspace zip by entry name.
- E5. A signature image is decoded by Go's `image` package (PNG, JPEG, GIF). Another format that PIL reads (WebP, BMP, TIFF) gets the "no image" path where Python would draw it. The signature pad stores PNG.
- E6. With `UBYHOST_DATA_DIR` unset, the purge deletes nothing and answers `500`; Python would look for photos under its default directory (compose sets `/data`).
- E7. The house-book PDF zip is built in memory (at most 100 forms); Python writes it to a temporary file. The workspace zip is written to a temporary file in both (the Go container has `mem_limit 128m`).
- E8. Zip entry times are the request clock in Go (`at.Local()`); Python stamps the time each entry is written. Not compared.
- E9. `html/template` escapes some characters in attributes differently from Jinja (`+` as `&#43;`); the golden pages contain none, so `<main>` is byte-equal to Python's.
- E10. The retention windows `UBYHOST_AUDIT_RETENTION_DAYS`, `UBYHOST_ALERT_RETENTION_DAYS`, `UBYHOST_RATE_LIMIT_RETENTION_HOURS` and `UBYHOST_RETENTION_NOTICE_DAYS` are not passed to the Go container, so Go uses the defaults; if the server's `.env` sets one, the Go purge uses a different window (owner step in 1609).

**What this brief ports, with the Python lines:**

| Go | Python | What it does |
|---|---|---|
| `ArchivedHandler`, `loadArchived` | `routes/exports.py` `settings_archived_view` 448-537 | `d.begin`; `type` (last value; not in `all`, `stays`, `properties`, `housebook`, `entities`: `all`); the four counts (owner via `IS NOT DISTINCT FROM`, as `db.null_safe_eq`) and the lists of the type; house-book rows are `housebook_archived_rows` with every field decrypted (a broken key is a `500`) |
| `renderArchived`, `templates/archived.tmpl` | `templates/settings_archived.html` | the back header (`title.rsplit(' ', 1)`), the pills with counts, the empty state, the four tables with restore forms (`return_to` is this page with its type), `date_cz` dates |
| `layout.Page.BodyAlerts`, func `host_alerts` (`hostweb/layout`, replaced) | `{% include "_host_alerts.html" %}` in a v2 page body | the alert stack the base layout would show, written where the page asks for it; pages that do not set `BodyAlerts` are unchanged (`TestGoldenMatchesPython` of the layout still passes) |

**Template rules.** Rule 7 (browser and geometry tests) and the UX gate (rule 10) cannot run on Go pages yet: the browser tests drive the Python app, and the page is dormant until the owner adds its path. The page is pinned instead by the golden: `<main>` of 12 cases in English, Czech and Vietnamese is byte-equal to Python's (whitespace folded), including the alert inside the body (`TestArchivedPageAlertsOnce`: once on the page, inside `<main>`). The UX gate runs on staging when the path is switched (owner step). The restore forms carry no `_csrf` field, as in Python.

**Pinned (golden `arch_`, 12 cases):** signed out; `all`, `stays`, `properties`, `housebook`, `entities` of workspace 1; `?type=bogus&type=entities` is `entities`; the empty states of workspace 2 (also in Vietnamese); the broken-key workspace is a `500` for `all` and a `200` for `stays` (no house-book row is read).

**Audit rows:** none (a read).

**Verified by the brief writer** (fresh throwaway worktree of `origin/go-wave3` at 859d114d5; the sidecars of briefs 1605, 1606, 1607, 1608 copied in order exactly as their step 1 does, then exactly the commands of §4): every `sha256sum` line `OK`, step 2 printed nothing, step 4 printed only `ok` lines on PostgreSQL 16, every named test `--- PASS` with 0 `SKIP`, and the Python run `passed` with 0 skipped (Python 3.13 venv with `App/requirements.txt`). Not run: any browser test (the Go pages are dormant).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/exports/archived.go` | create | `ArchivedHandler`, `loadArchived`, `renderArchived`, `dateCZ` |
| `go/internal/web/exports/templates/archived.tmpl` | create | the port of `settings_archived.html` |
| `go/internal/web/exports/archived_test.go` | create | `TestArchivedPageMatchesPython`, `TestArchivedPageAlertsOnce` |
| `go/internal/hostweb/layout/layout.go` | replace | `Page.BodyAlerts`; `bodyAlertStack` factored out of `buildView` |
| `go/internal/hostweb/layout/funcs.go` | replace | the `host_alerts` template func |
| `go/internal/web/exports/routes.go` | replace (this version holds the routes of this stage) | `Routes` lists the 12 ported routes |
| `go/internal/web/exports/i18n_keys.txt`, `go/internal/web/exports/i18n.json` | replace | the catalog keys of this stage; `i18n.json` is `App/scripts/go_host_i18n.render` of the keys file, as `exports_golden.py` writes it |
| `go/internal/web/exports/routes_inventory_test.go` | replace (created by 1605) | `TestExportRoutesInventory`: `Routes` has exactly the 12 patterns |
| `go/cmd/ubyhost-web/register_web_exports_test.go` | replace (created by 1605) | `TestExportRoutesRegistered`: the 12 routes reach their patterns on the web mux |
| `docs/tasks/1608-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1608-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git log --oneline --grep='^1607 step' | tail -3` prints at least one line (brief 1607 is in this branch).
   - `printf '%s\n' 'bf7852b2fecb333634f7940354e4483213c5fb882ab32e68b1c22d1b6ee5551a  go/internal/hostweb/layout/layout.go' '3387fae1dcc67afdbfa9955ccaea96855a2c1d47d4b076cbf4d11458b921c075  go/internal/hostweb/layout/funcs.go' '63b075548781937e72e7be172f26d00b0a65cb94b8a754f62344ed212baa270b  go/internal/web/exports/routes.go' | sha256sum -c - 2>&1 | tail -5` prints `: OK` for each of the 3 files (they are as this brief expects before it replaces them).
   - `ls go/internal/web/exports/archived.go 2>&1 | tail -1` says "No such file" (nothing of this brief is there yet).
   - `find docs/tasks/1608-files -name '*.txt' | wc -l | tail -1` prints `10`.
   If only `layout.go` or `funcs.go` fails the hash, another brief changed the layout since this one was written: STOP (§8), do not merge by hand.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1608-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -15
   bfc058bcd9dbdb4b76e248dd7ebf85f1bfe20f938ced6e415181a681c118ffcb  go/cmd/ubyhost-web/register_web_exports_test.go
   dded61aa7936a01118127b2aac59f7bb2f6444c9c451cb3d975cb87b6028bc27  go/internal/hostweb/layout/funcs.go
   c7df5d34599b600e2a4d0668b680568d1394aceb6655a781e9c41123fc057f79  go/internal/hostweb/layout/layout.go
   e7dc536d89e1283a5a1476f51a72a104364e8f52914dd01c068241cdd0f04c90  go/internal/web/exports/archived.go
   faae767b92e3c2e31c43f749dc8031a6f31c8c9758fedaf53c05c6df87720ad2  go/internal/web/exports/archived_test.go
   bdd0a2decab9aa9b0e5ab16047a72c9477c12cdc2432b747c9073f0308307822  go/internal/web/exports/i18n.json
   c22a08b03d91be8af3052c908f310b6d9057db318e63fa0e3075a5272f3893cd  go/internal/web/exports/i18n_keys.txt
   fe2496bcce3d998a6407699b3e8ef5f1cd27cea24ef28df92b1146ce34845d4a  go/internal/web/exports/routes.go
   7dba9ee9d15837db99ad2766ef3c43dcd17d1be4f6fd532db8c51289da93b74d  go/internal/web/exports/routes_inventory_test.go
   cd757f5f67d365a91dc77768a7df5515bde028e03cad6bba36fda1d31b535458  go/internal/web/exports/templates/archived.tmpl
   EOF
   ```

   Every line must end with `: OK` (10 lines). Then commit "1608 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/exports internal/hostweb internal/retention internal/photosweep cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/exports/ ./cmd/ubyhost-web/ ./internal/hostweb/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). No commit (nothing changed).

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1608 && chown postgres /var/tmp/pg1608 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1608/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1608/data -o "-p 55708 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1608" -l /var/tmp/pg1608/log -w start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55708/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (from `go/`, then `App/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55708/postgres go test ./internal/web/exports/ ./cmd/ubyhost-web/ ./internal/hostweb/... -count=1 2>&1 | tail -30
   ```

   Expected: 4 `ok` lines, one per package, and nothing else. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55708/postgres go test ./internal/web/exports/ ./cmd/ubyhost-web/ ./internal/hostweb/layout/ -count=1 -v -run '^TestExportRoutesInventory$|^TestExportRoutesRegistered$|^TestArchivedPageMatchesPython$|^TestArchivedPageAlertsOnce$|^TestGoldenMatchesPython$|^TestAlertPresentation$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -40
   ```

   Expected: one `--- PASS` line for each of the 6 tests (TestExportRoutesInventory, TestExportRoutesRegistered, TestArchivedPageMatchesPython, TestArchivedPageAlertsOnce, TestGoldenMatchesPython, TestAlertPresentation), and `ok` lines; no `--- SKIP`, no `--- FAIL`.

   Python (the golden freshness checks; no Python application file changes). If `App/.venv/bin/python` exists:

   ```bash
   cd App && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55708/postgres .venv/bin/python -m pytest tests/test_go_exports.py -q --tb=short -rs 2>&1 | tail -8
   ```

   Expected: `3 passed`, no `skipped`, no `failed`. If `App/.venv` does not exist, write "Python: CI only" in the report and go on (do not create a venv).

5. Stop and delete the throwaway server (skip if you used a server you did not start):

   ```bash
   su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1608/data -m fast stop' 2>&1 | tail -2; rm -rf /var/tmp/pg1608
   ```

   Expected: `server stopped`.

6. Write the report (§9), set `Status: review` and commit "1608 step 6".

## 5. Do not touch

`go/internal/session/`, `go/internal/secure/`, `go/internal/pdf/`, `go/internal/deadlines/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web_exports.go` and every other `register_*.go`, the files of `go/internal/web/exports/` that briefs 1320 and 1321 created and this brief does not name (`exports.go`, `guest_json.go`, `stays.go`, `submissions.go`, `exports_test.go`, `testdata/exports_golden.json`), `App/app/` (no Python application file), `App/tests/conftest.py`, `App/scripts/exports_golden.py`, `deploy/` (Caddy, compose, env), `docs/context/*`, and every file not in §3. AGENTS.md rules that apply: 2 (privacy), 3 (no real data in tests), 4 (no new dependency), 5 (plain PostgreSQL through pgx), 8 (never push to `main`), 11 (Go first).

## 6. Commands

Exactly the commands of §4 (steps 1, 2, 4, 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 10 files.
- [ ] Step 2 printed nothing.
- [ ] Step 4 printed 4 (first command) and 3 (second command) `ok` lines and each of the 6 named tests printed `--- PASS` (none `SKIP`, none `FAIL`); the Python run printed only `passed` (or the report says "Python: CI only").
- [ ] `git log --oneline --grep='^1608 step' | tail -5` lists at least the step 1 commit, and `git show --stat --format=%h <that hash> | tail -20` lists only paths of §3.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed.
- [ ] UI: rule 7 and the UX gate cannot run on Go pages yet (see §2); the report says so and lists the owner step. No screenshot.

## 8. Stop and ask

Stop, and write the report, if:

- a check, hash or file count of step 0 or step 1 is not as stated;
- a test fails twice (read the last 30 lines, fix nothing in the sidecar files yourself: report);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1608-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git log --oneline --grep='^1608 step' | tail -10`, then one `git show --stat --format=%h <hash> | tail -20` per commit).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `layout.go` and `funcs.go`: a page without `BodyAlerts` must render byte-identical (the layout golden pins it); with `BodyAlerts` the stack is built once and only when the nav shows. Read `archived.tmpl` against `settings_archived.html`: every value escaped, the restore `return_to` keeps the type.

## Owner steps

When the thread is merged and deployed: add `/settings/archived` to `UBYHOST_GO_PATHS`, then run the UX gate on staging for this page (390/768/1280 screenshots, as brief 1412 did for the other Go pages). `BodyAlerts` is also the fix for any other v2 page whose body includes `_host_alerts.html`.
