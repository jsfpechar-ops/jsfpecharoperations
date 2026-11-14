# 1598: Go onboarding: verify and switch the POST /onboarding/* routes (brief 1290)

Status: review
Tier: B (switch-verify: no new Go code; re-runs existing tests; owner switches paths)
Depends on: 1596 (and through it 1595; all three must be on the branch) | Base commit: current tip of the working branch | Branch: task/1598-go-onboarding-switch-post-routes
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 30k tokens

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1598 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1598 step'`.

## 1. Objective

Brief 1290 ported four POST routes from `App/app/routes/onboarding.py` to `go/internal/web/onboarding` and left them dormant, with the note "the steps to switch them on come with brief 1291". Brief 1291 was repurposed. This brief is the deferred switch brief for those four routes:

- `POST /onboarding/dismiss` → adds the Go handler `onboarding.dismissed`
- `POST /onboarding/resume` → adds the Go handler `onboarding.resumed`
- `POST /welcome-back/dismiss` → Go handler `welcome_back.dismissed`
- `POST /celebrations/dismiss` → Go handler `celebration.dismissed`

The executor re-runs the full onboarding package tests (1290 + 1595 + 1596) on the current branch to confirm the Go code still matches Python after all three briefs have landed. No new Go file is created. The owner then adds the four paths to `UBYHOST_GO_PATHS` (Owner steps).

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (settings writes and audit rows, as brief 1290 verified); 2 privacy: no new personal-data field, no new retention line, no outbound request; 3 no new test fixture (uses the golden from brief 1290); 4 no new dependency; 5 no schema change; 6 not applicable (POST redirects); 11 Go first: this brief enables existing Go code; it changes no Python application file. No go-first exception is used here.

**Why this brief is needed.** Brief 1595 owner step 2 says: "Add `/onboarding` to the comma-separated list (exact path; do not add `/onboarding/*`, the 1290 POST routes have their own switch)." This brief is that switch. It runs after 1595 and 1596 have added their Go code to the same package, so a full re-run confirms the whole package is still green. Then the owner switches the four paths.

**No new code is pre-written.** There are no sidecars. The executor only runs existing tests.

**Parity notes:** the Go code for these four routes was written and golden-tested in brief 1290. No behaviour changed in briefs 1595 or 1596. The executor confirms the 1290 parity tests are still green on the latest branch.

**Paths that become fully served by Go (after owner switch):** `POST /onboarding/dismiss`, `POST /onboarding/resume`, `POST /welcome-back/dismiss`, `POST /celebrations/dismiss`. These four paths carry no path parameter, so they can be added individually to `UBYHOST_GO_PATHS` without ambiguity.

