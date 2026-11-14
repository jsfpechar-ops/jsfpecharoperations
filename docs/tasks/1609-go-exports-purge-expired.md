# 1609: Go data exports, part 5: the purge button

Status: todo
Depends on: 1608 | Base commit: none (one big PR mode: the branch that is checked out) | Branch: the current one
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** The owner wants one big pull request for the whole Go port. You work on the branch that is checked out now. Never create a branch, never push, never open a PR. After each step that changes a file, commit with the message `1609 step k` (k is the step number) and nothing else in the first line; end the message with the two trailer lines from the session reminder if one is given. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1609 step'` and `git show --stat` on those commits.

## 1. Objective

Port `POST /settings/purge-expired`: the Settings button that deletes, for the signed-in workspace only, what the retention schedule no longer covers. **It deletes data.** The steps are exactly Python's, in Python's order, each one the Go port that its own golden pins, and every refusal and every deleted row is pinned by tests.

## 2. Context

Rules (AGENTS.md): 1 filing is not touched; 2 privacy: no new personal-data field and no outbound request, the exports contain the columns Python exports; 3 test data is made up (`@example.test`, test-only secrets and keys); 4 no new dependency (`go.mod` and `go.sum` stay as they are); 5 plain PostgreSQL through pgx with the Python SQL; 8 never push to `main`; 11 Go first: the only `App/` files are golden scripts and their parity tests, which go-first.md allows.

**PR text (hard rule 2):** no new outbound request and no new personal-data field.

