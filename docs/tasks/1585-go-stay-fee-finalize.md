# 1585: Go stay fees: seal one period (POST /stay-fees/{apartment_id}/finalize)

Status: todo
Depends on: 1330, 1242a (stayfee.Save), 1580 (the real PDF renderer, only needed for production, not for the tests) | Base commit: current tip of the working branch | Branch: task/1585-go-stay-fee-finalize
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1585 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1585 step'` and `git show --stat <commit>`, never a fixed base commit.

## 1. Objective

Add `POST /stay-fees/{apartment_id}/finalize` to `go/internal/web/stayfees`: it seals one fee period (or a correction of a sealed one) through `stayfee.Save`, writes the audit row and redirects with the Python flashes. Dormant until the owner routes the path.

## 2. Context

Rules (AGENTS.md): 1 filing correctness: the seal is the existing `stayfee.Save` (brief 1242a), this brief only calls it; 2 privacy: no new personal-data field, no new retention line, no outbound request; 3 fixtures are made up (`@example.test`, test-only keys); 4 no new dependency (stdlib, pgx and packages already in `go.mod`); 5 plain PostgreSQL through `pgxpool`, no schema change; 6 light mode, no page is added; 11 Go first (this brief is the Go port; no file under `App/app/` changes).

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The route writes through the existing seal code: encrypted PDF, CSV and payload with the same data keys as Python.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1585-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `13c65acc9a63c578655f9bf49e1b21cb4db2f43909c21c6e2d4e139a61d46dc4` | `go/cmd/ubyhost-web/register_web_stayfees_finalize.go` | create | 22 |
| `40c89133a897dae019f38badc10aa4497f252fbeade561f24badbe03820e7316` | `go/cmd/ubyhost-web/register_web_stayfees_finalize_test.go` | create | 15 |
| `6f98b558a8452d26e08fe1e65d8036fd53ef1256039ba0bc94f0c59953e9b4c6` | `go/internal/web/stayfees/finalize.go` | create | 194 |
| `adf875c7b6271d00c168970e0ad9f0de447c118b36588aa77db7a0a3c71798ef` | `go/internal/web/stayfees/finalize_i18n.json` | create | 12 |
| `00ecfc3138742d5d782348832971ea876e556937c92161e3b40c738e9a8c0d2c` | `go/internal/web/stayfees/finalize_test.go` | create | 458 |
| `0b6b943b00ddb1c55f8e6a106c4a9e284920cae08b89f76b486bb3eea0517fbf` | `go/internal/web/stayfees/finalize_overlap_test.go` | create | 27 |

**How the code is built.** `finalize.go` holds `FinalizeHandler(pool, getenv, now, renderer)`: it follows `stay_fee_finalize` line by line on the helpers of brief 1330 (`enter`: CSRF then login; `pathApartment`; `back`; `audit`; `feeReturnPath`) and calls `stayfee.Check`, `stayfee.Latest`, `stayfee.Covering`, `stayfee.CorrectionRate` and `stayfee.Save`. Its three own flash texts are in `finalize_i18n.json` (embedded, `finalizeCatalog`); `report_blocked` and `no_such_apartment` come from the existing catalog. The Fernet encrypter and decrypter are built from `secure.LoadDataKeys(getenv)` exactly as the `stay_fee_mail` job does (`stayfee.FernetEncrypter`, `stayfee.FernetDecrypter`).

**Renderer.** Nil renderer, decided here: `FinalizeHandler` takes the renderer as a parameter. When it is nil the handler runs the same checks as Python and then, instead of calling `Save`, shows the `report_blocked` error flash (the one Python shows when `save()` refuses) with a log line; nothing is sealed and no audit row is written. The register file passes the package variable `stayFeeRenderer`. NOTE for the reviewer: `init()` of the register file runs `registerRoutes(...)` with a closure, and the closure reads `stayFeeRenderer` when the mux is built (after all `init`s, so after brief 1580 has set it).

**Parity notes (Python `App/app/routes/stay_fees.py` unless named):**

| Python (`stay_fees.py`) | Go (`finalize.go`) |
|---|---|
| `stay_fee_finalize` 1259-1325: login, `is_active` check | `FinalizeHandler`: `enter`, `pathApartment`, `isActive` |
| month from the form or `_default_month`, `back_path`, `fee_return_path` | `c.month()`, `monthPath`, `feeReturnPath` |
| `correct == "1"`: `covering`, `period_anchor`, `correction_rate` | `stayfee.Covering`, `PeriodAnchor`, `CorrectionRate` |
| `stay_fee_auto.check(...)` and its issues | `stayfee.Check` with `Opts{Cadence, Rate, ScheduleToday}` |
| `latest(...)` and `already_saved` | `stayfee.Latest` |
| `collected_<guest id>` fields, `parse_czk_int`, `confirm_collected` | the loop over `checked.Period.Lines`, `stayfee.ParseCZKInt` |
| `stay_fee_filing.save(...)` and its `except` clauses | `stayfee.Save`, `finalizeSaveOutcome` (ValueError -> `report_blocked`, integrity error -> `already_saved`) |
| `db.audit("stay_fee_finalize", ...)` | `c.audit` (actor, actor user id, owner, impersonator as the other routes) |

