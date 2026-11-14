# 1583: Go stay fee PDF downloads (single report and monthly ZIP)

Status: todo
Depends on: 1240, 1242, 1330 | Base commit: current tip of the working branch | Branch: task/1583-go-stay-fee-pdf-downloads
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1583 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1583 step'` and `git show --stat <commit>`, never a fixed base commit.

## 1. Objective

Add `GET /stay-fees/{apartment_id}/pdf` (`stay_fee_pdf_download`) and `GET /stay-fees/pdfs.zip` (`stay_fee_pdfs_zip`) to `go/internal/web/stayfees`. Both serve the sealed, encrypted PDF stored in `stay_fee_filing.pdf_enc`, like the CSV route of brief 1330. Dormant until the owner routes the paths.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (nothing is recalculated or re-rendered; the stored bytes are served); 2 privacy: no new personal-data field, no new retention line, no outbound request; 3 fixtures are made up (`@example.test`, a test-only data key); 4 no new dependency (stdlib `archive/zip`, pgx and packages already in `go.mod`); 5 plain PostgreSQL through `pgxpool`, the Python SQL with `$n` placeholders, no schema change; 6 light mode (no page here); 11 Go first (this brief is the Go port; no file under `App/` changes).

**PR text (hard rule 2):** no new outbound request and no new personal-data field. Each download writes an audit row (`stay_fee_pdf`, `stay_fee_pdf_zip`) with ids, period and counts only, as Python does.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1583-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `6d8e33a93cd1a110bdfc8bc068fc2f62d9f973ffe621db6187c4dd9b7050bd09` | `go/cmd/ubyhost-web/register_web_stayfees_downloads.go` | create | 25 |
| `972103b3ebc1bc7ad4f05571b09051d5f8301e3bb33352e41afef36fd433d655` | `go/cmd/ubyhost-web/register_web_stayfees_downloads_test.go` | create | 21 |
| `a35905c876c4ee72bbb401c20e0134bce16d9e3272e616885924c8b302fde36c` | `go/internal/web/stayfees/download.go` | create | 237 |
| `c34d97154ac46badd74e405e8d11ee4ce917c6da6de67952aba00b08351e0427` | `go/internal/web/stayfees/download_test.go` | create | 344 |

**How the code is built.** `download.go` holds `PDFHandler`, `PDFsZipHandler`, `DownloadRoutes` (the two patterns) and `(*call).pdfBytes` (`stay_fee_filing.pdf_bytes`). It reuses the unexported helpers of `handlers.go` and `helpers.go` (`deps.enter`, `pathID`, `pathApartment`, `monthPath`, `flash`, `back`, `audit`) and `stayfee.Covering`, `stayfee.LoadApartment`, `stayfee.VSOf`. `register_web_stayfees_downloads.go` registers the routes from a new file (pattern of `register_web_stayfees.go`). No existing file is edited.

**Parity notes (Python `App/app/routes/stay_fees.py`):**

| Route | Python | Go |
|---|---|---|
| `GET /stay-fees/{apartment_id}/pdf` | `stay_fee_pdf_download` 936-977 | `PDFHandler` |
| `GET /stay-fees/pdfs.zip` | `stay_fee_pdfs_zip` 733-773 | `PDFsZipHandler` |
| `pdf_bytes` | `App/app/stay_fee_filing.py` 71-74 | `(*call).pdfBytes` |

Details that are easy to get wrong and are tested:

- Single PDF, month rules as the CSV route: no `month` or a bad one is the current Prague month; a month after the current one is a 303 to `/stay-fees/{id}/pdf?month=<current>`; no sealed filing and a property with a rate is a 303 to `/stay-fees/{id}?month=<m>` with `flash.stay_fees.not_saved`; no filing and no rate, a foreign, missing or out-of-range id is a 303 to `/stay-fees` with `flash.error.no_such_apartment`; a sealed filing of a property whose fee was switched off since still downloads.
- File name `hlaseni-poplatek-z-pobytu-<period_key>-<digits of stay_fee_vs>.pdf` (the single download has no apartment id; the ZIP entries do: `...-<vs>-<apartment_id>.pdf`, so an empty VS gives `--`). Headers `application/pdf`, `Cache-Control: no-store`. A filing with a NULL `pdf_enc` downloads as an empty body, as `pdf_bytes` returns `b""`. A token that does not decrypt is a 500 and no audit row.
- Audit `stay_fee_pdf`: `apartment_id=<id> period=<key> total=<total_due_czk>`. The audit row is written after the bytes are read, before the answer.
- ZIP: the host's non-archived properties, `ORDER BY internal_name, id`; per property the newest sealed filing covering the month (either cadence); entry name as above; a repeated name is skipped; entries are deflated; a month after the current one falls back to the current month with no redirect; no entry at all is a 303 to `/stay-fees?month=<m>` with `not_saved` and no audit row; else audit `stay_fee_pdf_zip` `month=<m> files=<n>`, `application/zip`, `attachment; filename="poplatek-z-pobytu-<m>.zip"`, `no-store`.
- Both routes: signed out is the login redirect; a non-integer id is a 422; `HEAD` is a 405 with `Allow: GET` (FastAPI lists GET only); a repeated `month` key reads the last value.
- Routing: Go's mux serves the literal `GET /stay-fees/pdfs.zip` before `GET /stay-fees/{apartment_id}` (the detail page of brief 1582). `TestPDFsZipBeatsDetailPattern` registers a dummy detail pattern next to the two routes and proves it.

