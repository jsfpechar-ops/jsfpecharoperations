# 1605: Go data exports, part 1: the signed registration form PDF

Status: review
Depends on: none (first brief of the thread; needs briefs 1320 and 1321, already in this branch) | Base commit: none (one big PR mode: the branch that is checked out) | Branch: the current one
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** The owner wants one big pull request for the whole Go port. You work on the branch that is checked out now. Never create a branch, never push, never open a PR. After each step that changes a file, commit with the message `1605 step k` (k is the step number) and nothing else in the first line; end the message with the two trailer lines from the session reminder if one is given. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1605 step'` and `git show --stat` on those commits.

## 1. Objective

Port `GET /guests/{guest_id}/form.pdf`: the signed registration form of one guest (the police form the host shows on inspection) as a PDF drawn with `go/internal/pdf`, the same drawing operations as Python's reportlab form. Add the test set-up that briefs 1606 to 1609 share.

## 2. Context

Rules (AGENTS.md): 1 filing is not touched; 2 privacy: no new personal-data field and no outbound request, the exports contain the columns Python exports; 3 test data is made up (`@example.test`, test-only secrets and keys); 4 no new dependency (`go.mod` and `go.sum` stay as they are); 5 plain PostgreSQL through pgx with the Python SQL; 8 never push to `main`; 11 Go first: the only `App/` files are golden scripts and their parity tests, which go-first.md allows.

**PR text (hard rule 2):** no new outbound request and no new personal-data field.

