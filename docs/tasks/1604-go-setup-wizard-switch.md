# 1604: Go setup wizard, part 6: verify and switch the wizard routes (without 1603)

Status: todo
Tier: B (switch-verify: no new Go code; re-runs existing tests; owner switches paths)
Depends on: 1602 (and through it 1601, 1600 and 1599; all four must be on the branch) | Does NOT depend on 1603 | Base commit: current tip of the working branch | Branch: task/1604-go-setup-wizard-switch
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 30k tokens

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1604 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1604 step'`.

## 1. Objective

Brief 1602 owner steps say: "The wizard runs on Python until you switch it. Wait for brief 1603 first (blocked: without it, 'Delete and continue' on the try-it page answers 501)." Brief 1603 is blocked indefinitely (it requires a writable data volume for the Go web service). This brief provides the alternative path: switch the wizard routes to Go without waiting for 1603, with the owner accepting that the try-it step's "Delete and continue" button answers 501 until brief 1603 is later unblocked.

The executor re-runs all wizard golden tests (briefs 1599, 1600, 1601 and 1602) on the current branch to confirm the Go code is still correct. No new Go file is created. The owner then adds the two wizard paths to `UBYHOST_GO_PATHS` (Owner steps).

After this brief merges, the wizard runs on Go with one known limitation: a host on the try-it step who has already registered a demo guest sees a "Delete and continue" button that returns 501 and writes nothing, instead of deleting the demo stay. The owner must tell affected hosts (if any) to skip to the finish page manually, or wait for brief 1603 to unblock.

## 2. Context

Rules (AGENTS.md): 1 filing correctness: the wizard never files or submits to UbyPort directly; the police step's Wait button saves `automation_mode` and `submit_after_hours` exactly as Python (brief 1602 golden). The 501 on try_it skip does not affect any real stay; it only affects the demo stay created by `POST /setup` with `step=try_it&action=demo`. 2 privacy: no new personal-data field, no new retention line, no outbound request. 3 no new test fixture (uses golden files from briefs 1599-1602). 4 no new dependency. 5 no schema change. 6 not applicable (this brief touches no template). 11 Go first: this brief enables existing Go code.

**No new code is pre-written.** There are no sidecars. The executor only runs existing tests.

**The 501 limitation.** After this brief's owner switch:
- The six wizard step pages render correctly in Go: calendar, guest link, police, property, finish and try-it.
- `POST /setup` handles all actions (hide, show, skip, wait, done, demo, keep) except one: `step=try_it&action=skip` while the property has a demo stay answers 501 and writes nothing (brief 1603, blocked). Python's route still serves `/apartments/*/setup` and `/apartments/*/setup/*` before the owner switch; Go serves them after.
- The owner must decide to accept the 501 before running the owner switch steps.

**When brief 1603 is later unblocked and merged:** `POST /setup` will serve the skip-with-demo branch; the 501 disappears automatically. Brief 1603's owner steps (which currently say "keep the wizard out of `UBYHOST_GO_PATHS`") become moot once this brief has already switched the wizard.

**Paths that become fully served by Go (after owner switch):** `/apartments/*/setup` (GET entry and POST action) and `/apartments/*/setup/*` (GET step pages). These are the same two Caddy path matchers as brief 1602's owner step 2.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/tasks/1604-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `ls go/internal/web/onboarding/wizard.go go/internal/web/onboarding/wizard_pages.go go/internal/web/onboarding/wizard_finish.go go/internal/web/onboarding/wizard_post.go 2>&1 | tail -4` lists all four (briefs 1599, 1600, 1601 and 1602 are done).
   - `ls go/cmd/ubyhost-web/register_web_onboarding_wizard.go 2>&1 | tail -1` lists the file.
   - `ls App/tests/test_go_onboarding_wizard.py App/tests/test_go_onboarding_wizard_pages.py App/tests/test_go_onboarding_wizard_finish.py App/tests/test_go_onboarding_wizard_post.py 2>&1 | tail -4` lists all four parity test files.
   - `grep -cF "TestWizardSkipWithDemoStayIs501" go/internal/web/onboarding/wizard_post_test.go 2>&1 | tail -1` prints `1` (confirms the 501 branch is tested and accounted for).
   - `ls go/internal/web/onboarding/wizard_post.go 2>&1 | tail -1` says `go/internal/web/onboarding/wizard_post.go` (brief 1602 is done; nothing of 1604 exists yet except this check passing trivially).

1. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/onboarding cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -20; go vet ./internal/web/onboarding/... ./cmd/... 2>&1 | tail -20
   ```

   Expected: no output at all. Anything printed: STOP (§8). No commit (no file changed).

2. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one; skip the start if an earlier brief of this series left it running (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55599/data status' | tail -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55599 && chown postgres /var/tmp/pg55599 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55599/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55599/data -o "-p 55599 -k /var/tmp/pg55599" -l /var/tmp/pg55599/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55599/postgres` in steps 3 and 4. No PostgreSQL 16 binaries at that path: write "CI only" in the report and STOP before step 3.

3. Run the Go tests on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55599/postgres go test ./internal/web/onboarding/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: `ok` lines for every package, no `FAIL`. Then count skips: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55599/postgres go test ./internal/web/onboarding/... ./cmd/ubyhost-web/... -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` must print `0`.

4. Run the Python wizard parity tests (one call, from `App/`). If `App/.venv` is missing, first run `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5`.

   ```bash
   cd App && .venv/bin/python -m pytest tests/test_go_onboarding_wizard.py tests/test_go_onboarding_wizard_pages.py tests/test_go_onboarding_wizard_finish.py tests/test_go_onboarding_wizard_post.py -q --tb=short -x 2>&1 | tail -10
   ```

   Expected: `4 passed` (1 from each file), 0 skipped. Anything else: STOP (§8).

5. Run the context lint (repo root):

   ```bash
   python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5
   ```

   Expected: `context lint: OK`. Anything else: STOP (§8).

6. Write the report (§9), set `Status: review` in this file and commit "1604 step 6".

## 5. Do not touch

`App/app/` (Python still serves the wizard routes until the owner switches them), `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, all files added by briefs 1595-1603 (Go and Python files; sidecar folders `docs/tasks/159[56]-files/`, `docs/tasks/160[0-2]-files/`). Hard rules of AGENTS.md: no secret or guest datum in a file or a log; nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 1, 3, 4 and 5). Never the full suite, never `go test ./...`.

## 7. Acceptance

- [ ] Step 0 checks all passed.
- [ ] Step 1: no output at all.
- [ ] Step 3: `ok` for every package, SKIP count `0`.
- [ ] Step 4: `4 passed`, 0 skipped.
- [ ] Step 5: `context lint: OK`.
- [ ] `git show --stat --format=%s $(git log --format=%h --grep='^1604 step') | tail -10` lists only `docs/tasks/1604-go-setup-wizard-switch.md` and `docs/tasks/1604-report.md`.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or `App/app/` file changed; nothing was pushed to `main`.
- [ ] UI: the UX gate of rule 10 is pending for the wizard pages (see Owner steps).

## 8. Stop and ask

Stop, and write the report, if:

- a check in step 0 is not as stated;
- a test fails twice;
- you reach 15 tool calls or about 30k tokens (write the report as `blocked`, see executor.md);
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1604-report.md` (400 tokens at most) and set this brief's `Status: review`. The report has:

1. The step commits (`git log --oneline --grep='^1604 step'`).
2. Each command with the last 5 lines of its output and the SKIP count.
3. §7 ticked.
4. Deviations.
5. Owner steps left.

## Risk list (for the reviewer)

No new code changes. Verify that step 3 passes with 0 skips (the 1599-1602 tests all green together) and that step 4 passes all 4 parity tests. The key risk is the 501 on `step=try_it&action=skip` with a demo stay: `TestWizardSkipWithDemoStayIs501` must be one of the passing Go tests, confirming the 501 branch writes nothing.

## Owner steps

**Before switching:** decide that the 501 on "Delete and continue" (try-it step, demo stay present) is acceptable. On a production host database, demo stays are rare (only appear after a host completes the try-it step with a demo guest registered). If a demo stay exists for any host, brief 1603 (blocked) must be done first, or that host must manually navigate to the finish page.

**UX gate (rule 10, required before switching production):**
1. Deploy the PR to staging.
2. Add `/apartments/*/setup /apartments/*/setup/*` to `UBYHOST_GO_PATHS` in the staging `.env`, then run `deploy.sh`.
3. Ask the orchestrator to run `test_layout_lint_browser.py` and capture 390, 768 and 1280 px screenshots of the six wizard pages (calendar, guest link, police, property, finish, try-it). Write a line per page in the PR about what was seen. Confirm rule 10 is satisfied.
4. Walk through a property's wizard on staging: every step, hide and resume, run the try-it demo (create the demo stay). Verify the pages look like the Python pages.

**Production switch:**
1. On the server, open the env file that holds `UBYHOST_GO_PATHS` (see `docs/ENVIRONMENT.md`).
2. Add `/apartments/*/setup /apartments/*/setup/*` to the space-separated list (double-quoted, same as the other entries). The `*` is a Caddy path wildcard.
3. Run `scripts/caddy-validate.sh`, then `docker compose up -d caddy`.
4. Open a property's wizard; every page must render as before.
5. Rollback: remove the two paths and repeat step 3.
