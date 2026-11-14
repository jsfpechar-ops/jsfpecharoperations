# 1586: Go stay fees: seal every ready period (POST /stay-fees/confirm-ready)

Status: todo
Depends on: 1330, 1242a (stayfee.Save and Check), 1580 (the real PDF renderer, only needed for production, not for the tests) | Base commit: current tip of the working branch | Branch: task/1586-go-stay-fee-confirm-ready
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1586 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1586 step'` and `git show --stat <commit>`, never a fixed base commit.

## 1. Objective

Add `POST /stay-fees/confirm-ready` to `go/internal/web/stayfees`: it seals the clean period of every listed property of the host for one month, flashes the count and redirects. Dormant until the owner routes the path.

## 2. Context

Rules (AGENTS.md): 1 filing correctness: the seal is the existing `stayfee.Save` (brief 1242a), this brief only calls it; 2 privacy: no new personal-data field, no new retention line, no outbound request; 3 fixtures are made up (`@example.test`, test-only keys); 4 no new dependency (stdlib, pgx and packages already in `go.mod`); 5 plain PostgreSQL through `pgxpool`, no schema change; 6 light mode, no page is added; 11 Go first (this brief is the Go port; no file under `App/app/` changes).

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The route writes through the existing seal code: encrypted PDF, CSV and payload with the same data keys as Python.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1586-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `665e4190945d92bfccfb93c40adfa6faaa6fac2a26e40b4846508e3c1e4c4ae6` | `go/cmd/ubyhost-web/register_web_stayfees_confirm.go` | create | 22 |
| `5801ea6d48a1911aa8099ba949e23f2b88c157bea67e6492b07d2c536dd9c4ba` | `go/cmd/ubyhost-web/register_web_stayfees_confirm_test.go` | create | 15 |
| `25de1212524a81d6881f7ed62d9a119c53b1c68834cb7b73a03551c7de05a979` | `go/internal/web/stayfees/confirm.go` | create | 155 |
| `332896144858757ea7ccc076570469899cd712ccba3dcd6ca0870b7beb42d12a` | `go/internal/web/stayfees/confirm_i18n.json` | create | 10 |
| `8044e411edbd2113f083a87b6d86ccf5e8e88ebb81efb269bce22da4d078892a` | `go/internal/web/stayfees/confirm_test.go` | create | 391 |

**How the code is built.** `confirm.go` holds `ConfirmReadyHandler(pool, getenv, now, renderer)` and `confirmOne`. `confirmOne` repeats the steps of `stayfee.Confirm` (`Check`, `Latest`, `Save` with the calculated amounts, the same refusals) but writes the audit row of a signed-in request (`c.audit`: the username as actor, the account id, the workspace as owner, the impersonator). `stayfee.Confirm` itself writes the job's audit row (actor `host`, no user) and cannot be used for a web request. The two flash texts are in `confirm_i18n.json` (embedded, `confirmCatalog`). The Fernet encrypter and decrypter are built from `secure.LoadDataKeys(getenv)` as the `stay_fee_mail` job does.

**Renderer.** Nil renderer, decided here: `ConfirmReadyHandler` takes the renderer as a parameter. When it is nil the handler shows the `bulk_none` error flash ("No period was ready to save.") with a log line and redirects; nothing is sealed, no apartment is read and no audit row is written. The register file passes the package variable `stayFeeRenderer`, which the closure reads when the mux is built (after all `init`s, so after brief 1580 has set it).

**Parity notes (Python `App/app/routes/stay_fees.py` unless named):**

| Python (`stay_fees.py` / `stay_fee_auto.py`) | Go (`confirm.go`) |
|---|---|
| `stay_fee_confirm_ready` 1198-1231: login, month, clamp to the current month | `ConfirmReadyHandler`: `enter`, `c.month()`, `defaultMonth` |
| `fee_return_path(return_to, 0) or "/stay-fees"` | `feeReturnPath(.., 0)` |
| loop over `form.getlist("apartment_id")`: strip, `isdigit`, dedupe by text | the loop over `c.r.PostForm["apartment_id"]` |
| `access.apartment`, `is_active`, `archived_at`, `active` | `apartmentOf`, `isActive`, `Archived`, `SELECT active` |
| `stay_fee_auto.confirm(..., audit_event="stay_fee_finalize")` | `confirmOne` |
| `bulk_saved` with count / `bulk_none` | `confirmCatalog` |

Details that are easy to get wrong and are tested: a month after the current one is replaced by the current month (which is not over, so nothing is ready); the ids are read from every `apartment_id` value, stripped, ASCII digits only, each text once; an id that is foreign, missing, without a fee, archived or switched off (`active = 0`) is skipped without a message; a blocked period (any check issue), an already sealed one, and a refused `Save` (inactive, overlap, changed, duplicate, any integrity error) are skipped, never changed; the sealed amounts are the calculated ones (no form amounts); the audit row event is `stay_fee_finalize`, detail `apartment_id=N period=KEY`, written once per sealed period after its `Save`; zero sealed shows the `bulk_none` error, otherwise the `bulk_saved` message with the count; `return_to` is honoured only for `/stay-fees` or `/stay-fees/0` paths.

**Known differences from Python, shared by every Go web area (not fixed here):** a missing or foreign record answers the not-found flash redirect as the sibling routes do; a non-integer id answers `422 {"detail":"Unprocessable Entity"}`; a repeated form key reads the last value (as Starlette does) except `apartment_id`, which reads every value; Python's `isdigit()` also accepts non-ASCII digits, Go's check is ASCII only.

