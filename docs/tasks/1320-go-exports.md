# 1320: Go port of the host downloads (receipts, envelopes, stays CSV), parity-checked against Python

Status: review

The sidecar files were removed after execution; the sha256 values in §2 match the committed code.
Depends on: none (1321 depends on this) | Base commit: a83df54 | Branch: task/1320-go-exports
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier A (filing records, guest data)

## 1. Objective

Add `go/internal/web/exports`, a Go port of six GET routes of App/app/routes/exports.py (stored Doručenka and error PDFs, the SOAP envelopes, the two receipt zips, the stays CSV), registered from a new `go/cmd/ubyhost-web/register_web_exports.go`, with a golden file written by the real Python on PostgreSQL so the two cannot drift. The routes stay switched off: no path goes into `UBYHOST_GO_PATHS`, no Caddy, compose or env change.

## 2. Context

Rules (AGENTS.md): 1 filing correctness (read-only copies of filed records, no filing code touched); 2 no new personal-data field and no outbound request; 3 no guest data in the repo (fixtures use `@example.test`, made-up names, test-only keys); 4 no new dependency (stdlib `archive/zip`, pgx and repo packages already in `go.mod`); 5 plain PostgreSQL through `pgxpool`.

**All code is pre-written and was dry-run by the brief writer** on a83df54. The exact files are sidecars in `docs/tasks/1320-files/<repo path>.txt`; step 1 copies them into place byte for byte and checks the sha256 below. Never retype or edit them.

| sha256 | file (repo path; sidecar = `docs/tasks/1320-files/<path>.txt`) |
|---|---|
| `964d5ed86596626e03ce14fa14506481c154b9c33fdc7e7367fd090254f4829a` | `App/scripts/exports_golden.py` |
| `642b4d0834752830352fa55474d26d0ec100bd37ff66fc4ae1ca4fa3ed67bec2` | `App/tests/test_go_exports.py` |
| `54aeed26ec033e6e4e8d93053be20057918bd234960b5d59fc970849714f8d12` | `go/cmd/ubyhost-web/register_web_exports.go` |
| `b57b4a633177a1353762e3dce69930ed2418424dfb47e7547c6e1f2ffd8c2da7` | `go/internal/web/exports/exports.go` |
| `80fa3aff095fd243c0003ab381d5c6a3b1502d605696a7ac27669135510eaeb6` | `go/internal/web/exports/exports_test.go` |
| `caaef0c70704902aecf3464d5e950cfa4895318d7cc5a5c5e749a36256b41336` | `go/internal/web/exports/i18n.json` |
| `5fd023cabc37c732192026283f20e792886d3a2ca4f54fb544e7a1496d2a00b7` | `go/internal/web/exports/i18n_keys.txt` |
| `0f1b26ddb7ebf695e7dd9be8efe9b62aef5749659eef956e25ec802aefcf6a16` | `go/internal/web/exports/routes.go` |
| `c67f7fd774ba10db8b4626d41545a43beb8c8521f9932c109b08808c136cad14` | `go/internal/web/exports/stays.go` |
| `7559840ad37941113cf9302ab474ccedd829a79e42f30f725ee579270f1a9dd3` | `go/internal/web/exports/submissions.go` |
| `8485b6357bf3541596643f50b11cfd89a0f279ff8170fc58062d2fa3c882c972` | `go/internal/web/exports/testdata/exports_golden.json` (generated, deterministic) |

**Routes ported** (Python source in App/app/routes/exports.py): `GET /submissions/{id}/receipt.pdf` (239-255), `GET /submissions/{id}/errors.pdf` (313-328), `GET /submissions/{id}/{which}.xml` (331-354), `GET /submissions/receipts.zip` (170-221 with reporting.build_receipts_zip / receipt_zip_name), `GET /reservations/{id}/dorucenka.zip` (258-310), `GET /reservations.csv` (69-91 with App/app/stays_export.py). Brief 1321 adds `/housebook.csv` and `/guests/{id}/export.json`.

