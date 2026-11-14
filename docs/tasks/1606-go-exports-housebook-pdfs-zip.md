# 1606: Go data exports, part 2: the house-book PDF zip

Status: todo
Depends on: 1605 | Base commit: none (one big PR mode: the branch that is checked out) | Branch: the current one
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** The owner wants one big pull request for the whole Go port. You work on the branch that is checked out now. Never create a branch, never push, never open a PR. After each step that changes a file, commit with the message `1606 step k` (k is the step number) and nothing else in the first line; end the message with the two trailer lines from the session reminder if one is given. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1606 step'` and `git show --stat` on those commits.

## 1. Objective

Port `GET /housebook/pdfs.zip`: one signed registration form per house-book entry of the filter (at most 100) in one zip, for an inspection. Add the route golden that pins briefs 1606 to 1609 against the Python app on PostgreSQL.

## 2. Context

Rules (AGENTS.md): 1 filing is not touched; 2 privacy: no new personal-data field and no outbound request, the exports contain the columns Python exports; 3 test data is made up (`@example.test`, test-only secrets and keys); 4 no new dependency (`go.mod` and `go.sum` stay as they are); 5 plain PostgreSQL through pgx with the Python SQL; 8 never push to `main`; 11 Go first: the only `App/` files are golden scripts and their parity tests, which go-first.md allows.

**PR text (hard rule 2):** no new outbound request and no new personal-data field.