Details that are easy to get wrong and are tested: a foreign, missing or fee-less apartment redirects to `/stay-fees` with the `no_such_apartment` error and nothing is read further; an archived apartment with a fee is NOT refused (Python only tests `is_active`); with no month the current month is used and a future month is not clamped (Python does not clamp here); a month whose period is not over yet is blocked by the check; a correction needs a covering sealed filing, else `report_blocked`; a correction uses the sealed cadence, the period anchor of the sealed key and the sealed flat rate when the period had one rate; a collected field that is present but not a plain number is `report_blocked` (an empty field keeps the calculated amount); a period with lines needs `confirm_collected=1`, checked after the amounts; the audit row is written only after `Save` succeeded; `ErrInactive`, `ErrOverlap` and `ErrChanged` show `report_blocked`, `ErrDuplicate` and any SQLSTATE of class 23 show `already_saved`, anything else answers 500; the schedule "today" is the UTC date of the clock (as the job), the issue "today" the Prague date.

**Known differences from Python, shared by every Go web area (not fixed here):** a missing or foreign record answers the not-found flash redirect as the sibling routes do; a non-integer id answers `422 {"detail":"Unprocessable Entity"}`; a repeated form key reads the last value (as Starlette does) except `apartment_id`, which reads every value; Python's `isdigit()` also accepts non-ASCII digits, Go's check is ASCII only.

**Paths that become fully served by Go:** `POST /stay-fees/{apartment_id}/finalize`. **Goes live on deploy if** that path is already routed to Go (assumed not). It also needs the real renderer of brief 1580 (`stayFeeRenderer`); until then the route seals nothing.

**Anchors that must exist verbatim** (step 0).

