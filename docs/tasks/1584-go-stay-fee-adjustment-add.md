# 1584: Go stay fee adjustment add (POST /stay-fees/{apartment_id}/adjustment)

Status: todo
Depends on: 1240, 1242, 1330 | Base commit: current tip of the working branch | Branch: task/1584-go-stay-fee-adjustment-add
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1584 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1584 step'` and `git show --stat <commit>`, never a fixed base commit.

## 1. Objective

Add `POST /stay-fees/{apartment_id}/adjustment` (`stay_fee_adjustment_add` and `_adjustment_bed_days`) to `go/internal/web/stayfees`: a host adds or removes bed-days for one stay fee period, or for a sealed period through a correction. The undo route already exists (`UndoHandler`). Dormant until the owner routes the path.

## 2. Context

Rules (AGENTS.md): 1 filing correctness: the bed-days a correction adds are read back by the sealing code, so the stored period key must be the sealed period's key (tested, see below); the sealing code itself is not touched; 2 privacy: no new personal-data field, no new retention line, no outbound request (the free-text reason is stored encrypted, as Python does, and stays out of the audit row); 3 fixtures are made up (`@example.test`, a test-only data key); 4 no new dependency; 5 plain PostgreSQL through `pgxpool`, no schema change; 6 light mode (no page here); 11 Go first (no file under `App/` changes).

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The reason text is Fernet-encrypted into `stay_fee_adjustment.reason_enc`; the audit row holds ids, period, direction and days only.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1584-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `ad2f0d5ee922de0dd8dc27985cc00b54429795a15f7c411902a419e3ac0f8e88` | `go/cmd/ubyhost-web/register_web_stayfees_adjust.go` | create | 25 |
| `3c07d1c7015d55075ceb2a15349305cdb8f80f6e42fc5404d10b4c130d29bf8c` | `go/cmd/ubyhost-web/register_web_stayfees_adjust_test.go` | create | 16 |
| `25de54d1ea4b8cdb077df9971e23865ff1660f2056c154a55ccbfbe19e8dfb48` | `go/internal/web/stayfees/adjust.go` | create | 232 |
| `c8b2102daf47c85aa3a51105dd7066fcc560db625dc47ee271e5d4ed4f247890` | `go/internal/web/stayfees/adjust_i18n.json` | create | 17 |
| `a42cbeb237fb1b69a11266a75c01612f4bff03ae51b4cc464d3ac1faa4929340` | `go/internal/web/stayfees/adjust_test.go` | create | 458 |