**Known differences from Python, shared by every Go web area (not fixed here):** a non-integer id answers `422 {"detail":"Unprocessable Entity"}`; `HEAD` is a 405 here (as the CSV route); ZIP entry timestamps are the request time in UTC (Python writes the server's local time); the ZIP bytes are not identical to Python's (compression level, extra fields) but each entry body is the identical stored PDF. A property with a rate that Python lists but whose newest filing is `superseded` is skipped as in Python (`covering` ignores superseded rows). No Python call renders a PDF here, so the Go PDF renderer is not involved.

**Paths that become fully served by Go:** `GET /stay-fees/pdfs.zip` and `GET /stay-fees/*/pdf`. **Goes live on deploy if** these paths are already routed to Go (assumed not). The routes only read stored data and write one audit row.

**Anchors that must exist verbatim** (step 0): the Python and Go function lines listed there.

**Verified by the brief writer** (in a throwaway worktree of `go-wave3`, steps applied exactly and in order, sidecars copied as step 1 does): `gofmt -l` printed nothing, `go build ./...` and `go vet ./internal/web/stayfees/... ./cmd/...` were silent, and `go test ./internal/web/stayfees/... ./cmd/ubyhost-web/... -count=1` passed on PostgreSQL 16 with the golden test of brief 1330 still green and 0 skipped tests. The tests cover: the PDF body, headers, file name and audit row (monthly, quarterly seal, NULL `pdf_enc`, admin inside the workspace); every redirect (future month, current month not saved, bad month, inactive, foreign, missing and out-of-range property, signed out, 422, HEAD 405, no audit row on a refusal); an undecryptable blob (500, no audit); the ZIP (entry names, order, bodies, deflate, headers, audit, other host, future and bad month, a month nobody sealed, signed out); and the mux test.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_stayfees_downloads.go` | create | registers the two routes |
| `go/cmd/ubyhost-web/register_web_stayfees_downloads_test.go` | create | route registration test |
| `go/internal/web/stayfees/download.go` | create | the two handlers |
| `go/internal/web/stayfees/download_test.go` | create | route tests |
| `docs/tasks/1583-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1583-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `ls go/internal/web/stayfees/handlers.go go/internal/stayfee/filing.go 2>&1 | tail -2` lists both files (briefs 1240 and 1330 are on this branch).
   - `grep -cF "def stay_fee_pdfs_zip(request: Request):" App/app/routes/stay_fees.py | tail -1` prints `1`.
   - `grep -cF "def stay_fee_pdf_download(apartment_id: int, request: Request):" App/app/routes/stay_fees.py | tail -1` prints `1`.
   - `grep -cF "def pdf_bytes(row: Dict[str, Any]) -> bytes:" App/app/stay_fee_filing.py | tail -1` prints `1`.
   - `grep -cF "func CSVHandler(" go/internal/web/stayfees/handlers.go | tail -1` prints `1`.
   - `grep -cF "func (c *call) noSuchApartment()" go/internal/web/stayfees/handlers.go | tail -1` prints `1`.
   - `grep -cF "func Covering(" go/internal/stayfee/filing.go | tail -1` prints `1`.
   - `grep -cF "func LoadApartment(" go/internal/stayfee/loader.go | tail -1` prints `1`.
   - `grep -cF "func VSOf(" go/internal/stayfee/calc.go | tail -1` prints `1`.
   - `ls go/internal/web/stayfees/download.go 2>&1 | tail -1` says "No such file" (nothing of this brief exists yet).
   - `find docs/tasks/1583-files -name '*.txt' | wc -l | tail -1` prints `4`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1583-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -6
   6d8e33a93cd1a110bdfc8bc068fc2f62d9f973ffe621db6187c4dd9b7050bd09  go/cmd/ubyhost-web/register_web_stayfees_downloads.go
   972103b3ebc1bc7ad4f05571b09051d5f8301e3bb33352e41afef36fd433d655  go/cmd/ubyhost-web/register_web_stayfees_downloads_test.go
   a35905c876c4ee72bbb401c20e0134bce16d9e3272e616885924c8b302fde36c  go/internal/web/stayfees/download.go
   c34d97154ac46badd74e405e8d11ee4ce917c6da6de67952aba00b08351e0427  go/internal/web/stayfees/download_test.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1583 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/stayfees cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/stayfees/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all (gofmt lists nothing, build and vet are silent). Anything printed: STOP (§8). Nothing changed, so no commit.

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if it already runs (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55583/data status' | tail -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55583 && chown postgres /var/tmp/pg55583 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55583/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55583/data -o "-p 55583 -k /var/tmp/pg55583" -l /var/tmp/pg55583/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55583/postgres` in the next step. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55583/postgres go test ./internal/web/stayfees/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: two lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stayfees	<seconds>s` and `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	<seconds>s`. The golden test of brief 1330 (`TestActionsMatchPython`) is part of the first package and must stay green. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55583/postgres go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestPDFDownload$|^TestPDFDownloadRedirects$|^TestPDFDownloadUndecryptable$|^TestPDFsZip$|^TestPDFsZipBeatsDetailPattern$|^TestStayFeesDownloadRoutesRegistered$' 2>&1 | grep -aE '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of 6 tests (times differ) and two final `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestPDFDownload (0.NNs)
   --- PASS: TestPDFDownloadRedirects (0.NNs)
   --- PASS: TestPDFDownloadUndecryptable (0.NNs)
   --- PASS: TestPDFsZip (0.NNs)
   --- PASS: TestPDFsZipBeatsDetailPattern (0.NNs)
   --- PASS: TestStayFeesDownloadRoutesRegistered (0.NNs)

   Report the SKIP count (it must be 0): `go test ... -v 2>&1 | grep -ac -- '--- SKIP'`.

5. Write the report (§9), set `Status: review` in this file and commit "1583 step 5". Do not open a PR (one big PR mode); the owner or the orchestrator opens it with the PR text of §2.

## 5. Do not touch

`App/` (no Python file changes; the Python routes stay the live ones), `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, `go/internal/web/stayfees/handlers.go`, `i18n.json`, `go/cmd/ubyhost-web/register_web_stayfees.go` and every other existing file. Hard rules of AGENTS.md: no secret or guest datum in a file or a log (the test data is made up), nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 2 and 4). The test-map row for `go/internal/web/stayfees` already exists; the coordinator adds the new test names from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 4 files.
- [ ] The format, build and vet step printed nothing.
- [ ] The test step printed `ok` for both packages, and each of the 6 named tests printed `--- PASS` (none `SKIP`, none `FAIL`) on PostgreSQL; the SKIP count is 0.
- [ ] `git log --oneline --grep='^1583 step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1583 step') | tail -40` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed to `main`.
- [ ] UI: not applicable (rules 7 and 10): the routes return files and redirects, no template changes; they are dormant until the owner routes the paths.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor, a hash or a file count of step 0 or step 1 is not as stated;
- a test fails twice (read the last 30 lines, fix nothing in the sidecar files yourself: report);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1583-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git diff --stat` as in §7).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of: `download.go` (`PDFHandler`: the property is reached through the owner-scoped `pathApartment` before any filing is read, so a foreign id leaks nothing; the audit row is written only after a successful decrypt; `PDFsZipHandler`: the property list is scoped by `owner_user_id` and excludes archived rows, an entry is added only for a covering filing of that same property); the registration file (two patterns, no duplicate of an existing pattern; `go test` of `cmd/ubyhost-web` builds the mux and would panic on a duplicate).

## Owner steps

None: nothing is switched on. When the stay fee pages move to Go, route `GET /stay-fees/pdfs.zip` and `GET /stay-fees/*/pdf` together with brief 1582 (the detail page), and keep `pdfs.zip` ahead of the detail pattern if Caddy matches paths by prefix.
