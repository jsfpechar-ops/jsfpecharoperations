# 1592: Go customer admin, part 3: the six "System problems" counts of the console home

Status: review
Depends on: 1591 | Base commit: none (one big PR mode: the branch that is checked out) | Branch: the current one
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (operator pages, billing and mail; no filing, no guest data)

> **One big PR mode.** The owner wants one big pull request for the whole Go port. You work on the branch that is checked out now. Never create a branch, never push, never open a PR, never call an `mcp__` tool. After each step that changes a file, commit with the message `1592 step k` (k is the step number) and nothing else in the first line; end the message with the two trailer lines from the session reminder if one is given. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1592 step'` and `git show --stat` on those commits.

## 1. Objective

Compute in Go the six counts that the operator console home (`GET /admin`, brief 1593) prints under "System problems": filings needing attention, stuck submissions, calendar feeds, background jobs, e-mail problems and open alerts, plus the number of open incident-review suggestions. They are read-only SQL; each is pinned against fixed seed rows and a fixed clock.

## 2. Context

Rules (AGENTS.md): 1 filing is not touched; 2 privacy: no new personal-data field and no new outbound request; 3 test data is made up (`@example.test`, test-only secrets); 4 no new dependency; 5 plain PostgreSQL through pgx with the Python SQL; 6 light mode, forms work without JavaScript; 8 never push to `main`; 11 Go first.