**Non-goals (stay on Python):** `GET /guests/{id}/form.pdf` and `GET /housebook/pdfs.zip` (need a Go PDF library, not decided, billing thread); `POST /settings/workspace-export` (its zip holds `guests/<id>.pdf` from `housebook.registration_form_pdf`, the same PDF gap, so it cannot match Python yet); `POST /settings/purge-expired` (waits for the retention and photo-sweep ports); `GET /settings/archived` (HTML page, waits for the shared Go host layout). No layout or template is written here.

**How the Go copies Python:**

- Gate: `hostweb.Login` (= auth.require_login); `access.owner_id` = workspace id; ownership joins with `a.owner_user_id IS NOT DISTINCT FROM $n` (= db.null_safe_eq on PostgreSQL); `access.identity_visible` / `dorucenka_download_visible` (admin always, own workspace always, impersonation only for a guest id in payload `rv`); `auth.impersonating` adds ` while_supporting=1` to the PDF audit details.
- Audit (= db.audit with the actor require_login sets): `actor` = signed-in username, `actor_user_id` = signed-in id, `impersonator_user_id` = signed-in id only while impersonating, else NULL, `owner_user_id` = workspace id, `at` = db.utcnow format. The golden compares all seven columns.
- Decryption: `request_xml_enc` through `secure.LoadDataKeys` (= db.decrypt_field: no token gives the plaintext column, a bad token is a 500; Python decrypts it whenever it is selected, so a broken token also fails `response.xml`).
- Bodies and headers: status, Content-Type (Starlette adds `; charset=utf-8` to text/*), Content-Disposition, Location (flash via `hostweb.Back`, texts from a package catalog `i18n.json` written from host_i18n.py by the golden script; `scripts/go_host_i18n.py` only globs `go/internal/*/`), `Cache-Control: no-store, private` (the Python middleware sets it on every non-static response; Go sets it per route). Zips: same entry names, order, contents, deflate method; bytes differ (timestamps, compressor). CSV: own writer for Python's `csv.writer(delimiter=";")` QUOTE_MINIMAL with `\r\n` and BOM, `csv_safe` ported. base64 like `b64decode` (non-alphabet dropped, bad padding = "Stored document is not valid base64." 500). Filenames use the injected `now` in server-local time (= `datetime.now()`).
- `{which}.xml` is not a ServeMux pattern: the route is `GET /submissions/{id}/{file}`; `receipt.pdf` and `errors.pdf` are more specific and win. A `{file}` not ending in `.xml` (or exactly `.xml`) is not a Python route of this module and gets `http.NotFound`, the same 404 as main.go's `/` catch-all (main.go has no proxy to Python; Caddy only sends listed paths). A non-integer id also gets that 404 (Python: HTML error page for browsers, 422 JSON for scripts; Go has no host layout yet). HEAD is 405 like FastAPI's GET routes.
- `Routes()` builds handlers without touching the pool (the registry rule; `TestRoutesNeedNoPool` checks it with a nil pool).

**Parity mechanism.** `App/scripts/exports_golden.py` creates and drops database `ubyhost_exports_golden` on the server in `UBYHOST_TEST_DATABASE_URL`, applies the PostgreSQL schema, seeds 3 users, 3 apartments, 7 stays, 6 submissions (one encrypted envelope, one bad base64 receipt) and 5 guests, freezes `datetime.now` in exports.py and `db.utcnow`, sends 37 requests through the FastAPI TestClient (signed out, owner, other host, admin, admin impersonating the owner; en/cs/vi flashes) and records status, headers, body or zip entries and the audit rows each wrote. `exports_test.go` seeds the same rows into a fresh PostgreSQL, sends the same requests to `Routes()` and compares. PostgreSQL, not SQLite, because the Go routes run there (and 1321's `SELECT *` order and boolean results differ). `App/tests/test_go_exports.py` checks the catalog everywhere and runs the script with `--check` when a PostgreSQL URL is set (CI job test-postgres-full).

**Verified by the brief writer:** gofmt empty, `go vet ./...` clean, `go test ./cmd/ubyhost-web/ ./internal/web/...` ok with local PostgreSQL 16 (`--- PASS: TestGoldenParity`, not skipped), golden `--check` clean on a second run, the pytest file 3 passed on PostgreSQL (2 passed 1 skipped on SQLite); mutations (impersonator dropped, a body byte, an audit detail) each failed the Go test.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/exports/exports.go` | create | gate, flash, audit, query helpers, PDF response |
| `go/internal/web/exports/submissions.go` | create | receipt/errors PDF, envelopes, both receipt zips |
| `go/internal/web/exports/stays.go` | create | stays CSV, CSV writer, csv_safe |
| `go/internal/web/exports/routes.go` | create | `Routes()` pattern list |
| `go/internal/web/exports/exports_test.go` | create | golden parity on PostgreSQL, nil-pool and helper tests |
| `go/internal/web/exports/i18n_keys.txt` | create | flash keys the package reads |
| `go/internal/web/exports/i18n.json` | create (generated) | those keys from host_i18n.py |
| `go/internal/web/exports/testdata/exports_golden.json` | create (generated) | seed, requests, expected responses |
| `go/cmd/ubyhost-web/register_web_exports.go` | create | `init()` → `registerRoutes` |
| `App/scripts/exports_golden.py` | create | writes the two generated files |
| `App/tests/test_go_exports.py` | create | catalog and golden freshness |
| `docs/tasks/1320-report.md` | create | the report (§9) |

No other file may change. The sidecars under `docs/tasks/1320-files/` are already committed with this brief; leave them.

## 4. Steps

0. Checks (one call, repo root): `git branch --show-current` prints `task/1320-go-exports`; `ls go/internal/web go/cmd/ubyhost-web/register_web_exports.go App/scripts/exports_golden.py App/tests/test_go_exports.py 2>&1 | tail -30` says "No such file" four times; `grep -c 'func registerRoutes(' go/cmd/ubyhost-web/registry.go` prints 1; `grep -c 'ubyhost_sqlite_date' App/migrations_pg/00001_baseline.sql` prints at least 1. If `App/.venv/bin/python` is missing: `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5`. Anything else: STOP (§8).

1. Copy the sidecars into place and check them (one call, repo root):

   ```bash
   cd docs/tasks/1320-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum App/scripts/exports_golden.py App/tests/test_go_exports.py go/cmd/ubyhost-web/register_web_exports.go go/internal/web/exports/*.go go/internal/web/exports/i18n* go/internal/web/exports/testdata/exports_golden.json | tail -30
   ```

   Every hash must equal the table in §2 (11 files). A mismatch: STOP. Commit "1320 step 1" (the 11 files).

2. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, skip to step 3. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1320 && chown postgres /var/tmp/pg1320 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1320/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1320/data -o "-p 55432 -k /var/tmp/pg1320" -l /var/tmp/pg1320/log start' 2>&1 | tail -3
   ```

   Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres` in steps 3-4. No PostgreSQL 16 binaries at that path: write "CI only" in the report and continue with the non-DB commands.

3. Golden freshness (from `App/`): `UBYHOST_TEST_DATABASE_URL=<url> .venv/bin/python scripts/exports_golden.py --check 2>&1 | grep -v INFO | tail -5` prints nothing (no `stale:` line), and `git status --short ../go | tail -5` is empty. A `stale:` line: STOP (Python moved; never edit the JSON, Python or Go to match).

4. Go (from `go/`): `test -z "$(gofmt -l .)" && go vet ./... && UBYHOST_TEST_DATABASE_URL=<url> go test ./cmd/ubyhost-web/ ./internal/web/... -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30`. Expected: `--- PASS: TestGoldenParity`, `--- PASS: TestRoutesNeedNoPool`, `--- PASS: TestHelpers` and two `ok`. A SKIP of TestGoldenParity means the URL was not seen. A FAIL: STOP, paste the first 30 lines.

5. Python (from `App/`): `UBYHOST_TEST_DATABASE_URL=<url> .venv/bin/python -m pytest tests/test_go_exports.py tests/test_go_host_i18n.py -q --tb=short -rs 2>&1 | tail -30` passes with 0 skipped (without PostgreSQL: one skip of `test_exports_golden_is_current` is expected). Then write the report (§9) and commit "1320 step 5".

## 5. Do not touch

`App/app/` (all of it), `App/migrations_pg/`, `go/internal/hostweb/`, `go/internal/session/`, `go/internal/jobs/`, `go/internal/validation/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web.go`, `go/go.mod`, `go/go.sum`, `App/tests/conftest.py`, `App/scripts/go_host_i18n.py`, `deploy/`, `.github/`, `docs/ENVIRONMENT.md`, `docs/context/` (status, test-map, decisions, known-issues). No env var, no `UBYHOST_GO_PATHS` value, no migration, no dependency. Hard rules 1-5.

## 6. Commands

Steps 3-5 above (they are the test-map for this change: the new package, the registry, the golden). From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] The 11 sha256 values of step 1 match §2.
- [ ] Step 3: `--check` clean, `git status --short ../go` empty.
- [ ] Step 4: gofmt empty, vet clean, `TestGoldenParity` PASS on PostgreSQL (or "CI only" with the reason).
- [ ] Step 5: pytest green.
- [ ] `git diff --stat a83df54..HEAD | tail -30` lists only §3 paths, this brief and `docs/tasks/1320-files/`, `docs/tasks/1321*`.
- [ ] Commits "1320 step 1" and "1320 step 5"; nothing pushed.