**All code is pre-written, compiled and tested.** Sidecars are `docs/tasks/1606-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Write nothing outside §3. A file marked "replace" is replaced by the plain `cp` of step 1; there is nothing to merge, and step 0 checks by hash that it is the version this brief expects.

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
| `HousebookPDFsHandler` | `routes/exports.py` `housebook_pdfs_download` 380-416 | `d.begin`; identity hidden: back to `/housebook` with `err` `flash.error.identity_hidden_export`; the entries of `housebook_rows(apartment, from, to, owner)` (`housebookGuests`, every field decrypted: a broken key is a `500`); none: `err` `flash.error.no_housebook_matches`; more than 100: `err` `flash.error.too_many_entries` with `count` and `limit`; audit `export_housebook_pdfs` `rows=<n>`; `attachment; filename="domovni-kniha-pdf-<YYYYMMDD>.zip"` |
| `housebookPDFsZip`, `pdfEntryName` | `housebook.build_housebook_pdfs_zip` 285-300, `_pdf_entry_name` 274-282 | deflated, one `registrationFormPDF` per row in row order; name `<stay from>-<surname>-<first name>` with non-word runs as `_`, cut to 96 characters, or `guest-<id>` |
| `housebookGuests`, `housebookCSV` (in `housebook.go`, replaced) | `housebook._housebook_sql`, `housebook_rows` | the query of `GET /housebook.csv` (brief 1321) moved into a function both routes use; `HousebookCSVHandler` is unchanged in behaviour (its golden still passes) |

**Route golden.** `App/scripts/exports_routes_golden.py` (new) seeds the rows of `exports_golden.py` plus a few made-up extras (2019 guests, 101 guests of workspace 5, legal entities, an archived property, invoices, stay-fee filings, an alert, a broken archived guest), freezes the clock at `2026-11-13T12:00:00+00:00` everywhere the routes read it, sends 48 requests to the Python app and writes `testdata/exports_routes_golden.json`: status, the compared headers, every audit row, zip entries (forms as `PDF`, other files as bytes), the archive page's `<main>`, and after each purge the database state and photo files. `routes_golden_test.go` replays a case prefix on the Go routes; this brief runs `form_` (11 cases) and `zip_` (11 cases); 1607 to 1609 run `ws_`, `arch_`, `purge_`. `App/tests/test_go_exports_routes.py` fails when Python changes and the golden was not rewritten (PostgreSQL only).

**Pinned:** the zip of workspace 1 has 13 entries in Python's order, from `2019-03-01-Old-Stay.pdf` to `2026-07-01-Paper-Adult.pdf`, with audit `rows=13`; `?apartment=6` gives `2026-06-01-Tab_Name-Q_uote.pdf`; workspace 5 (101 entries) is refused with `/housebook?err=Too%20many%20entries%20%28101%29%20for%20one%20download.%20Narrow%20the%20date%20or%20property%20filter%20to%20100%20or%20fewer.`; `TestPDFEntryName` pins `guest-7.pdf`, the 96-character cut and `O_Brien_Smith-Zoë.pdf`.

**Verified by the brief writer** (fresh throwaway worktree of `origin/go-wave3` at 859d114d5; the sidecars of briefs 1605, 1606 copied in order exactly as their step 1 does, then exactly the commands of §4): every `sha256sum` line `OK`, step 2 printed nothing, step 4 printed only `ok` lines on PostgreSQL 16, every named test `--- PASS` with 0 `SKIP`, and the Python run `passed` with 0 skipped (Python 3.13 venv with `App/requirements.txt`). Not run: any browser test (the Go pages are dormant).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/exports/housebook_zip.go` | create | `HousebookPDFsHandler`, `housebookPDFsZip`, `pdfEntryName` |
| `go/internal/web/exports/housebook.go` | replace (created by 1321) | adds `housebookGuests` and `housebookCSV`; `HousebookCSVHandler` uses them |
| `go/internal/web/exports/housebook_zip_test.go` | create | `TestPDFEntryName` |
| `go/internal/web/exports/routes_golden_test.go` | create | the replay; `TestFormRefusalsMatchPython`, `TestHousebookPDFsMatchPython` |
| `go/internal/web/exports/testdata/exports_routes_golden.json` | create | written by the golden script |
| `App/scripts/exports_routes_golden.py` | create | the route golden script |
| `App/tests/test_go_exports_routes.py` | create | the golden covers the five routes and is current |
| `go/internal/web/exports/routes.go` | replace (this version holds the routes of this stage) | `Routes` lists the 10 ported routes |
| `go/internal/web/exports/i18n_keys.txt`, `go/internal/web/exports/i18n.json` | replace | the catalog keys of this stage; `i18n.json` is `App/scripts/go_host_i18n.render` of the keys file, as `exports_golden.py` writes it |
| `go/internal/web/exports/routes_inventory_test.go` | replace (created by 1605) | `TestExportRoutesInventory`: `Routes` has exactly the 10 patterns |
| `go/cmd/ubyhost-web/register_web_exports_test.go` | replace (created by 1605) | `TestExportRoutesRegistered`: the 10 routes reach their patterns on the web mux |
| `docs/tasks/1606-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1606-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git log --oneline --grep='^1605 step' | tail -3` prints at least one line (brief 1605 is in this branch).
   - `printf '%s\n' '7e99e33f07e86a0a1bf955b99bcb9086e758dd746c04d65abb51c9138784b9c8  go/internal/web/exports/housebook.go' '98749b4d1e5235a71780a04bf4ccee7910b819e40c727ec27c88580fc8efd2ef  go/internal/web/exports/routes.go' | sha256sum -c - 2>&1 | tail -5` prints `: OK` for each of the 2 files (they are as this brief expects before it replaces them).
   - `ls go/internal/web/exports/housebook_zip.go 2>&1 | tail -1` says "No such file" (nothing of this brief is there yet).
   - `find docs/tasks/1606-files -name '*.txt' | wc -l | tail -1` prints `12`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1606-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -15
   7dd148f9fbc066acc52d9b34268f1f0d10842b4cd58b6b96c78ee7f3c7fb37c1  App/scripts/exports_routes_golden.py
   7b557c8f7b5c7ad927efdb824d46bffe4cc7e3703dd2b02b46e39cf5f54f6f02  App/tests/test_go_exports_routes.py
   7e0adb4f53f0556ddf3c0de636988012ecbe7d1c9547dee6329cc7589b4449d7  go/cmd/ubyhost-web/register_web_exports_test.go
   7b5d6bb5f0807c68e82cf3ccdd6a86ebfa7e268971b9db0708d77ef053163562  go/internal/web/exports/housebook.go
   61cc0aaa458047585f2805b8cdb05c5ed318979396bcbd52b7cbd7ce4d1662e6  go/internal/web/exports/housebook_zip.go
   4d3d4f732326b818372dffdcabf6c036ebd2b2a1e0610a9ab8ccfd095716a51c  go/internal/web/exports/housebook_zip_test.go
   65de447718d02cf37e8e01bfc7798089b641f4606d8b3e1c96c19457c30eaaa0  go/internal/web/exports/i18n.json
   826457c7fd59ec9067c4ce307298e7dcb670e1d7a997897bfb2772733877fd2c  go/internal/web/exports/i18n_keys.txt
   acf4c179ce52217aa824d004c50e8ecbefab750c23aa19145ff7e38b1aca4235  go/internal/web/exports/routes.go
   73801b7f21e21917c6ba0be4f40ef372ee04e030ae1c6168424cdd5f471471ab  go/internal/web/exports/routes_golden_test.go
   3432bd6806b503ebc43e4c404ec7d1ab9bfd9372668097cd38046bed5c27b16f  go/internal/web/exports/routes_inventory_test.go
   4e579137949c69fc22aee06b40479f4b99d6b2d40960176a7bffeb1a6eca448a  go/internal/web/exports/testdata/exports_routes_golden.json
   EOF
   ```

   Every line must end with `: OK` (12 lines). Then commit "1606 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/exports internal/hostweb internal/retention internal/photosweep cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/exports/ ./cmd/ubyhost-web/ 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). No commit (nothing changed).

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1606 && chown postgres /var/tmp/pg1606 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1606/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1606/data -o "-p 55706 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1606" -l /var/tmp/pg1606/log -w start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55706/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (from `go/`, then `App/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55706/postgres go test ./internal/web/exports/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
   ```

   Expected: 2 `ok` lines, one per package, and nothing else. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55706/postgres go test ./internal/web/exports/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestExportRoutesInventory$|^TestExportRoutesRegistered$|^TestPDFEntryName$|^TestFormRefusalsMatchPython$|^TestHousebookPDFsMatchPython$|^TestGoldenParity$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -40
   ```

   Expected: one `--- PASS` line for each of the 6 tests (TestExportRoutesInventory, TestExportRoutesRegistered, TestPDFEntryName, TestFormRefusalsMatchPython, TestHousebookPDFsMatchPython, TestGoldenParity), and `ok` lines; no `--- SKIP`, no `--- FAIL`.

   Python (the golden freshness checks; no Python application file changes). If `App/.venv/bin/python` exists:

   ```bash
   cd App && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55706/postgres .venv/bin/python -m pytest tests/test_go_exports_routes.py tests/test_go_exports.py tests/test_go_registration_form.py -q --tb=short -rs 2>&1 | tail -8
   ```

   Expected: `6 passed`, no `skipped`, no `failed`. If `App/.venv` does not exist, write "Python: CI only" in the report and go on (do not create a venv).