**All code is pre-written, compiled and tested.** Sidecars are `docs/tasks/1609-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Write nothing outside §3. A file marked "replace" is replaced by the plain `cp` of step 1; there is nothing to merge, and step 0 checks by hash that it is the version this brief expects.

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
| `PurgeExpiredHandler` | `routes/exports.py` `purge_expired_records` 539-571 | `d.beginPost` (CSRF, login with the method masked: E1); owner required; `UBYHOST_DATA_DIR` unset: `500`, nothing deleted (E6); then the three steps below in order; a failed step is a `500` after the steps before it (as the Python exception); `303` to `/settings` with `msg` `flash.settings.purged` (`parts` joined by ` and `, English in every language as in Python) or `flash.settings.nothing_to_purge` |
| step 1: `retention.RunAs(ctx, pool, cfg, prague today, now, &owner, &actor)` | `retention.run(claim.prague_today(), dry_run=False, owner_user_id=owner)` (`App/app/retention.py`) | every owner-scoped retention step in apply mode, whatever `UBYHOST_RETENTION_AUTOPURGE` says (the button forces it); `RunAs` is `Run` plus the request's actor in the audit rows; `Run` calls it with `nil`, so the global job is unchanged (`TestRunMatchesPythonGolden` still passes) |
| step 2: `photosweep.PurgeStalePhotos` | `passport_photos.purge_stale(owner_user_id=owner)` | the owner's guests that are verified, checked in 7 days or more before today, or uploaded 30 days or more before today: photo file deleted, `passport_photo_at` cleared; orphan files are left for the global sweep; audit `retention_delete` `passport_photos` |
| step 3: `photosweep.PurgeSubmissionPayloads` | `reporting.purge_submission_payloads(owner_user_id=owner)` | the owner's settled submissions older than 90 days: `request_xml`, `request_xml_enc`, `response_xml` set to NULL; audit `submission_payload_purge` (actor the signed-in user) and `retention_delete` `ubyport_xml` |

**What is deleted, pinned (golden `purge_`, 7 cases, clock frozen at 2026-11-13 12:00 UTC):**

| Request | Guests | Photo marks | Envelopes kept | Reservations | Photo files | Message |
|---|---|---|---|---|---|---|
| before | 120 | 2 | 4 | 11 | `11.jpg.enc`, `14.png`, `30.jpg` | |
| signed out, no CSRF | unchanged | unchanged | 4 | 11 | unchanged | `/login?next=...`, `/login?notice=form_expired` |
| workspace 2 | 120 | 2 | 3 | 11 | unchanged | `Deleted 1 submission envelope(s) no longer needed.` |
| workspace 1 | 118 (guests 30 and 31 of 2019 gone) | 0 | 1 | 10 | none | `Deleted 2 guest record(s) past the retention period and 2 passport image(s) no longer needed and 2 submission envelope(s) no longer needed.` |
| workspace 1 again (Czech), workspace 5, supporting admin | unchanged | 0 | 1 | 10 | none | `flash.settings.nothing_to_purge` |

Invoices stay 2 (none older than 10 years). Every audit row is compared with Python's: the `retention_delete` line of each of the 21 retention classes, `retention_run` with the counts, `retention_purge` `deleted 2 guest record(s) whose stay ended before 2020-01-01` (actor the signed-in user), `passport_photos`, `submission_payload_purge`, `ubyport_xml`, with the owner, actor and impersonator ids (the supporting admin: actor 3, impersonator 3). `TestPurgeExpiredRefusals`: a GET (`405`), signed out, no CSRF and `UBYHOST_DATA_DIR` unset change no row, no file and write no audit row. `TestPurgeExpiredPausedWorkspace`: a paused workspace (billing on) still purges (E1).

**Verified by the brief writer** (fresh throwaway worktree of `origin/go-wave3` at 859d114d5; the sidecars of briefs 1605, 1606, 1607, 1608, 1609 copied in order exactly as their step 1 does, then exactly the commands of §4): every `sha256sum` line `OK`, step 2 printed nothing, step 4 printed only `ok` lines on PostgreSQL 16, every named test `--- PASS` with 0 `SKIP`, and the Python run `passed` with 0 skipped (Python 3.13 venv with `App/requirements.txt`). Not run: any browser test (the Go pages are dormant).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/exports/purge.go` | create | `PurgeExpiredHandler`, `purgeParts` |
| `go/internal/web/exports/purge_test.go` | create | `TestPurgeExpiredMatchesPython`, `TestPurgeExpiredRefusals`, `TestPurgeExpiredPausedWorkspace` |
| `go/internal/retention/retention.go` | replace (created by the retention thread) | `Actor`, `RunAs`; `Run` calls `RunAs(..., nil)` |
| `go/internal/photosweep/owner.go` | create | `PurgeStalePhotos`, `PurgeSubmissionPayloads` for one workspace |
| `go/internal/web/exports/routes.go` | replace (this version holds the routes of this stage) | `Routes` lists the 13 ported routes |
| `go/internal/web/exports/i18n_keys.txt`, `go/internal/web/exports/i18n.json` | replace | the catalog keys of this stage; `i18n.json` is `App/scripts/go_host_i18n.render` of the keys file, as `exports_golden.py` writes it |
| `go/internal/web/exports/routes_inventory_test.go` | replace (created by 1605) | `TestExportRoutesInventory`: `Routes` has exactly the 13 patterns |
| `go/cmd/ubyhost-web/register_web_exports_test.go` | replace (created by 1605) | `TestExportRoutesRegistered`: the 13 routes reach their patterns on the web mux |
| `docs/tasks/1609-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1609-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git log --oneline --grep='^1608 step' | tail -3` prints at least one line (brief 1608 is in this branch).
   - `printf '%s\n' 'ac304e25c0583a8413444f2ab05a5415f8c18a26cd6b507e56b42a1972b3c9e0  go/internal/retention/retention.go' 'fe2496bcce3d998a6407699b3e8ef5f1cd27cea24ef28df92b1146ce34845d4a  go/internal/web/exports/routes.go' | sha256sum -c - 2>&1 | tail -5` prints `: OK` for each of the 2 files (they are as this brief expects before it replaces them).
   - `ls go/internal/web/exports/purge.go 2>&1 | tail -1` says "No such file" (nothing of this brief is there yet).
   - `ls go/internal/photosweep/owner.go 2>&1 | tail -1` says "No such file" (nothing of this brief is there yet).
   - `find docs/tasks/1609-files -name '*.txt' | wc -l | tail -1` prints `9`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1609-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -15
   d7bdd3ba08ee8143f294d433e0658d676beb737b3ca6984680a26cd7f9f593b3  go/cmd/ubyhost-web/register_web_exports_test.go
   2a9c07f4a1ea245a77b3c31c1a6b9a18278e67dbcec8a9ef8bb481460cb0f1fd  go/internal/photosweep/owner.go
   1080010172c58f9fdcc34dade6698ee9429f21cd15ea8381314ea796e081d9cb  go/internal/retention/retention.go
   eaed416717554bc7ffbf329e0687edff569d05ac9ca30acf0387d68f0d1dfb9b  go/internal/web/exports/i18n.json
   a719ff90c5e156cd933b275b9c158155236f2e61541502dd90630c577d44b223  go/internal/web/exports/i18n_keys.txt
   49eb29f55e91e9da187162e77f00547ad1f7a080527c8563de673852881527e5  go/internal/web/exports/purge.go
   6ff8a61be1e9640a07ae6ac5655bbe826a8a7b5b3f669a03ada61bc53b9efe21  go/internal/web/exports/purge_test.go
   c9c90ec95c4a536ba0ab2b74828ba785b5a9c79caf610de391b560a5762d847e  go/internal/web/exports/routes.go
   aff29b311eac6f302695b48e57be1f7bfa68182337aa73fb1151f0729e6691c3  go/internal/web/exports/routes_inventory_test.go
   EOF
   ```

   Every line must end with `: OK` (9 lines). Then commit "1609 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/exports internal/hostweb internal/retention internal/photosweep cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/exports/ ./cmd/ubyhost-web/ ./internal/retention/ ./internal/photosweep/ 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). No commit (nothing changed).

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1609 && chown postgres /var/tmp/pg1609 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1609/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1609/data -o "-p 55709 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1609" -l /var/tmp/pg1609/log -w start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55709/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (from `go/`, then `App/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55709/postgres go test ./internal/web/exports/ ./cmd/ubyhost-web/ ./internal/retention/ ./internal/photosweep/ -count=1 2>&1 | tail -30
   ```

   Expected: 4 `ok` lines, one per package, and nothing else. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55709/postgres go test ./internal/web/exports/ ./cmd/ubyhost-web/ ./internal/retention/ ./internal/photosweep/ -count=1 -v -run '^TestExportRoutesInventory$|^TestExportRoutesRegistered$|^TestPurgeExpiredMatchesPython$|^TestPurgeExpiredRefusals$|^TestPurgeExpiredPausedWorkspace$|^TestRunMatchesPythonGolden$|^TestApplyWithoutDataDirDeletesNoGuest$|^TestRunMatchesPython$|^TestRunNeedsDataDir$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -40
   ```

   Expected: one `--- PASS` line for each of the 9 tests (TestExportRoutesInventory, TestExportRoutesRegistered, TestPurgeExpiredMatchesPython, TestPurgeExpiredRefusals, TestPurgeExpiredPausedWorkspace, TestRunMatchesPythonGolden, TestApplyWithoutDataDirDeletesNoGuest, TestRunMatchesPython, TestRunNeedsDataDir), and `ok` lines; no `--- SKIP`, no `--- FAIL`.

   Python (the golden freshness checks; no Python application file changes). If `App/.venv/bin/python` exists:

   ```bash
   cd App && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55709/postgres .venv/bin/python -m pytest tests/test_go_exports.py tests/test_go_exports_routes.py -q --tb=short -rs 2>&1 | tail -8
   ```

   Expected: `5 passed`, no `skipped`, no `failed`. If `App/.venv` does not exist, write "Python: CI only" in the report and go on (do not create a venv).