## 8. Stop and ask

Stop, and write the report as `blocked`, if:

- a step 0 check fails or a §3 file already exists;
- a hash differs, or the golden is stale;
- any test fails twice, or `TestGoldenParity` fails once (a Go/Python mismatch is a question for the orchestrator);
- you reach 25 tool calls or about 50k tokens (see executor.md);
- a new dependency seems needed, or a file outside §3 needs a change;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1320-report.md` (600 tokens at most) and set this brief's `Status: review`. It has: 1. `git diff --stat a83df54..HEAD | tail -15`; 2. steps 1, 3, 4, 5 with the last 5 lines of output; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left (none: nothing is switched on).

## Risk list (for the reviewer)

Read `submissions.go`, `exports.go` and `stays.go` against the Python line ranges in §2: the ownership SQL (`IS NOT DISTINCT FROM`, stays CSV `($1::bigint IS NULL OR a.owner_user_id = $1)`), the audit columns and which branches audit (receipt/errors only when owned, also on a 404 for a missing PDF; xml after the ownership check and without `while_supporting`; zips only after a non-empty build; stay zip audit before the one-file/zip decision), the identity gates, the base64 rule, `receipt_zip_name` (`[:36]`, Unicode `\w`), the `{file}` 404 path, and that `Routes()` never touches the pool. Then `exports_test.go` must not skip in CI (`--- PASS: TestGoldenParity` in the Go job). Known and accepted, see the PR text: redirects from `hostweb.Login`/`Back` carry Go's `text/html` type and short body where Starlette sends none (the test skips Content-Type on 303); the Python middleware's session refresh and CSRF cookie are not ported (same as the other Go host routes; `m.wrap` adds the security headers); a non-integer id is a plain 404, not the HTML error page or 422; `go/internal/session.AcceptancePending` defaults every document to version 1.7 while `config.py` has privacy and dpa at 1.8 (pre-existing, outside this brief; the seed accepts both versions; flag for a session fix before any host route goes live); the identity-hidden redirect is unreachable today (impersonation needs an admin, and admins always see) but is ported.

## Owner steps

None for this brief: no path is in `UBYHOST_GO_PATHS`. Switching on is a later owner decision (Caddy globs such as `/submissions/*/receipt.pdf`, `/submissions/*.xml`, `/submissions/receipts.zip`, `/reservations/*/dorucenka.zip`, `/reservations.csv`).