**Paths that become fully served by Go:** `POST /stay-fees/confirm-ready`. **Goes live on deploy if** that path is already routed to Go (assumed not). It also needs the real renderer of brief 1580 (`stayFeeRenderer`); until then the route seals nothing.

**Anchors that must exist verbatim** (step 0).

**Verified by the brief writer** (in a worktree of go-wave3, the sidecars copied as step 1 does): `gofmt -l` printed nothing, `go build ./...` and `go vet ./internal/web/stayfees/ ./cmd/...` were silent, and `go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1 -v` passed on PostgreSQL 16 (port 55585) with 0 `--- SKIP` lines, the golden test `TestActionsMatchPython` of brief 1330 still green, and the named tests PASS. Both new briefs (1585 and 1586) were also checked alone: with the files of the other brief removed the package still vets. The two new briefs share no file; the existing 1330 golden test and the stay-fee mail tests were part of the same run.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_stayfees_confirm.go` | create | registers `POST /stay-fees/confirm-ready` with `stayFeeRenderer` |
| `go/cmd/ubyhost-web/register_web_stayfees_confirm_test.go` | create | route registration test |
| `go/internal/web/stayfees/confirm.go` | create | `ConfirmReadyHandler`, `confirmOne` |
| `go/internal/web/stayfees/confirm_i18n.json` | create | the two flashes of this route (cs, en), from `App/app/host_i18n.py` |
| `go/internal/web/stayfees/confirm_test.go` | create | route tests on PostgreSQL (fake renderer) |
| `docs/tasks/1586-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1586-report.md` | create | the report (§9) |

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
   - `grep -cF "async def stay_fee_confirm_ready(request: Request):" App/app/routes/stay_fees.py | tail -1` prints `1`.
   - `ls go/internal/web/stayfees/confirm.go 2>&1 | tail -1` says "No such file" (nothing of this brief exists yet).
   - `ls go/internal/stayfeemail/testdata/stay_fee_job_golden.json | tail -1` prints the path (the test fixture).
   - `find docs/tasks/1586-files -type f | wc -l | tail -1` prints `5`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1586-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -7
   665e4190945d92bfccfb93c40adfa6faaa6fac2a26e40b4846508e3c1e4c4ae6  go/cmd/ubyhost-web/register_web_stayfees_confirm.go
   5801ea6d48a1911aa8099ba949e23f2b88c157bea67e6492b07d2c536dd9c4ba  go/cmd/ubyhost-web/register_web_stayfees_confirm_test.go
   25de1212524a81d6881f7ed62d9a119c53b1c68834cb7b73a03551c7de05a979  go/internal/web/stayfees/confirm.go
   332896144858757ea7ccc076570469899cd712ccba3dcd6ca0870b7beb42d12a  go/internal/web/stayfees/confirm_i18n.json
   8044e411edbd2113f083a87b6d86ccf5e8e88ebb81efb269bce22da4d078892a  go/internal/web/stayfees/confirm_test.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1586 step 1".

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
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55585/postgres go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestConfirmReadySealsCleanPeriods$|^TestConfirmReadyNothingToSeal$|^TestConfirmReadyReturnTo$|^TestConfirmReadyNeedsLoginAndCSRF$|^TestConfirmReadyNilRenderer$|^TestConfirmReadyOverlap$|^TestStayFeesConfirmReadyRouteRegistered$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of 7 tests (times differ) and two final `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestConfirmReadySealsCleanPeriods (0.NNs)
   --- PASS: TestConfirmReadyNothingToSeal (0.NNs)
   --- PASS: TestConfirmReadyReturnTo (0.NNs)
   --- PASS: TestConfirmReadyNeedsLoginAndCSRF (0.NNs)
   --- PASS: TestConfirmReadyNilRenderer (0.NNs)
   --- PASS: TestConfirmReadyOverlap (0.NNs)
   --- PASS: TestStayFeesConfirmReadyRouteRegistered (0.NNs)

5. Write the report (§9), set `Status: review` in this file and commit "1586 step 5". Do not open a PR (one big PR mode). Report the SKIP count (must be 0).

## 5. Do not touch

`App/` (no Python file changes; the Python routes stay the live ones), `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, `go/internal/web/stayfees/handlers.go`, `i18n.json`, `helpers.go`, `go/cmd/ubyhost-web/register_web_stayfees.go`, `go/cmd/ubyhost-web/register_job_stay_fee_mail.go` and every existing file of the package. Hard rules of AGENTS.md: no secret or guest datum in a file or a log (the test data is made up), nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 2 and 4). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 5 files.
- [ ] The format, build and vet step printed nothing.
- [ ] The test step printed `ok` for both packages, and each of the 7 named tests printed `--- PASS` (none `SKIP`, none `FAIL`) on PostgreSQL.
- [ ] `git log --oneline --grep='^1586 step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1586 step') | tail -40` lists only the paths of §3 and the sidecars.
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

Write `docs/tasks/1586-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git diff --stat` as in §7).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of: `confirm.go` (`confirmOne` seals only when `Check` found no issue and no live filing exists; every id is checked against the host's own apartments before anything is read; a nil renderer returns before any apartment is read), `confirm_i18n.json` (texts copied from `host_i18n.py`), the register file.

## Owner steps

None for this brief: nothing is switched on. When the owner routes the path to Go, first check that brief 1580 has set `stayFeeRenderer` (otherwise the route answers with the flash described above and seals nothing), then add the path named in section 2 to `UBYHOST_GO_PATHS`.