5. Stop and delete the throwaway server (skip if you used a server you did not start):

   ```bash
   su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1609/data -m fast stop' 2>&1 | tail -2; rm -rf /var/tmp/pg1609
   ```

   Expected: `server stopped`.

6. Write the report (§9), set `Status: review` and commit "1609 step 6".

## 5. Do not touch

`go/internal/session/`, `go/internal/secure/`, `go/internal/pdf/`, `go/internal/deadlines/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web_exports.go` and every other `register_*.go`, the files of `go/internal/web/exports/` that briefs 1320 and 1321 created and this brief does not name (`exports.go`, `guest_json.go`, `stays.go`, `submissions.go`, `exports_test.go`, `testdata/exports_golden.json`), `App/app/` (no Python application file), `App/tests/conftest.py`, `App/scripts/exports_golden.py`, `deploy/` (Caddy, compose, env), `docs/context/*`, and every file not in §3. AGENTS.md rules that apply: 2 (privacy), 3 (no real data in tests), 4 (no new dependency), 5 (plain PostgreSQL through pgx), 8 (never push to `main`), 11 (Go first).

## 6. Commands

Exactly the commands of §4 (steps 1, 2, 4, 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 9 files.
- [ ] Step 2 printed nothing.
- [ ] Step 4 printed 4 (first command) and 4 (second command) `ok` lines and each of the 9 named tests printed `--- PASS` (none `SKIP`, none `FAIL`); the Python run printed only `passed` (or the report says "Python: CI only").
- [ ] `git log --oneline --grep='^1609 step' | tail -5` lists at least the step 1 commit, and `git show --stat --format=%h <that hash> | tail -20` lists only paths of §3.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed.
- [ ] UI: not applicable (a redirect; the button is on `/settings/data`, still Python).

## 8. Stop and ask

Stop, and write the report, if:

- a check, hash or file count of step 0 or step 1 is not as stated;
- a test fails twice (read the last 30 lines, fix nothing in the sidecar files yourself: report);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- anything would run the purge against a database other than the throwaway test server;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1609-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git log --oneline --grep='^1609 step' | tail -10`, then one `git show --stat --format=%h <hash> | tail -20` per commit).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

This route deletes data. Read `purge.go`: no step may run before CSRF, login and the owner check; the data-dir check must come before step 1; the steps must be in Python's order and stop at the first error. Read `retention.go`'s diff: `Run` must behave exactly as before (`RunAs(..., nil)`), and the actor may only change the audit columns. Read `owner.go`: every query has `a.owner_user_id = $n`; no orphan-file step. Note: `photosweep` has two tests that skip as root (`TestRemoveFileFailsOnUnwritableDir`, `TestRunFailsOnReadOnlyPhotos`); they are not named here.

## Owner steps

When briefs 1605 to 1609 are merged and deployed (numbered, in this order):

1. Add the five paths to `UBYHOST_GO_PATHS` in the server's `.env`, separated by spaces, keeping what is there: `/guests/*/form.pdf /housebook/pdfs.zip /settings/workspace-export /settings/archived`, then restart with `docker compose up -d` in `deploy/lightsail`.
2. Do **not** add `/settings/purge-expired` yet. The Go container mounts `/data` read-only (`ubyhost-data:/data:ro`), so the photo step would fail with a `500` after the retention step already deleted rows. Add it only after (a) the Go `/data` mount is writable and (b) the retention job's dry-run counts of Go and Python matched on three mornings.
3. Before adding it: check that `.env` sets none of `UBYHOST_AUDIT_RETENTION_DAYS`, `UBYHOST_ALERT_RETENTION_DAYS`, `UBYHOST_RATE_LIMIT_RETENTION_HOURS`, `UBYHOST_RETENTION_NOTICE_DAYS` (`grep RETENTION .env`). If one is set, it must also be passed to the `ubyhost-go` service in `docker-compose.yml` first (a separate brief), or Go purges with a different window (E10).
4. Run the UX gate for `/settings/archived` on staging (brief 1608).