5. Stop and delete the throwaway server (skip if you used a server you did not start):

   ```bash
   su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1606/data -m fast stop' 2>&1 | tail -2; rm -rf /var/tmp/pg1606
   ```

   Expected: `server stopped`.

6. Write the report (§9), set `Status: review` and commit "1606 step 6".

## 5. Do not touch

`go/internal/session/`, `go/internal/secure/`, `go/internal/pdf/`, `go/internal/deadlines/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web_exports.go` and every other `register_*.go`, the files of `go/internal/web/exports/` that briefs 1320 and 1321 created and this brief does not name (`exports.go`, `guest_json.go`, `stays.go`, `submissions.go`, `exports_test.go`, `testdata/exports_golden.json`), `App/app/` (no Python application file), `App/tests/conftest.py`, `App/scripts/exports_golden.py`, `deploy/` (Caddy, compose, env), `docs/context/*`, and every file not in §3. AGENTS.md rules that apply: 2 (privacy), 3 (no real data in tests), 4 (no new dependency), 5 (plain PostgreSQL through pgx), 8 (never push to `main`), 11 (Go first).

## 6. Commands

Exactly the commands of §4 (steps 1, 2, 4, 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 12 files.
- [ ] Step 2 printed nothing.
- [ ] Step 4 printed 2 (first command) and 2 (second command) `ok` lines and each of the 6 named tests printed `--- PASS` (none `SKIP`, none `FAIL`); the Python run printed only `passed` (or the report says "Python: CI only").
- [ ] `git log --oneline --grep='^1606 step' | tail -5` lists at least the step 1 commit, and `git show --stat --format=%h <that hash> | tail -20` lists only paths of §3.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed.
- [ ] UI: not applicable (a zip, no template).

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

Write `docs/tasks/1606-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git log --oneline --grep='^1606 step' | tail -10`, then one `git show --stat --format=%h <hash> | tail -20` per commit).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read `housebook.go`'s diff: the query and the CSV bytes must be exactly those of 1321 (`TestGoldenParity` pins them); `HousebookPDFsHandler` must refuse before rendering any PDF and write the audit row only after the zip is complete.

## Owner steps

When the thread is merged and deployed: add `/housebook/pdfs.zip` to `UBYHOST_GO_PATHS` (brief 1609 lists them all).