**All code is pre-written, compiled and tested.** Sidecars are `docs/tasks/1605-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Write nothing outside §3. A file marked "replace" is replaced by the plain `cp` of step 1; there is nothing to merge, and step 0 checks by hash that it is the version this brief expects.

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
| `GuestFormPDFHandler` | `routes/exports.py` `guest_form_pdf` 94-113 | `d.begin`; the guest of this workspace (`ownedGuestSQL`, every field decrypted: a field no key decrypts is a `500`); none: back to `/reservations` with `err` `flash.error.no_such_guest`; identity hidden (`access.identity_visible`: admin always, host in its own workspace always): `err` `flash.error.identity_hidden_export`; audit `export_registration_pdf` `guest_id=<id>`; `attachment; filename="registration-form-<id>.pdf"` |
| `registrationFormPDF`, `drawRegistrationForm` | `housebook.registration_form_pdf` 302-, `_draw_field` | A4 form: header, house, stay, guest fields, signature block (image, or the text of `reporting.signature_record`: own, signed for a child by an adult, exempt, imported) |
| `signatureRecord` | `reporting.signature_record` | the signed-for text `Signed by <first> <last> for <first> <last>, as <role>, <at>, wording <version>` (Python `None` printed as `None`) |
| `signatureImage` | `ImageReader(b64decode(...))` | the data URL's image re-encoded as PNG; undecodable: the no-image path (E5) |

**Golden.** `App/scripts/registration_form_golden.py` (new, a golden script: go-first.md allows it) runs `housebook.registration_form_pdf` on 9 made-up rows with `db.query_one` mocked and a recording canvas, and writes `testdata/registration_form_golden.json` (every draw operation: font, size, position, text, image box). `TestRegistrationFormMatchesPython` replays them on `go/internal/pdf` within 0.01 pt. `App/tests/test_go_registration_form.py` fails when the Python form changes and the golden was not rewritten (no database needed).

**Audit rows:** `export_registration_pdf`, detail `guest_id=<id>`, actor the signed-in username, `owner_user_id` the workspace, `actor_user_id` the signed-in user, `impersonator_user_id` the admin while supporting. `TestGuestFormPDFRoute` pins `[export_registration_pdf guest_id=11 owner@example.test 1 1 <nil>]` and, for the supporting admin, `... admin@example.test 1 3 3`; a broken key writes none.

**Shared test set-up** (`more_env_test.go`): `newWorld` seeds the rows of `testdata/exports_golden.json` and its photo files, mounts `Routes` with the golden's test-only keys and clock, and `do`/`doLang` sign sessions (owner 1, other host 2, admin 3, admin supporting workspace 1, broken-key host 4, stale login) and CSRF pairs.

**Verified by the brief writer** (fresh throwaway worktree of `origin/go-wave3` at 859d114d5; the sidecars of briefs 1605 copied in order exactly as their step 1 does, then exactly the commands of §4): every `sha256sum` line `OK`, step 2 printed nothing, step 4 printed only `ok` lines on PostgreSQL 16, every named test `--- PASS` with 0 `SKIP`, and the Python run `passed` with 0 skipped (Python 3.13 venv with `App/requirements.txt`). Not run: any browser test (the Go pages are dormant).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/exports/form_pdf.go` | create | `GuestFormPDFHandler`, `registrationFormPDF`, the drawing |
| `go/internal/web/exports/form_pdf_test.go` | create | `TestRegistrationFormMatchesPython`, `TestSignatureRecord`, `TestGuestFormPDFRoute` |
| `go/internal/web/exports/more_env_test.go` | create | shared test set-up of briefs 1605 to 1609 |
| `go/internal/web/exports/testdata/registration_form_golden.json` | create | written by the golden script |
| `App/scripts/registration_form_golden.py` | create | the golden script |
| `App/tests/test_go_registration_form.py` | create | the golden is current |
| `go/internal/web/exports/routes.go` | replace (this version holds the routes of this stage) | `Routes` lists the 9 ported routes |
| `go/internal/web/exports/i18n_keys.txt`, `go/internal/web/exports/i18n.json` | replace | the catalog keys of this stage; `i18n.json` is `App/scripts/go_host_i18n.render` of the keys file, as `exports_golden.py` writes it |
| `go/internal/web/exports/routes_inventory_test.go` | create | `TestExportRoutesInventory`: `Routes` has exactly the 9 patterns |
| `go/cmd/ubyhost-web/register_web_exports_test.go` | create | `TestExportRoutesRegistered`: the 9 routes reach their patterns on the web mux |
| `docs/tasks/1605-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1605-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `printf '%s\n' '3630c8337096ab5e53f67bf5cd470624da43b92786bfe95e6a241795e51a9e02  go/internal/web/exports/routes.go' '5fd023cabc37c732192026283f20e792886d3a2ca4f54fb544e7a1496d2a00b7  go/internal/web/exports/i18n_keys.txt' | sha256sum -c - 2>&1 | tail -5` prints `: OK` for each of the 2 files (they are as this brief expects before it replaces them).
   - `ls go/internal/web/exports/form_pdf.go 2>&1 | tail -1` says "No such file" (nothing of this brief is there yet).
   - `grep -cF 'func signatureKind(ctx context.Context, d deps, g row) (string, error) {' go/internal/web/exports/housebook.go | tail -1` prints `1`.
   - `find docs/tasks/1605-files -name '*.txt' | wc -l | tail -1` prints `11`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1605-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -15
   16b6f930cc67e1f0ded2b2e4e365d8879d2d8946606ca4c3e63f1030dc6ab900  App/scripts/registration_form_golden.py
   270d6eb7210882162b9da142dc7f04bfd761fb101cfe6fe02d9c3c0736a08c0e  App/tests/test_go_registration_form.py
   4248dce2458120f09406c4870083904edd8fd2d9b7e4fce46d6e45465822f1fd  go/cmd/ubyhost-web/register_web_exports_test.go
   e89e9bfb07e4e5f08321559ed8d04a27f70720d3aacdf821da902b324f043168  go/internal/web/exports/form_pdf.go
   4f70947bfc51c84b866210cd17ef1dc43d6868b9446a35dee880483e01ac7758  go/internal/web/exports/form_pdf_test.go
   0ffdcd8f7a428fd6cf674ca17612a49261d0cb0405e80b38d5d7a01dd13e08b8  go/internal/web/exports/i18n.json
   c688b0f38243aaba7af67dc73c1682cdc3800ff676ae65482dbcbbe20c9983bc  go/internal/web/exports/i18n_keys.txt
   17714716d358958df6800d7c9be4796316959a236808f68484b1b2206194847d  go/internal/web/exports/more_env_test.go
   98749b4d1e5235a71780a04bf4ccee7910b819e40c727ec27c88580fc8efd2ef  go/internal/web/exports/routes.go
   d6a1fc596a4a255214be9cf142aabd3fd007a7f9469a0e80e395695ad4c7fe8e  go/internal/web/exports/routes_inventory_test.go
   6bbeb968031d033aa2d35e570c2c485f43b5a43439b5ae950845232059d8dc4f  go/internal/web/exports/testdata/registration_form_golden.json
   EOF
   ```

   Every line must end with `: OK` (11 lines). Then commit "1605 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/exports internal/hostweb internal/retention internal/photosweep cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/exports/ ./cmd/ubyhost-web/ 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). No commit (nothing changed).

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1605 && chown postgres /var/tmp/pg1605 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1605/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1605/data -o "-p 55705 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1605" -l /var/tmp/pg1605/log -w start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55705/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (from `go/`, then `App/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55705/postgres go test ./internal/web/exports/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
   ```

   Expected: 2 `ok` lines, one per package, and nothing else. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55705/postgres go test ./internal/web/exports/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestExportRoutesInventory$|^TestExportRoutesRegistered$|^TestRegistrationFormMatchesPython$|^TestSignatureRecord$|^TestGuestFormPDFRoute$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -40
   ```

   Expected: one `--- PASS` line for each of the 5 tests (TestExportRoutesInventory, TestExportRoutesRegistered, TestRegistrationFormMatchesPython, TestSignatureRecord, TestGuestFormPDFRoute), and `ok` lines; no `--- SKIP`, no `--- FAIL`.

   Python (the golden freshness checks; no Python application file changes). If `App/.venv/bin/python` exists:

   ```bash
   cd App && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55705/postgres .venv/bin/python -m pytest tests/test_go_registration_form.py tests/test_go_exports.py -q --tb=short -rs 2>&1 | tail -8
   ```

   Expected: `4 passed`, no `skipped`, no `failed`. If `App/.venv` does not exist, write "Python: CI only" in the report and go on (do not create a venv).

5. Stop and delete the throwaway server (skip if you used a server you did not start):

   ```bash
   su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1605/data -m fast stop' 2>&1 | tail -2; rm -rf /var/tmp/pg1605
   ```

   Expected: `server stopped`.

6. Write the report (§9), set `Status: review` and commit "1605 step 6".

## 5. Do not touch

`go/internal/session/`, `go/internal/secure/`, `go/internal/pdf/`, `go/internal/deadlines/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web_exports.go` and every other `register_*.go`, the files of `go/internal/web/exports/` that briefs 1320 and 1321 created and this brief does not name (`exports.go`, `guest_json.go`, `stays.go`, `submissions.go`, `exports_test.go`, `testdata/exports_golden.json`), `App/app/` (no Python application file), `App/tests/conftest.py`, `App/scripts/exports_golden.py`, `deploy/` (Caddy, compose, env), `docs/context/*`, and every file not in §3. AGENTS.md rules that apply: 2 (privacy), 3 (no real data in tests), 4 (no new dependency), 5 (plain PostgreSQL through pgx), 8 (never push to `main`), 11 (Go first).

## 6. Commands

Exactly the commands of §4 (steps 1, 2, 4, 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 11 files.
- [ ] Step 2 printed nothing.
- [ ] Step 4 printed 2 (first command) and 2 (second command) `ok` lines and each of the 5 named tests printed `--- PASS` (none `SKIP`, none `FAIL`); the Python run printed only `passed` (or the report says "Python: CI only").
- [ ] `git log --oneline --grep='^1605 step' | tail -5` lists at least the step 1 commit, and `git show --stat --format=%h <that hash> | tail -20` lists only paths of §3.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed.
- [ ] UI: not applicable (a PDF, no template).

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

Write `docs/tasks/1605-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git log --oneline --grep='^1605 step' | tail -10`, then one `git show --stat --format=%h <hash> | tail -20` per commit).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read `form_pdf.go`: the handler order (Cache-Control, login, guest lookup with decryption, missing, identity, render, audit, response) must match `guest_form_pdf`; the audit row is written only after the PDF rendered; `signatureImage` must never panic on a bad data URL.

## Owner steps

When the thread is merged and deployed: add `/guests/*/form.pdf` to `UBYHOST_GO_PATHS` (see brief 1609's owner steps for the whole list). Nothing else.