**PR text (hard rule 2):** read-only aggregate SQL; no new outbound request and no new personal-data field (the queries select no guest field, as Python's own `admin_ops` does not).

**All code is pre-written, compiled and tested.** Sidecars are `docs/tasks/1592-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Write nothing outside §3. No file of this brief replaces another brief's file.

**The thread (briefs 1590 to 1594).** Port the 7 routes of `App/app/routes/admin_customers.py` that Go does not serve yet (the file has 10 routes; briefs 1361, 1363 and 1364 ported `GET /admin/customers`, `GET /admin/customers/{user_id}` and `POST /admin/customers/{user_id}/aktivovat`; `GET /admin/funnel` is from brief 1361 and is not in that file) into the existing package `go/internal/web/customers` (package `customers`). Nothing routes to them until the owner adds the paths to `UBYHOST_GO_PATHS`.

| Brief | Routes (method path, Python function) | New files |
|---|---|---|
| 1590 | `POST /admin/customers/{user_id}/stav` (customer_status), `/prodlouzit` (customer_extend_trial), `/overit-znovu` (customer_resend_verification); the shared action guards | `actions.go`, `actions_account.go` |
| 1591 | `POST /admin/customers/{user_id}/sleva` (customer_discount), `/plan` (customer_plan), `/priradit` (customer_assign_plan) | `actions_billing.go`, `actions_invoicer.go` |
| 1592 | the six "System problems" counts of `admin_ops.overview()` (no route) | `ops.go` |
| 1593 | `GET /admin` (admin_home) with its template | `home.go`, `templates/admin_home.tmpl` |
| 1594 | registers the 7 routes in `go/cmd/ubyhost-web` and pins the route inventory (all 10 routes of the file) | `register_web_customers_test.go` |

**Order:** 1590, 1591, 1592, 1593, 1594, each `Depends on` the one before. The files `templates/i18n.json` and `templates/i18n_keys.txt` are named by 1590, 1591 and 1593: each brief replaces both with the version for its stage (1593's is the full catalog), so this order is the only valid one. Briefs 1360 to 1364 (customer admin list, detail, toggle) must already be in the branch; the billing engine (`go/internal/billing`, brief 1340), `go/internal/billingjob`, `go/internal/signup` and `billingweb.OperatorQueue` / `GetPortfolio` (brief 1341, `go/internal/web/billing/analytics.go`) are older still. The billing page thread 1555 to 1560 is not needed: 1593 reads only `OperatorQueue` and `GetPortfolio`, which exist since 1341.

**What this brief ports, with the Python lines (`App/app/admin_ops.py`, `App/app/scheduler.py`, `App/app/incidents.py`):**

Python builds the whole of `admin_ops.overview()` (298-325) for `GET /admin`, but `admin_home.html` prints only the six counts and the length of `incidents.open_review_alerts()`. Go computes only those seven numbers, with the same SQL, and leaves out the rows, the age columns, the ttlock block and every field the row builders read. The full `/admin/operations` page stays on Python.

| Go (`ops.go`) | Python | Count |
|---|---|---|
| `Ops` `Filings` | `filings_needing_attention` 80-124 | `COUNT(DISTINCT r.id)` of stays whose guest has `submit_state` `error` or `blocked`, or whose submission is `outcome_unknown` while the guest is not `sent` (guest and stay not archived) |
| `Ops` `Stuck` | `stuck_submissions` 127-157 | submissions `running` for more than 30 minutes (`RUNNING_STUCK_MINUTES`) |
| `Ops` `Feeds` | `feeds_needing_attention` 160-203 | active feeds of active, unarchived apartments whose last status is not `ok`, or never checked, or last checked more than 3 hours ago (`FEED_STALE_HOURS`) |
| `Ops` `Mail` | `mail_problems` 245-274 | outbox rows `failed`, `bounced`, `complained`, or `queued` since more than 30 minutes, or `sending` not updated for 30 minutes (`MAIL_STUCK_MINUTES`) |
| `Ops` `Alerts` | `open_alerts` 277-295 | the sum of the counts of the first 50 (kind, level) groups of unresolved alerts, ordered by count desc, kind (`ROW_LIMIT`) |
| `jobCount` `Jobs` | `job_health` 206-242 | jobs whose `job_last_ok:<job>` setting is missing or older than `late_after_minutes` (twice the interval, plus 15 minutes for an interval under 15), or that have an open `job_failed` alert (`job_failed:<job>`); 14 jobs, intervals from `scheduler.job_intervals()` (`jobIntervals`: `ical` and `submit` read `UBYHOST_ICAL_POLL_MINUTES` and `UBYHOST_SUBMIT_SWEEP_MINUTES`, defaults 60 and 10) |
| `ReviewAlertCount` | `incidents.open_review_alerts` 117-122 | unresolved alerts of kind `incident_review` |
| `parseOpsTime`, `ageMinutes` | `admin_ops.parse_time` 41-52, `age_minutes` 55-59 | ISO stamps with or without an offset (none means UTC), `Z` read as `+00:00`; anything else is "no time"; age is whole minutes, never negative |

**Known differences from Python (not fixed here, listed in every report):**

- F1. The six counts use the request time passed in by the caller; Python reads `datetime.now(utc)` inside each function, so two counts could straddle a second boundary there. No effect on a count that is not on a threshold.
- F2. `parseOpsTime` accepts the layouts the app writes (`YYYY-MM-DDTHH:MM:SS[.f][+hh:mm]`, space instead of `T`, a bare date); Python's `datetime.fromisoformat` of Python 3.12 accepts a few more exotic forms (week dates, basic format `20261113T101500`), which the app never writes. Such a value counts as "no time" in Go.

**Fixed numbers:** `TestOpsCounts` seeds a clock of 2026-11-13 12:00 UTC and pins each count against rows just inside and just outside every threshold (a submission running 29 and 31 minutes, a feed checked 2 h 59 and 3 h 01 ago, a queued mail 29 and 31 minutes old, a job whose last success is exactly `2 * interval` and one minute more, 51 alert groups so the limit of 50 bites); `TestOpsTimeHelpers` pins `parseOpsTime` and `ageMinutes` (negative age 0, offset, `Z`, junk).

**Verified by the brief writer** (fresh throwaway worktree of the branch head; briefs 1590 to 1592 copied in order exactly as their step 1 does): gofmt empty; `go build ./...` and `go vet ./internal/web/customers/... ./cmd/...` silent; `go test ./internal/web/customers/... ./cmd/ubyhost-web/...` ok on PostgreSQL 16 with the two named tests PASS and 0 skipped. Every query was read against `admin_ops.py` 80-295 and the job intervals and threshold against `scheduler.py` 86-122; no divergence other than F1 and F2. Not run: any Python test.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/customers/ops.go` | create | `OpsCounts`, `Ops`, `jobCount`, `ReviewAlertCount`, `jobIntervals`, `lateAfterMinutes`, `parseOpsTime`, `ageMinutes` |
| `go/internal/web/customers/ops_test.go` | create | `TestOpsCounts`, `TestOpsTimeHelpers` |
| `docs/tasks/1592-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1592-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git log --oneline --grep='^1591 step' | tail -3` prints at least one line (brief 1591 is in this branch).
   - `ls go/internal/web/customers/actions_billing.go go/internal/web/customers/actions_invoicer.go 2>&1 | tail -2` lists both files of brief 1591.
   - `ls go/internal/web/customers/ops.go 2>&1 | tail -1` says "No such file".
   - `grep -cF "func stamp(t time.Time) string {" go/internal/web/customers/handlers.go | tail -1` prints `1` (`ops.go` calls it).
   - `grep -cF "func dbPool(t *testing.T) *pgxpool.Pool {" go/internal/web/customers/query_test.go | tail -1` prints `1`, and `grep -cF "func seed(t *testing.T, pool *pgxpool.Pool, g goldenFile) {" go/internal/web/customers/query_test.go | tail -1` prints `1` (the test helpers `ops_test.go` uses).
   - `find docs/tasks/1592-files -name '*.txt' | wc -l | tail -1` prints `2`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1592-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   f03818147ae5fe584f702177d44ca7fcf1aba08310b0e4ebd4f21c9183442285  go/internal/web/customers/ops.go
   e3c733f602f811a581a3c05098dbe1521d5e80342909de32c257a96ecfde0a43  go/internal/web/customers/ops_test.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1592 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/customers cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/customers/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). No commit (nothing changed).

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1592 && chown postgres /var/tmp/pg1592 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1592/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1592/data -o "-p 55592 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1592" -l /var/tmp/pg1592/log -w start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55592/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55592/postgres go test ./internal/web/customers/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: two lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/customers	<seconds>s` and `ok  	...go/cmd/ubyhost-web	<seconds>s`. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55592/postgres go test ./internal/web/customers/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestOpsCounts$|^TestOpsTimeHelpers$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -40
   ```

   Expected: one `--- PASS` line for each of the 2 tests (TestOpsCounts, TestOpsTimeHelpers), then `ok` lines; no `--- SKIP`, no `--- FAIL`. Then count skips in the whole run and write the number in the report: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55592/postgres go test ./internal/web/customers/ ./cmd/ubyhost-web/ -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` must print `0`.

5. Stop and delete the throwaway server (skip if you used a server you did not start):

   ```bash
   su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1592/data -m fast stop' 2>&1 | tail -2; rm -rf /var/tmp/pg1592
   ```

   Expected: `server stopped`.

6. Write the report (§9), set `Status: review` and commit "1592 step 6".

## 5. Do not touch

`go/internal/hostweb/`, `go/internal/session/`, `go/internal/billing/`, `go/internal/billingjob/`, `go/internal/signup/`, `go/internal/web/billing/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `registry.go` and every `register_*.go` that is not named in §3, the existing files of `go/internal/web/customers/` that briefs 1361 to 1364 created (`detail.go`, `handlers.go`, `handlers_test.go`, `pages.go`, `pages_test.go`, `query.go`, `query_test.go`, `testdata/`, the existing templates), `App/` (no Python file, no `App/tests/conftest.py`), `docs/context/*`, and every file not in §3. AGENTS.md rules that apply: 2 (privacy), 3 (no real data in tests), 4 (no new dependency: `go.mod` and `go.sum` stay as they are), 5 (SQL is plain PostgreSQL through pgx, taken from the Python), 8 (never push to `main`), 11 (Go first: no file under `App/app/` is named in §3, so no exception of go-first applies).

## 6. Commands

Exactly the commands of §4 (steps 1, 2, 4, 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 2 files.
- [ ] Step 2 printed nothing.
- [ ] Step 4 printed the `ok` lines, each of the 2 named tests printed `--- PASS`, and the skip count is `0` (none `SKIP`, none `FAIL`).
- [ ] `git log --oneline --grep='^1592 step' | tail -5` lists at least the step 1 commit, and `git show --stat --format=%h <that hash> | tail -20` lists only paths of §3.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed. There is no route in this brief.
- [ ] UI: not applicable (no template or page in this brief).

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

Write `docs/tasks/1592-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git log --oneline --grep='^1592 step' | tail -10`, then one `git show --stat --format=%h <hash>` per commit).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `ops.go`: each SQL against the Python one (the `filings` condition `g.submit_state <> 'sent'`, the `LIMIT 50` inside the `alerts` sum, the strict `<` on every cutoff), `lateAfterMinutes`, and that `jobIntervals` lists the same 14 jobs as `scheduler.job_intervals()`. A job added to Python later must be added here.

## Owner steps

None here (no route).
