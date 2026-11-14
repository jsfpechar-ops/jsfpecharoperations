# 1508: Go auth, the operator's System page GET /admin/operations (dormant)

Status: todo
Depends on: 1282 (auth `Routes`, `d.admin`, the incident POSTs) and 1430-1434 (Go Havel: `havelGuideAnchors`, `HavelFeature`, `go/internal/anthropic`), both already on go-wave3. No 1501 helper is used. | Base commit: 859d114d5 | Branch: go-wave3
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

**One big PR mode.** Work on the branch that is checked out now (go-wave3). Never create a branch, never push, never open a PR, no `mcp__` tools. Commit after each step that changes a file with the message `1508 step k` (k = the step number), and the report as `1508 report`. The orchestrator opens the PR.

**One brief, not two.** The split plan (1500 §4) said this page "may need two briefs". It does not: all code is pre-written in sidecars and proven against the real Python page, so the executor only copies files, runs one edit script and runs tests.

## 1. Objective

Serve `GET /admin/operations` (the operator's System page: filings, stuck reports, calendars, background jobs, mail, TTLock, open alerts, Havel gaps and spend, the security incident register) from Go, with the same HTML as Python's `admin_operations.html`. Tier A: the page is read-only and dormant (no path switch), and its visible lines are proven equal to the Python page on five seeded cases.

## 2. Context

Rules (AGENTS.md): 2 privacy: no new personal-data field and no outbound request; the page reads only aggregates, no guest field, no feed URL, no mail recipient (as `admin_ops.py` says in its docstring); the incident drafts show the controllers' contact e-mails, exactly as Python. 3 test data is made up (`@example.test`). 4 no new dependency: `golang.org/x/text` is already a direct requirement in `go/go.mod` (line 12); `golang.org/x/text/cases` is a package of that module, so `go.mod`/`go.sum` do not change (`go mod tidy -diff` is empty). 5 plain PostgreSQL through pgx, the SQL of `admin_ops.py` with `$n` placeholders; no schema change. 11 go-first: `App/scripts/admin_operations_golden.py` and `App/tests/test_go_admin_operations_golden.py` are port plumbing (go-first exception 1: golden scripts and parity tests). No file under `App/app/` changes.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The Go page shows what the Python page shows, to an operator only.

**The code is in sidecar files.** `docs/tasks/1508-files/<repo path>.txt` holds every new file; `docs/tasks/1508-files/edit_shared.py` makes the three edits of shared files. Never type or edit the code.

**What the Python route does** (`App/app/routes/admin_accounts.py` 929-950, `operations_admin`): `_require_admin`, then `render("admin_operations.html", ops=admin_ops.overview(), havel_ops=havel.admin_overview(), rows=[{incident, draft}] for incidents.list_all(), review_alerts=incidents.open_review_alerts(), owners=SELECT id, username FROM user_account ORDER BY username)`.

**Every query the page needs, and its Go port** (all in `go/internal/web/auth/opspage/data.go` unless named):

| Block | Python | Go |
|---|---|---|
| Filings needing attention | `admin_ops.filings_needing_attention` 77-121: `COUNT(DISTINCT r.id)` and the per-stay list over `guest` ⋈ `reservation` ⋈ `apartment` ⟕ `submission` ⟕ `user_account`, severity 3/2/1/0 folded in SQL, `ORDER BY severity DESC, since ASC LIMIT 50`; params `reporting.ERROR/BLOCKED/SENT` (`reporting.py` 48-50), `SUBMISSION_MAX_AUTO_ATTEMPTS` (134) | `loadFilings`, `ubyport.SubmissionMaxAutoAttempts` (`go/internal/ubyport/outcome.go` 14) |
| Reports stuck in sending | `stuck_submissions` 124-150: `state = 'running' AND created_at < now-30 min` | `loadStuck` |
| Calendars | `feeds_needing_attention` 155-193: active feed on an active, unarchived property, status not `ok` or last check (`COALESCE(last_checked_at, last_sync_at)`) missing or older than 3 h; never-checked first | `loadFeeds` |
| Background jobs | `job_health` 198-232, `scheduler.job_intervals` 86-107 (ical and submit from `UBYHOST_ICAL_POLL_MINUTES` / `UBYHOST_SUBMIT_SWEEP_MINUTES`, `config.py` 315, 318), `late_after_minutes` 119-122, `settings` keys `job_last_ok:<job>`, open `job_failed` alerts `LIMIT 50` | `loadJobs`, `jobIntervals`, `lateAfterMinutes` |
| Mail problems | `mail_problems` 237-265: failed/bounced/complained, queued over 30 min, sending not updated for 30 min; no recipient | `loadMail` |
| Open alerts | `open_alerts` 270-288: unresolved, `GROUP BY kind, level ORDER BY n DESC, kind LIMIT 50` | `loadAlerts` |
| TTLock | `overview` 291-325: `lock_api_usage` this UTC month (`ttlock.calls_this_month` 130-139), `door_code` issued since the 1st (UTC) and failed/revoke_failed, `UBYHOST_TTLOCK_MONTHLY_CALLS` (default 30000), `UBYHOST_DOOR_CODES`, `UBYHOST_DOOR_CODES_LIVE` (`config.py` 335, 339, 365) | `loadTTLock` |
| Havel | `havel.admin_overview` 643-654, `gap_groups` 614-640, `normalise_question` 602-605, `guide_section` 608-611, `GAP_REASON_KEYS`, `GUIDE_FOR_PAGE` 586-597: spend this month vs `UBYHOST_AI_MONTHLY_USD_HAVEL`, `havel_stats` of the last 30 days, the last 2000 `havel_gap` rows grouped | new `go/internal/web/ai/havel_ops.go`: `HavelAdminOverview`, `HavelGapGroups`, `HavelNormaliseQuestion`; reuses `havelGuideAnchors` (`havel_data.go` 112), `HavelFeature` (58) and `anthropic.Service` (`Today`, `MonthSpendUSD`, `Cfg.MonthlyUSD`, `Enabled`) |
| Incident register | `incidents.list_all` 28-31 (`ORDER BY detected_at DESC, id DESC`), `controller_notification_draft` 86-117 (contacts from `legal_entity` per affected owner), `affected_owner_ids` 38-42, `open_review_alerts` 120-125 | `LoadIncidents`, `Draft`, `ownerIDs`, `LoadReviewAlerts` |
| Affected hosts checklist | `SELECT id, username FROM user_account ORDER BY username` | `LoadOwners` |

**The new files:**

- `go/internal/web/auth/opspage/` (package `opspage`): `data.go` (the reads above), `page.go` (`Serve`: the view, the template macros `age` and `workspace_link`, Jinja's `capitalize`, the System tab), `templates/admin_operations.tmpl` (Go twin of the 267-line template, rendered through `layout.Render`, read-only), `i18n_keys.txt` and `i18n.json` (the page's strings, written by `App/scripts/go_host_i18n.py`, which globs every `go/internal/**/i18n_keys.txt`; a sub-package keeps this catalog apart from `auth/i18n.json`, which sibling briefs regenerate), `page_test.go`, `testdata/admin_operations_golden.json`.
- `go/internal/web/auth/operations.go`: `operationsAdmin` = `d.admin` (the existing `_require_admin`, `admin.go` 34-42) then `opspage.Serve`. `operations_test.go`: the route is listed once and a signed-out visitor gets 303 `/login?next=/admin/operations` with no body.
- `go/internal/web/ai/havel_ops.go`: see the Havel row.
- `App/scripts/admin_operations_golden.py`: seeds a throwaway SQLite database, signs in as the admin through TestClient, freezes the clock of `admin_ops`, `ttlock` and `ai` at 2026-11-13 12:00 UTC and renders the real Python page for five cases (full data in en/cs/vi with door codes live, off, test mode and Havel on/off, and empty data in en/cs). It keeps `visible_lines` of the page area (`div.ui-page`): each text run and each tag with one of 20 attributes (id, href, action, name, value, class, open, disabled, data-label, ...). It also pins the five drafts byte for byte and `normalise_question`, `age_minutes`, `capitalize`, `late_after_minutes` on fixed inputs. `App/tests/test_go_admin_operations_golden.py` fails when the golden file is stale.

**Edits of shared files** (`edit_shared.py`, written like 1509's `edit_routes.py` so it applies whatever siblings 1502-1510 already did; each edit refuses to run twice):

1. `go/internal/web/auth/auth.go` `Routes`: appends `{"GET /admin/operations", "/admin/operations", d.operationsAdmin},` at the end of the slice, after any rows other briefs added.
2. `go/internal/web/auth/auth_test.go` `TestRoutesBuildWithoutPool`: the route count becomes one more than it is now (18 -> 19 on the base commit).
3. `deploy/lightsail/docker-compose.yml`, service `ubyhost-go`, `environment:`: seven bare keys, each in alphabetical place: `UBYHOST_AI_MONTHLY_USD_HAVEL`, `UBYHOST_AI_PRICE_CACHE_READ`, `UBYHOST_AI_PRICE_CACHE_WRITE`, `UBYHOST_AI_PRICE_INPUT`, `UBYHOST_AI_PRICE_OUTPUT`, `UBYHOST_DOOR_CODES_LIVE`, `UBYHOST_TTLOCK_MONTHLY_CALLS`. The file's comment says "A new variable read in go/ must be added here"; a bare key passes the value through from `.env` only when it is set there. Without them the Go page would show the default cap, prices, call limit and "test mode". Side effect: the Go Havel chat (1430, `register_web_ai_havel.go` 28) reads the same cap and prices through `anthropic.ConfigFromEnv`, so on a server that sets them its budget now matches Python's.

**Differences from Python, on purpose or unreachable in practice** (the reviewer checks each):

1. `ORDER BY username`: production PostgreSQL sorts `user_account.username` (COLLATE "C") by bytes; Python on SQLite sorts NOCASE (`App/app/db.py` 97). Go sorts as production does. The golden seed uses lower-case names so both agree.
2. Controller contacts in the draft: `ORDER BY id` added (Python has no ORDER BY; it returns id order in practice).
3. `affected_owner_ids` holding a JSON object: Go gives no owners; Python iterates the object's keys. The app only writes lists.
4. An `UBYHOST_*` number that does not read as an integer: Go uses the default; Python stops at import. An AI variable set to an empty string counts as unset in Go.
5. `parse_time` reads the shapes the app writes (offset with colon, `Z`, none, date only, space or `T`, fractions); rarer ISO forms Python 3.12 also accepts (offset without colon, comma fraction, basic format) show "Never" in Go.
6. `casefold` is `golang.org/x/text/cases.Fold` (full case folding, as Python); characters newer than one of the two Unicode tables may fold differently (grouping only, never what is shown).
7. The texts the handler builds use `hostweb.Lang` (first `?lang=` value), the layout the last; differs only with two `lang` values in one URL.
8. A wrong method answers Go's plain-text 405 (Python JSON), as everywhere in the Go port.

**Verified by the brief writer** (fresh throwaway worktree of 859d114d5 with exactly the step 1 and step 2 actions, PostgreSQL 16 on a disposable port): 12 sha256 `OK`; `edit_shared.py` printed its three lines (count 18 -> 19); `gofmt -l` empty, `go build ./...`, `go vet ./internal/web/auth/... ./internal/web/ai/ ./cmd/...` silent, `go mod tidy -diff` empty; `go test ./internal/web/auth/... ./internal/web/ai/ ./internal/hostweb/... ./cmd/ubyhost-web/ -count=1 -v`: six `ok`, 0 `--- SKIP`; pytest of the four Python files of §6: 21 passed; `scripts/context_lint.py` OK; the golden script gave the same file on every run (`--check` passes). Mutations caught by the tests: job slack 14 instead of 15, feed stale after 4 h instead of 3, TTLock warning at 90 % instead of 80 %, gap groups sorted oldest first, lower-case instead of casefold, negative ages not clamped, capitalize without lower-casing the rest, stuck mail by `created_at` instead of `updated_at`.

Anchors (step 0, each `grep -cF '<anchor>' <file>` prints 1):

| File | Anchor |
|---|---|
| `go/internal/web/auth/auth.go` | `func Routes(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) []Route {` |
| `go/internal/web/auth/admin.go` | `func (d deps) admin(w http.ResponseWriter, r *http.Request) (*session.Host, bool) {` |
| `go/internal/web/auth/auth_test.go` | `t.Errorf("%d routes, want ` |
| `go/internal/web/ai/havel_data.go` | `var havelGuideAnchors = [][2]string{` |
| `go/internal/anthropic/ai.go` | `func (s *Service) MonthSpendUSD(ctx context.Context, feature string, day time.Time) (float64, error) {` |
| `go/internal/ubyport/outcome.go` | `const SubmissionMaxAutoAttempts = 1` |
| `App/app/routes/admin_accounts.py` | `    return render(request, "admin_operations.html", {` |
| `deploy/lightsail/docker-compose.yml` | `  ubyhost-go:` |

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/auth/opspage/data.go` | create (copy) | every read of the page |
| `go/internal/web/auth/opspage/page.go` | create (copy) | `Serve`, the view, catalog and templates |
| `go/internal/web/auth/opspage/templates/admin_operations.tmpl` | create (copy) | Go twin of `admin_operations.html` |
| `go/internal/web/auth/opspage/i18n_keys.txt` | create (copy) | the keys the page reads |
| `go/internal/web/auth/opspage/i18n.json` | create (copy, generated) | catalog from `host_i18n.py` |
| `go/internal/web/auth/opspage/page_test.go` | create (copy) | page vs Python golden, gate, drafts, helpers, owner ids |
| `go/internal/web/auth/opspage/testdata/admin_operations_golden.json` | create (copy, generated) | golden |
| `go/internal/web/auth/operations.go` | create (copy) | the admin gate and the handler |
| `go/internal/web/auth/operations_test.go` | create (copy) | route listed, signed-out redirect |
| `go/internal/web/ai/havel_ops.go` | create (copy) | Havel block of the page |
| `App/scripts/admin_operations_golden.py` | create (copy) | writes the golden from the real Python page (go-first exception 1) |
| `App/tests/test_go_admin_operations_golden.py` | create (copy) | the golden is fresh (go-first exception 1) |
| `go/internal/web/auth/auth.go` | edit (script) | one row at the end of `Routes` |
| `go/internal/web/auth/auth_test.go` | edit (script) | route count +1 |
| `deploy/lightsail/docker-compose.yml` | edit (script) | seven bare keys in `ubyhost-go` |
| `docs/tasks/1508-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1508-report.md` | create | the report |

No other file may change.

## 4. Steps

0. Checks (repo root, one call). Anything else than stated: STOP (§8). No commit.

   ```bash
   git status --short | grep -v '^?? docs/tasks/' | tail -5; git log --oneline --grep='^1501 step' | wc -l | tail -1
   ls go/internal/web/auth/opspage go/internal/web/auth/operations.go go/internal/web/ai/havel_ops.go App/scripts/admin_operations_golden.py 2>&1 | grep -c 'No such file'
   find docs/tasks/1508-files -name '*.txt' | wc -l | tail -1
   ```

   Expected: no `git status` line, a number of at least 1 (the branch is go-wave3 with 1501 in it), `4`, `12`. Then the eight anchors of §2 (one call, eight `grep -cF` joined with `;`): eight `1`.

1. Copy the sidecars and check them (repo root, one call). Never retype or edit them:

   ```bash
   cd docs/tasks/1508-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -13
   ba49d7cc92f20abf5cb3923a21641bbefd51ce73dd0f3f2c6cf303350ab68bcd  App/scripts/admin_operations_golden.py
   534bb46cd5608801b6aacbc60c84b3f335f97d12fa8f9746e1d334aa57ad76b6  App/tests/test_go_admin_operations_golden.py
   8104428bd8175daf525f01a3fb1ea53a41f8d3d964c6af732b7c44a71d97d46e  go/internal/web/ai/havel_ops.go
   3ada0503a650219d8e68e8074bec01ebc333e0f8e4d93107b9fccdd225c4f07b  go/internal/web/auth/operations.go
   ff4045c5092487f422c49e4c6071c2f3f36456612b56293e0b5978012fb03bee  go/internal/web/auth/operations_test.go
   78a07a93deeb608654f74763b4e31093fee483bf41925665224b95e46cc5e14a  go/internal/web/auth/opspage/data.go
   efe8d702f5d74ab8a5592dab800adedf6947b38f84f0a3da79413552126d23e5  go/internal/web/auth/opspage/page.go
   f58cb8084e43adc6215eaeb4313b31ca6839d58178131326acdf3b45a0e0a552  go/internal/web/auth/opspage/page_test.go
   14f1bcb2e18b2fcd2acdcac1ab37dfc648346a45309106e3bea1059e2b0da80b  go/internal/web/auth/opspage/templates/admin_operations.tmpl
   4b142f7d254e2c705b800fbc68b4d03ded168aeee0619d6a1726ea7162d56281  go/internal/web/auth/opspage/i18n_keys.txt
   316b03a8e5f1e99ffcb6405603c3665f08727cf2492a76382e992f4a99fae7be  go/internal/web/auth/opspage/i18n.json
   f2c937c84ab9c99c077d9cb7a4a4a2730219137e4d15697e4d41b420d80c0328  go/internal/web/auth/opspage/testdata/admin_operations_golden.json
   EOF
   ```

   Every line ends with `: OK`. Commit `1508 step 1` with the twelve copied files, `docs/tasks/1508-files/` and this brief (`git add` them by path; never `git add -A`, sibling briefs may have untracked files in `docs/tasks/`).

2. The shared edits, then format, build and vet (repo root, one call):

   ```bash
   python3 docs/tasks/1508-files/edit_shared.py 2>&1 | tail -5; grep -c 'd.operationsAdmin' go/internal/web/auth/auth.go; cd go && gofmt -l internal/web/auth internal/web/ai 2>&1 | tail -5; go build ./... 2>&1 | tail -10; go vet ./internal/web/auth/... ./internal/web/ai/ ./cmd/... 2>&1 | tail -10; go mod tidy -diff 2>&1 | grep -v downloading | tail -5
   ```

   Expected: three lines `auth.go: route added`, `auth_test.go: route count N -> N+1` (N is 18 if no sibling brief ran before, more if one did), `docker-compose.yml: 7 keys added to ubyhost-go`; then `1`; then nothing else. An `AssertionError`: STOP (§8). Commit `1508 step 2` (the three edited files, by path).

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1508 && chown postgres /var/tmp/pg1508 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1508/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1508/data -o "-p 55608 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1508" -l /var/tmp/pg1508/log -w start' 2>&1 | tail -3
   ```

   Expected: `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55608/postgres` below. No PostgreSQL 16 at that path: STOP (§8); the tests must not be skipped.

4. Go tests on PostgreSQL (from `go/`, one call):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55608/postgres go test ./internal/web/auth/... ./internal/web/ai/ ./internal/hostweb/... ./cmd/ubyhost-web/ -count=1 -v 2>&1 | grep -E '^(--- (SKIP|FAIL)|ok|FAIL|panic)' | tail -20; UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55608/postgres go test ./internal/web/auth/ ./internal/web/auth/opspage/ -count=1 -v -run '^(TestOperationsRoute|TestRoutesBuildWithoutPool|TestVisibleLines|TestPageMatchesPython|TestPageNeedsAdmin|TestDraftsMatchPython|TestHelpersMatchPython|TestOwnerIDs|TestCatalogHasPageKeys)$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -15
   ```

   Expected: six `ok` lines and no `--- SKIP`, `--- FAIL` or `panic` line; then nine `--- PASS` lines and two `ok`. Report the SKIP count (0).

5. Python checks (from `App/`, one call). If `App/.venv/bin/python` is missing, first `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3; cd ..`.

   ```bash
   cd App && .venv/bin/python -m pytest tests/test_go_admin_operations_golden.py tests/test_go_host_i18n.py tests/test_go_auth_routes.py tests/test_wp32_container_sizing.py tests/test_pg_app_role_script.py tests/test_pg_backup_scripts.py tests/test_pg_cutover_script.py -q --tb=short -rs 2>&1 | tail -8
   ```

   Expected: all passed, no `SKIPPED` line. `test_go_admin_operations_golden` or `test_go_host_i18n` failing means Python changed since the golden was written: STOP (§8), do not regenerate.

6. Stop and delete the throwaway server (skip if you used one you did not start):

   ```bash
   su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1508/data -m fast stop' 2>&1 | tail -2; rm -rf /var/tmp/pg1508
   ```

   Expected: `server stopped`.

7. Run §6's last command, write the report (§9), set `Status: review`, commit `1508 report`. Do not push.

## 5. Do not touch

`go/internal/hostweb/` (layout and catalogs are read-only), `go/internal/session/`, `go/internal/jobs/`, `go/internal/anthropic/`, every existing file of `go/internal/web/ai/` and `go/internal/web/auth/` except the two lines `edit_shared.py` changes (`auth.go` `Routes`, `auth_test.go` count), `go/internal/web/auth/i18n.json` and `i18n_keys.txt`, `go/cmd/ubyhost-web/` (the route registers through the existing `register_web_auth.go` loop), `go/go.mod`, `go/go.sum`, `App/app/`, `App/tests/conftest.py`, every other part of `deploy/` (Caddy, `.env` examples, `UBYHOST_GO_PATHS` defaults), `docs/context/*`, `docs/tasks/1508-files/`. Never print a secret, address or token. Rules 2, 3, 4, 5, 11 as in §2.

## 6. Commands

Exactly the commands of §4 (steps 0 to 6). Never the full suite, never `go test ./...` or `pytest tests`. Last, from the repo root: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding naming 1508).

Test-map: no row covers these Go packages; the Go commands of step 4 are this brief's tests. The Python files of step 5 are the parity test, the catalog freshness test, the auth catalog test and the compose-file tests (the compose file changed).

## 7. Acceptance

- [ ] Step 1 printed 12 `: OK`.
- [ ] Step 2 printed the three script lines and `1`, nothing else.
- [ ] Step 4: six `ok`, nine named `--- PASS`, 0 `--- SKIP`.
- [ ] Step 5: all passed, 0 skipped.
- [ ] `for c in $(git log --format=%h --grep='^1508 '); do git show --name-only --format= $c; done | sort -u` lists only §3 paths and this brief file (its Status line).
- [ ] `git show $(git log --format=%h --grep='^1508 step 2') -- deploy/ | grep '^[-+] ' | grep -v '^+      UBYHOST_[A-Z_]*:$'` prints nothing (only bare keys added), and no `UBYHOST_GO_PATHS` change anywhere; nothing pushed.
- [ ] UI (rules 7 and 10): the page is dormant (no path routes to it) and the Python browser and geometry tests cannot load a Go-rendered page, so no 390 px screenshot can be taken in this PR; the visible lines equal Python's (step 4). The UX gate runs on staging before the owner switches the path (Owner steps); the report says so.

## 8. Stop and ask

Stop, and write the report, if:

- a check, anchor, hash or file count of steps 0 to 1 is not as stated, or `edit_shared.py` raises;
- a test fails twice (never change a sidecar: report);
- PostgreSQL 16 cannot be started (the database tests must run, not skip);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1508-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (the §7 file list).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the full diff of:

- `go/internal/web/auth/opspage/data.go`: each SQL against the `admin_ops.py` line it ports (§2 table); the 30-minute, 3-hour and month cutoffs (`isoSeconds`, UTC); `ownerIDs`; `Draft` byte for byte; nothing selects a guest column, a feed URL or a recipient.
- `go/internal/web/auth/opspage/page.go`: `buildView` (the `age` thresholds 120 and 2880, the TTLock 80 % test, the alert-kind label only when translated, `None` for a missing review detail), `Serve` (Page: nav `operations`, body `detail`, v2, admin workspace).
- `go/internal/web/auth/opspage/templates/admin_operations.tmpl`: both incident forms post to `/admin/incidents` and `/admin/incidents/{id}` with `_csrf`; the timestamp buttons are `disabled` once set.
- `go/internal/web/auth/operations.go`: the handler starts with `d.admin`.
- `go/internal/web/ai/havel_ops.go`: grouping and the stable sorts (Python's `sorted(..., reverse=True)` and `Counter.most_common` keep first-seen order on ties).
- `deploy/lightsail/docker-compose.yml`: seven bare keys only, in `ubyhost-go`.
- Known differences 1 to 8 of §2.

## Owner steps

Do these only after the big PR with this brief is merged and deployed. Staging first (the UX gate, brief 1412 is the pattern), production after the gate passed. The `.env` file is in `/opt/ubyhost/deploy/lightsail/` (see `docs/LIGHTSAIL.md`).

1. Nothing to set for the new compose keys: they pass through what `.env` already holds for Python (`UBYHOST_AI_MONTHLY_USD_HAVEL`, the `UBYHOST_AI_PRICE_*` values, `UBYHOST_DOOR_CODES_LIVE`, `UBYHOST_TTLOCK_MONTHLY_CALLS`). After the deploy, run `docker compose up -d ubyhost-go` once so the Go container gets them.
2. Connect to the server: `ssh ubuntu@<server address>` (staging first), then `cd /opt/ubyhost/deploy/lightsail`. Write down the current switch line: `grep -n '^UBYHOST_GO_PATHS' .env`.
3. `nano .env`: inside the double quotes of `UBYHOST_GO_PATHS=` add a space and `/admin/operations`. Save with Ctrl+O, Enter, Ctrl+X.
4. `./scripts/caddy-validate.sh` (must end without an error), then `docker compose up -d caddy`. Open `/admin/operations` signed in as the operator and check that it loads.
5. On staging only: the UX gate of rule 10 for `/admin/operations` (`test_layout_lint_browser.py` green, 390, 768 and 1280 px screenshots, the design-system checklist); send the screenshots to the orchestrator. Do step 3 on production only after the gate passed.
6. To go back: put the line from step 2 back with `nano .env`, run `./scripts/caddy-validate.sh` and `docker compose up -d caddy`.