**Assumption:** `UBYHOST_GO_PATHS` does not currently include `/onboarding/*`, `/welcome-back/*` or `/celebrations/*` (brief 1595's owner step 2 adds only the exact path `/onboarding`, not `/*`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/tasks/1598-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `ls go/internal/web/onboarding/routes.go go/internal/web/onboarding/setup.go go/internal/web/onboarding/onboarding_page.go go/internal/web/onboarding/demo_reset.go 2>&1 | tail -4` lists all four (briefs 1290, 1595 and 1596 are done).
   - `ls go/cmd/ubyhost-web/register_web_onboarding.go go/cmd/ubyhost-web/register_web_onboarding_page.go go/cmd/ubyhost-web/register_web_onboarding_demo.go 2>&1 | tail -3` lists all three.
   - `grep -cF "POST /onboarding/dismiss" go/cmd/ubyhost-web/register_web_onboarding.go 2>&1 | tail -1` prints `1`.
   - `grep -cF "POST /demo/reset" go/cmd/ubyhost-web/register_web_onboarding_demo.go 2>&1 | tail -1` prints `1`.
   - `ls App/tests/test_go_onboarding_setup.py App/tests/test_go_onboarding_page_golden.py App/tests/test_go_demo_reset_golden.py 2>&1 | tail -3` lists all three (the parity tests from briefs 1290, 1595 and 1596).

1. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/onboarding cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -20; go vet ./internal/web/onboarding/... ./cmd/... 2>&1 | tail -20
   ```

   Expected: no output at all. Anything printed: STOP (§8). No commit (no file changed).

2. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if already running (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55598/data status' | tail -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55598 && chown postgres /var/tmp/pg55598 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55598/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55598/data -o "-p 55598 -k /var/tmp/pg55598" -l /var/tmp/pg55598/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55598/postgres` in steps 3 and 4. No PostgreSQL 16 binaries at that path: write "CI only" in the report and STOP before step 3.

3. Run the Go tests on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55598/postgres go test ./internal/web/onboarding/... ./internal/palette/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: `ok` lines for every package, no `FAIL`, no `SKIP` lines. Anything else: STOP (§8). Then count skips: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55598/postgres go test ./internal/web/onboarding/... ./internal/palette/... ./cmd/ubyhost-web/... -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` must print `0`.

4. Run the Python parity tests (one call, from `App/`). If `App/.venv` is missing, first run `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5`.

   ```bash
   cd App && .venv/bin/python -m pytest tests/test_go_onboarding_setup.py tests/test_go_onboarding_page_golden.py tests/test_go_demo_reset_golden.py -q --tb=short -x 2>&1 | tail -10
   ```

   Expected: `5 passed` (2 from `test_go_onboarding_setup.py`, 1 from `test_go_onboarding_page_golden.py`, 2 from `test_go_demo_reset_golden.py`), 0 skipped. Anything else: STOP (§8).

5. Run the context lint (repo root):

   ```bash
   python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5
   ```

   Expected: `context lint: OK`. Anything else: STOP (§8).

6. Write the report (§9), set `Status: review` in this file and commit "1598 step 6".

## 5. Do not touch

`App/app/` (Python still serves these four routes until the owner switches them), `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, any file added by briefs 1290, 1595, 1596 and 1599-1604 (all Go and Python files; the sidecar files in `docs/tasks/159[56]-files/` and `docs/tasks/160[0-2]-files/`). Hard rules of AGENTS.md: no secret or guest datum in a file or a log; nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 1, 3, 4 and 5). Never the full suite, never `go test ./...`.

## 7. Acceptance

- [ ] Step 0 checks all passed.
- [ ] Step 1: no output at all.
- [ ] Step 3: `ok` for every package, SKIP count `0`.
- [ ] Step 4: `5 passed`, 0 skipped.
- [ ] Step 5: `context lint: OK`.
- [ ] `git show --stat --format=%s $(git log --format=%h --grep='^1598 step') | tail -10` lists only `docs/tasks/1598-go-onboarding-switch-post-routes.md` and `docs/tasks/1598-report.md`.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or `App/app/` file changed; nothing was pushed to `main`.

## 8. Stop and ask

Stop, and write the report, if:

- a check in step 0 is not as stated (a file is missing or a grep count is wrong);
- a test fails twice;
- you reach 15 tool calls or about 30k tokens (write the report as `blocked`, see executor.md);
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1598-report.md` (400 tokens at most) and set this brief's `Status: review`. The report has:

1. The step commits (`git log --oneline --grep='^1598 step'`).
2. Each command with the last 5 lines of its output and the SKIP count.
3. §7 ticked.
4. Deviations.
5. Owner steps left.

## Risk list (for the reviewer)

No new code changes. Verify that step 3 passes with 0 skips (the 1290, 1595 and 1596 tests all green together) and that step 4 passes all 5 parity tests. The only risk is a regression in the shared package caused by overlapping code from the three briefs.

## Owner steps

After the UX gate for `GET /onboarding` (brief 1595, owner item 7) passes on staging, switch the four POST routes:

1. On the server, open the env file that holds `UBYHOST_GO_PATHS` (see `docs/ENVIRONMENT.md`).
2. Add these four paths to the space-separated list (each is an exact POST path with no wildcard):
   `/onboarding/dismiss /onboarding/resume /welcome-back/dismiss /celebrations/dismiss`
3. Run `scripts/caddy-validate.sh`, then `docker compose up -d caddy`.
4. Verify: in a signed-in host session, dismiss and resume the onboarding guide; the response must be a 303 redirect to `/?msg=...` or `/?err=...` as before. Check the audit log for `onboarding.dismissed` / `onboarding.resumed` rows.
5. Rollback: remove the four paths and repeat step 3.