**How the code is built.** `adjust.go` holds `AdjustmentAddHandler`, `AdjustRoutes`, `(*call).adjustmentBedDays` (`_adjustment_bed_days`), `pyInt` (Python's `int()` on a stripped string) and the embedded catalog of three flash texts (`adjust_i18n.json`, generated from `App/app/host_i18n.py`: `flash.stay_fees.adjust_invalid`, `adjust_negative`, `adjust_frozen`; `i18n.json` is not edited, and `flash.stay_fees.saved`, `report_blocked` and `error.no_such_apartment` come from it). The write is `stayfee.AddAdjustment` (brief 1242), the period figures `stayfee.PropertyPeriod`, `stayfee.CorrectionRate`, `stayfee.NetBedDays`. CSRF, login, flash and redirect handling are `deps.enter`, `call.flash` and `call.back`, the same as `UndoHandler`.

**Parity notes (Python `App/app/routes/stay_fees.py`):**

| Route | Python | Go |
|---|---|---|
| `POST /stay-fees/{apartment_id}/adjustment` | `stay_fee_adjustment_add` 1022-1100 | `AdjustmentAddHandler` |
| bed-days of the form | `_adjustment_bed_days` 1008-1019 | `(*call).adjustmentBedDays` |
| the insert | `App/app/stay_fee_adjustment.py` `add` 39-65 | `stayfee.AddAdjustment` |

Details that are easy to get wrong and are tested:

- Order: CSRF, login, the property (a foreign, missing, out-of-range or rate-less property is a 303 to `/stay-fees` with `flash.error.no_such_apartment`; an archived property that still has a rate passes, because Python checks only the rate), then the month, then the period, then the form.
- `month` is the posted month or the current Prague month. The back link is `/stay-fees/{id}?month=<m>`; for a correction it ends `&correct=1` (not for the "no sealed filing" refusal).
- `correct=1`: needs a sealed filing covering the month, else `flash.stay_fees.report_blocked`. The row is stored under the sealed period's cadence and key (a quarterly seal `2026-Q3` files under `2026-Q3` for any month in the quarter), and the figures are recalculated with `CorrectionRate`. Without `correct`, a sealed period answers `adjust_frozen`; otherwise the key uses the property's current cadence.
- Validation order: direction `add` or `remove`, mode `people` or `bed_days`, reason of at least 3 characters after stripping, else `adjust_invalid`; people mode needs people 1-99 and nights 1-366 (bed-days is their product), bed-days mode 1-9999; the numbers follow Python `int()` (`1_0` and `+7` are accepted, `1.5`, `1__0`, an empty value and a number too large are refused). A mode `people` row stores `people_count` and `nights`, a `bed_days` row stores NULL for both.
- Negative check: guest liable nights plus the net open corrections plus the new delta must stay at 0 or more, else `adjust_negative`; a reversed correction no longer counts.
- The reason is the stripped text cut to 200 characters, encrypted; `created_by` is the workspace owner (also for an admin working inside the workspace; the audit row then names the admin as impersonator); `created_at` is the request time as `...+00:00`.
- Audit `stay_fee_adjustment`: `apartment_id=<id> period=<key> direction=<d> days=<n>`; redirect with `flash.stay_fees.saved`. A refusal writes no row and no audit.

**Known differences from Python, shared by every Go web area (not fixed here):** a non-integer path id is a `422 {"detail":"Unprocessable Entity"}`; Python's `int()` also accepts non-ASCII digits, Go's parser takes ASCII only; the "today" the rate schedule uses is the UTC date of the request (as `stayfeemail`); a missing CSRF token is the shared 403 of `hostweb.CSRF`. No golden file is added: the Python golden script needs the Python virtualenv, which is not part of this brief, so the expectations are written from the Python code and asserted in `adjust_test.go` (rows, redirect, audit).

**Paths that become fully served by Go:** `POST /stay-fees/*/adjustment` (one segment; `/adjustment/*/undo` is already Go). **Goes live on deploy if** this path is already routed to Go (assumed not).

**Anchors that must exist verbatim** (step 0): the Python and Go function lines listed there.

**Verified by the brief writer** (in a throwaway worktree of `go-wave3`, steps applied exactly and in order, sidecars copied as step 1 does): `gofmt -l` printed nothing, `go build ./...` and `go vet ./internal/web/stayfees/... ./cmd/...` were silent, and `go test ./internal/web/stayfees/... ./cmd/ubyhost-web/... -count=1` passed on PostgreSQL 16 with the golden test of brief 1330 still green and 0 skipped tests. The tests cover: a saved adjustment (stored row, decrypted stripped reason, audit, redirect with the saved text, people mode counts, 200-character cut, `1_0`/`+7`/`9999`, admin inside the workspace), the default month, 20 invalid forms (no row, no audit, Czech text), the negative check (including a reversed correction and zero net), the frozen period, corrections (no seal, monthly seal key, `&correct=1`, quarterly seal key `2026-Q3`), and the refusals (foreign, missing, out-of-range, rate-less, text id, signed out, other host, bad CSRF, GET, archived with rate).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_stayfees_adjust.go` | create | registers the route |
| `go/cmd/ubyhost-web/register_web_stayfees_adjust_test.go` | create | route registration test |
| `go/internal/web/stayfees/adjust.go` | create | the handler |
| `go/internal/web/stayfees/adjust_i18n.json` | create | three flash texts (cs, en, vi) |
| `go/internal/web/stayfees/adjust_test.go` | create | route tests |
| `docs/tasks/1584-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1584-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `git log --oneline --grep='^1330 step' | wc -l | tail -1` prints a number of 1 or more (brief 1330 is on this branch).
   - `grep -cF "async def stay_fee_adjustment_add(apartment_id: int, request: Request):" App/app/routes/stay_fees.py | tail -1` prints `1`.
   - `grep -cF "def _adjustment_bed_days(form) -> int:" App/app/routes/stay_fees.py | tail -1` prints `1`.
   - `grep -cF "func UndoHandler(" go/internal/web/stayfees/handlers.go | tail -1` prints `1`.
   - `grep -cF "func AddAdjustment(" go/internal/stayfee/adjust.go | tail -1` prints `1`.
   - `grep -cF "func PropertyPeriod(" go/internal/stayfee/loader.go | tail -1` prints `1`.
   - `grep -cF "func CorrectionRate(" go/internal/stayfee/filing.go | tail -1` prints `1`.
   - `grep -cF "func NetBedDays(" go/internal/stayfee/loader.go | tail -1` prints `1`.
   - `grep -cF "func FernetEncrypter(" go/internal/stayfee/save.go | tail -1` prints `1`.
   - `ls go/internal/web/stayfees/adjust.go 2>&1 | tail -1` says "No such file" (nothing of this brief exists yet).
   - `find docs/tasks/1584-files -type f | wc -l | tail -1` prints `5`.

1. Copy the sidecars and check them (one call, repo root). The sidecar names end in `.txt` (also the JSON one, `adjust_i18n.json.txt`). Never retype or edit them:

   ```bash
   cd docs/tasks/1584-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -6
   ad2f0d5ee922de0dd8dc27985cc00b54429795a15f7c411902a419e3ac0f8e88  go/cmd/ubyhost-web/register_web_stayfees_adjust.go
   3c07d1c7015d55075ceb2a15349305cdb8f80f6e42fc5404d10b4c130d29bf8c  go/cmd/ubyhost-web/register_web_stayfees_adjust_test.go
   25de54d1ea4b8cdb077df9971e23865ff1660f2056c154a55ccbfbe19e8dfb48  go/internal/web/stayfees/adjust.go
   c8b2102daf47c85aa3a51105dd7066fcc560db625dc47ee271e5d4ed4f247890  go/internal/web/stayfees/adjust_i18n.json
   a42cbeb237fb1b69a11266a75c01612f4bff03ae51b4cc464d3ac1faa4929340  go/internal/web/stayfees/adjust_test.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1584 step 1".

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
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55583/postgres go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestAdjustmentAddSaves$|^TestAdjustmentAddNoMonthUsesCurrentMonth$|^TestAdjustmentAddInvalid$|^TestAdjustmentAddNegativeAndFrozen$|^TestAdjustmentAddCorrection$|^TestAdjustmentAddRefusals$|^TestStayFeesAdjustRouteRegistered$' 2>&1 | grep -aE '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of 7 tests (times differ) and two final `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestAdjustmentAddSaves (0.NNs)
   --- PASS: TestAdjustmentAddNoMonthUsesCurrentMonth (0.NNs)
   --- PASS: TestAdjustmentAddInvalid (0.NNs)
   --- PASS: TestAdjustmentAddNegativeAndFrozen (0.NNs)
   --- PASS: TestAdjustmentAddCorrection (0.NNs)
   --- PASS: TestAdjustmentAddRefusals (0.NNs)
   --- PASS: TestStayFeesAdjustRouteRegistered (0.NNs)

   Report the SKIP count (it must be 0): `go test ... -v 2>&1 | grep -ac -- '--- SKIP'`.

5. Write the report (§9), set `Status: review` in this file and commit "1584 step 5". Do not open a PR (one big PR mode); the owner or the orchestrator opens it with the PR text of §2.

## 5. Do not touch

`App/` (no Python file changes; the Python routes stay the live ones), `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, `go/internal/web/stayfees/handlers.go`, `i18n.json`, `testdata/actions_golden.json`, `go/cmd/ubyhost-web/register_web_stayfees.go`, `go/internal/stayfee/**` and every other existing file. Hard rules of AGENTS.md: no secret or guest datum in a file or a log (the test data is made up), nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 2 and 4). The test-map row for `go/internal/web/stayfees` already exists; the coordinator adds the new test names from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 5 files.
- [ ] The format, build and vet step printed nothing.
- [ ] The test step printed `ok` for both packages, and each of the 7 named tests printed `--- PASS` (none `SKIP`, none `FAIL`) on PostgreSQL; the SKIP count is 0.
- [ ] `git log --oneline --grep='^1584 step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1584 step') | tail -40` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed to `main`.
- [ ] UI: not applicable (rules 7 and 10): the route answers with a redirect, no template changes; it is dormant until the owner routes the path.

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

Write `docs/tasks/1584-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git diff --stat` as in §7).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of: `adjust.go` (the property is reached through the owner-scoped `pathApartment` before any read or write; for a correction the key comes from the sealed filing, never from the live cadence; the insert and the audit row come last, after every refusal; the reason is encrypted and not logged), `adjust_i18n.json` (texts equal `App/app/host_i18n.py` lines 754-756 and 2914-2916 and the Vietnamese ones), the registration file (one pattern, no duplicate).

## Owner steps

None: nothing is switched on. The path switch for `POST /stay-fees/*/adjustment` goes together with the stay fee detail page (brief 1582), which holds the form that posts here.