**Verified by the brief writer** (in a worktree of go-wave3, the sidecars copied as step 1 does): `gofmt -l` printed nothing, `go build ./...` and `go vet ./internal/web/stayfees/ ./cmd/...` were silent, and `go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1 -v` passed on PostgreSQL 16 (port 55585) with 0 `--- SKIP` lines, the golden test `TestActionsMatchPython` of brief 1330 still green, and the named tests PASS. Both new briefs (1585 and 1586) were also checked alone: with the files of the other brief removed the package still vets. The two new briefs share no file; the existing 1330 golden test and the stay-fee mail tests were part of the same run.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_stayfees_finalize.go` | create | registers `POST /stay-fees/{apartment_id}/finalize` with `stayFeeRenderer` |
| `go/cmd/ubyhost-web/register_web_stayfees_finalize_test.go` | create | route registration test |
| `go/internal/web/stayfees/finalize.go` | create | `FinalizeHandler`, `finalizeSaveOutcome` |
| `go/internal/web/stayfees/finalize_i18n.json` | create | the three flashes of this route (cs, en), from `App/app/host_i18n.py` |
| `go/internal/web/stayfees/finalize_test.go` | create | route tests on PostgreSQL (fake renderer) |
| `go/internal/web/stayfees/finalize_overlap_test.go` | create | overlap test |
| `docs/tasks/1585-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1585-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `ls go/internal/web/stayfees/handlers.go | tail -1` prints the path (brief 1330 is on this branch).
   - `ls go/internal/stayfee/save.go | tail -1` prints the path (brief 1242a is on this branch).
   - `grep -cF "func Save(ctx context.Context, db DB, deps SaveDeps, ap *Apartment, a SaveArgs) (int64, error) {" go/internal/stayfee/save.go | tail -1` prints `1`.
   - `grep -cF "func Check(ctx context.Context, q Querier, dec Decrypter, ap *Apartment, month, today time.Time, o Opts) (*Checked, error) {" go/internal/stayfee/loader.go | tail -1` prints `1`.
   - `grep -cF "func feeReturnPath(raw string, apartmentID int64) string {" go/internal/web/stayfees/helpers.go | tail -1` prints `1`.
   - `grep -cF "func (d deps) enter(w http.ResponseWriter, r *http.Request) *call {" go/internal/web/stayfees/handlers.go | tail -1` prints `1`.
   - `grep -cF "var stayFeeRenderer stayfee.PDFRenderer" go/cmd/ubyhost-web/register_job_stay_fee_mail.go | tail -1` prints `1`.
   - `grep -cF "async def stay_fee_finalize(apartment_id: int, request: Request):" App/app/routes/stay_fees.py | tail -1` prints `1`.
   - `ls go/internal/web/stayfees/finalize.go 2>&1 | tail -1` says "No such file" (nothing of this brief exists yet).
   - `ls go/internal/stayfeemail/testdata/stay_fee_job_golden.json | tail -1` prints the path (the test fixture).
   - `find docs/tasks/1585-files -type f | wc -l | tail -1` prints `6`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1585-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -8
   13c65acc9a63c578655f9bf49e1b21cb4db2f43909c21c6e2d4e139a61d46dc4  go/cmd/ubyhost-web/register_web_stayfees_finalize.go
   40c89133a897dae019f38badc10aa4497f252fbeade561f24badbe03820e7316  go/cmd/ubyhost-web/register_web_stayfees_finalize_test.go
   6f98b558a8452d26e08fe1e65d8036fd53ef1256039ba0bc94f0c59953e9b4c6  go/internal/web/stayfees/finalize.go
   adf875c7b6271d00c168970e0ad9f0de447c118b36588aa77db7a0a3c71798ef  go/internal/web/stayfees/finalize_i18n.json
   00ecfc3138742d5d782348832971ea876e556937c92161e3b40c738e9a8c0d2c  go/internal/web/stayfees/finalize_test.go
   0b6b943b00ddb1c55f8e6a106c4a9e284920cae08b89f76b486bb3eea0517fbf  go/internal/web/stayfees/finalize_overlap_test.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1585 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/stayfees cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/stayfees/ ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). Nothing changed, so no commit.

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if an earlier brief of this series left it running (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55585/data status' | tail -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55585 && chown postgres /var/tmp/pg55585 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55585/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55585/data -o "-p 55585 -k /var/tmp/pg55585" -l /var/tmp/pg55585/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55585/postgres` in the next step. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55585/postgres go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
   ```

   Expected: two lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stayfees	<seconds>s` and `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	<seconds>s`. The golden test of brief 1330 (`TestActionsMatchPython`) is part of the first package and must stay green. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55585/postgres go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestFinalizeSealsPeriod$|^TestFinalizeReturnTo$|^TestFinalizeRefusals$|^TestFinalizeNeedsLoginAndCSRF$|^TestFinalizeNilRenderer$|^TestFinalizeCorrection$|^TestFinalizeSaveErrorMapping$|^TestFinalizeOverlap$|^TestStayFeesFinalizeRouteRegistered$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of 9 tests (times differ) and two final `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestFinalizeSealsPeriod (0.NNs)
   --- PASS: TestFinalizeReturnTo (0.NNs)
   --- PASS: TestFinalizeRefusals (0.NNs)
   --- PASS: TestFinalizeNeedsLoginAndCSRF (0.NNs)
   --- PASS: TestFinalizeNilRenderer (0.NNs)
   --- PASS: TestFinalizeCorrection (0.NNs)
   --- PASS: TestFinalizeSaveErrorMapping (0.NNs)
   --- PASS: TestFinalizeOverlap (0.NNs)
   --- PASS: TestStayFeesFinalizeRouteRegistered (0.NNs)

5. Write the report (§9), set `Status: review` in this file and commit "1585 step 5". Do not open a PR (one big PR mode). Report the SKIP count (must be 0).

## 5. Do not touch

`App/` (no Python file changes; the Python routes stay the live ones), `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, `go/internal/web/stayfees/handlers.go`, `i18n.json`, `helpers.go`, `go/cmd/ubyhost-web/register_web_stayfees.go`, `go/cmd/ubyhost-web/register_job_stay_fee_mail.go` and every existing file of the package. Hard rules of AGENTS.md: no secret or guest datum in a file or a log (the test data is made up), nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 2 and 4). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 6 files.
- [ ] The format, build and vet step printed nothing.
- [ ] The test step printed `ok` for both packages, and each of the 9 named tests printed `--- PASS` (none `SKIP`, none `FAIL`) on PostgreSQL.
- [ ] `git log --oneline --grep='^1585 step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1585 step') | tail -40` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed to `main`.
- [ ] UI: not applicable (rules 7 and 10): the route only redirects, no page or template is added, and it is dormant (no path routes to it).

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

Write `docs/tasks/1585-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git diff --stat` as in §7).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of: `finalize.go` (nothing is written before every check passed; `Save` is the only writer of the filing; the audit row follows the seal; a nil renderer returns before `Save`), `finalize_i18n.json` (texts copied from `host_i18n.py`), the register file (passes `stayFeeRenderer` as the package variable at registration time, see the note on the renderer).

## Owner steps

None for this brief: nothing is switched on. When the owner routes the path to Go, first check that brief 1580 has set `stayFeeRenderer` (otherwise the route answers with the flash described above and seals nothing), then add the path named in section 2 to `UBYHOST_GO_PATHS`.
