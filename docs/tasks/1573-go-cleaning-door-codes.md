# 1573: Go cleaning host pages, part 4: the door-code actions (manual, TTLock queue, remove)

Status: todo
Depends on: 1570, 1571, 1572 | Base commit: current tip of the working branch | Branch: task/1573-go-cleaning-door-codes
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1573 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1573 step'` and `git show --stat <commit>`, never a fixed base commit.

## 1. Objective

Add the last cleaning route, `POST /cleaning/properties/{id}/code/{action}` (manual code, queue a permanent TTLock code, remove the code), to `go/internal/web/cleaning`, ported from `cleaning_codes.py`. With it Go serves every method of every `/cleaning` path, so the whole prefix can move. Dormant until the owner routes the paths.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (cleaning pages only); 2 privacy: no new personal-data field, no new retention line, no outbound request; 3 fixtures are made up (`@example.test`, test-only keys); 4 no new dependency (stdlib, pgx and packages already in `go.mod`); 5 plain PostgreSQL through `pgxpool`, the Python SQL with `$n` placeholders, no schema change; 6 light mode, the forms work without JavaScript; 11 Go first (this brief is the Go port; no file under `App/app/` changes).

**PR text (hard rule 2):** no new outbound request: the TTLock action only writes a `pending` `cleaning_code` row and the Python worker (`process_queue`) still talks to the lock provider. No new personal-data field: the PIN is stored encrypted as before (`pin_enc`). The three writers take the same advisory lock key as Python (`hashtext('cleaning_property')`, apartment id).

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1573-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `1edecb4d8b23faaabeb628aab375ebe4bedac50082083ee4343adbf18f8238ba` | `go/cmd/ubyhost-web/register_web_cleaning_host_codes_test.go` | create | 39 |
| `7147639b78d91f9ae6db65d9fd3014a0df301d5b41508336ffabd6ab4fe10f47` | `go/internal/web/cleaning/host_codes.go` | create | 408 |
| `bf6aedee09700d06fcdeb083f9d3ea22fed0062e48bbdb5e20247a20b2865482` | `go/internal/web/cleaning/host_codes_test.go` | create | 334 |

**How the code is built.** `host_codes.go` is one handler with three actions, each a transaction under the same advisory lock key as Python. `activate` is `_activate` without its lock-provider branch: a manual code never takes that branch, and the TTLock activation stays in the Python worker. Errors come back as the key Python raises as `ValueError` and re-render the settings page of brief 1572 with status 422.

**Parity notes (Python `App/app/routes/cleaning.py` unless named):**

| Route | Python | Go |
|---|---|---|
| `POST /cleaning/properties/{id}/code/{action}` | `code_action` 297-315 | `(*hostServer).codeAction` |
| action `manual` | `cleaning_codes.save_manual` 119-147, `_activate` 67-116 | `saveManual`, `activate` |
| action `ttlock` | `cleaning_codes.queue_permanent` 150-183, `ttlock.allowed_for`, `billing.entitlements` | `queuePermanent`, `lockProviderAllowed`, `lockListed` |
| action `remove` | `cleaning_codes.remove` 323-343 | `removeCode` |

Details that are easy to get wrong and are tested: the checks run in Python's order (CSRF, login, the property must be the host's and active, then the action; an unknown action is `404` after the property check); errors re-render the settings page with status 422 and `ct(key)`: `login_required` (staging without login), `code` (PIN not 1 to 32 of `A-Za-z0-9*#-`, checked after strip), `pending` (a lock operation is running: `issuing` or `revoking`; the whole change is rolled back), `lock_setup` (door codes off, no authorized account, the property is not bound to a listed TTLock lock, or the plan does not allow it); a manual code makes the previous active code `revoked` (PIN wiped) or, for a TTLock code, `revoke_pending` (PIN kept for the worker), except that typing the same PIN (with or without the final `#`) takes the code over and marks the old one `detached` with its PIN wiped, so the lock is not touched; a pending TTLock code is sent to `revoke_pending` when a manual code replaces it; `ttlock` on a property with a pending code only retries a `failed` one; the TTLock plan rule is `billing.entitlements().ttlock`: always on when billing is off, no billing row or trial, otherwise the Max plan or the add-on, never when paused; every write takes `pg_advisory_xact_lock(hashtext('cleaning_property'), apartment_id)` like Python.

**Known differences from Python, shared by every Go web area (not fixed here):** a missing or foreign record answers `404 {"detail":"Not Found"}` (and a non-integer id `422`), where Python shows the branded error page to a browser; `HEAD` is served by the `GET` pattern; a repeated query key reads the last value in the code written here (as Starlette does) but the older `buildPayload` reads the first. Python's `int()` also accepts `1_0` and a leading `+`; Go's parser accepts the sign only.

**Paths that become fully served by Go:** `/cleaning/properties/*/code/*` (POST). After this brief every method of every path of `routes/cleaning.py` is served by Go: `/cleaning`, `/cleaning/new`, `/cleaning/schedule`, `/cleaning/events`, `/cleaning/events/*`, `/cleaning/events/*/edit`, `/cleaning/events/*/delete`, `/cleaning/properties`, `/cleaning/properties/*`, `/cleaning/properties/*/code/*`, `/cleaning/shares`, `/cleaning/shares/*/revoke`, `/cleaning/shared/*`, `/cleaning/shared/*/schedule` (`TestCleaningAllRoutesRegistered` pins the 16 routes). Nothing is routed by this brief.

**Anchors that must exist verbatim** (step 0): the Python function lines and the Go function lines listed there.

**Verified by the brief writer** (in a throwaway worktree of this branch, with the steps of briefs 1570 to 1573 applied exactly and in order, sidecars copied as step 1 does): `gofmt -l` printed nothing, `go build ./...` and `go vet ./internal/web/cleaning/... ./cmd/...` were silent, and `go test ./internal/web/cleaning/... ./cmd/ubyhost-web/... -count=1` passed on PostgreSQL 16, with the golden test of brief 1310 still green and the named tests PASS. The tests cover: manual code (stored encrypted, row created for a property without one, a second manual code revokes the first, typing the same PIN as an active TTLock code with or without `#` detaches it, another PIN queues it for revocation and keeps its PIN, a pending code goes to `revoke_pending`), manual refusals (six bad PINs, 32 characters accepted, a running lock operation blocks and writes nothing), remove (manual and TTLock codes, a pending one, a property without a row, a running operation rolls the whole change back), the TTLock queue (a pending code is not touched, a failed one is retried, a new `pending` code with the right account, lock, name, 7-digit encrypted PIN and `next_attempt_at`), the lock-setup refusals (door codes off, no client secret, no lock on the property, no or wrong lock list, account not ok, standard plan without add-on) and the passes (add-on, Max), a paused account (login gate redirect), staging without login, the access rules (unknown action, foreign, archived, missing, text id, signed out, no CSRF token), and the 16-route registration table.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_cleaning_host_codes_test.go` | create | route registration test |
| `go/internal/web/cleaning/host_codes.go` | create | door-code actions |
| `go/internal/web/cleaning/host_codes_test.go` | create | route tests |
| `docs/tasks/1573-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1573-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `git log --oneline --grep='^1570 step' | wc -l | tail -1` prints a number of 1 or more (brief 1570 is on this branch).
   - `git log --oneline --grep='^1571 step' | wc -l | tail -1` prints a number of 1 or more (brief 1571 is on this branch).
   - `git log --oneline --grep='^1572 step' | wc -l | tail -1` prints a number of 1 or more (brief 1572 is on this branch).
   - `grep -cF "async def code_action(request: Request, property_id: int, action: str):" App/app/routes/cleaning.py | tail -1` prints `1`.
   - `grep -cF "def save_manual(apartment_id: int, value: str) -> None:" App/app/cleaning_codes.py | tail -1` prints `1`.
   - `grep -cF "def queue_permanent(home: dict, owner_id: int | None) -> int:" App/app/cleaning_codes.py | tail -1` prints `1`.
   - `grep -cF "def remove(apartment_id: int) -> None:" App/app/cleaning_codes.py | tail -1` prints `1`.
   - `grep -cF "func (s *hostServer) renderSettings(" go/internal/web/cleaning/host_settings.go | tail -1` prints `1`.
   - `grep -cF "func ensureProperty(" go/internal/web/cleaning/host_settings.go | tail -1` prints `1`.
   - `grep -cF "func parseHostForm(" go/internal/web/cleaning/host_events.go | tail -1` prints `1`.
   - `ls go/internal/web/cleaning/host_codes.go 2>&1 | tail -1` says "No such file" (nothing of this brief exists yet).
   - `find docs/tasks/1573-files -name '*.txt' | wc -l | tail -1` prints `3`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1573-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -6
   1edecb4d8b23faaabeb628aab375ebe4bedac50082083ee4343adbf18f8238ba  go/cmd/ubyhost-web/register_web_cleaning_host_codes_test.go
   7147639b78d91f9ae6db65d9fd3014a0df301d5b41508336ffabd6ab4fe10f47  go/internal/web/cleaning/host_codes.go
   bf6aedee09700d06fcdeb083f9d3ea22fed0062e48bbdb5e20247a20b2865482  go/internal/web/cleaning/host_codes_test.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1573 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/cleaning cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/cleaning/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all (gofmt lists nothing, build and vet are silent). Anything printed: STOP (§8). Nothing changed, so no commit.

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if an earlier brief of this series left it running (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55570/data status' | tail -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55570 && chown postgres /var/tmp/pg55570 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55570/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55570/data -o "-p 55570 -k /var/tmp/pg55570" -l /var/tmp/pg55570/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55570/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55570/postgres go test ./internal/web/cleaning/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: two lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/cleaning	<seconds>s` and `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	<seconds>s`. The golden test of brief 1310 (`TestCleaningMatchesPython`) is part of the first package and must stay green. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55570/postgres go test ./internal/web/cleaning/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestHostManualCode$|^TestHostManualCodeErrors$|^TestHostRemoveCode$|^TestHostRemoveCodeBusy$|^TestHostQueuePermanentCode$|^TestHostQueuePermanentCodeRefused$|^TestHostCodeActionAccess$|^TestHostCodesStagingNoLogin$|^TestCleaningAllRoutesRegistered$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of 9 tests (times differ) and two final `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestHostManualCode (0.NNs)
   --- PASS: TestHostManualCodeErrors (0.NNs)
   --- PASS: TestHostRemoveCode (0.NNs)
   --- PASS: TestHostRemoveCodeBusy (0.NNs)
   --- PASS: TestHostQueuePermanentCode (0.NNs)
   --- PASS: TestHostQueuePermanentCodeRefused (0.NNs)
   --- PASS: TestHostCodeActionAccess (0.NNs)
   --- PASS: TestHostCodesStagingNoLogin (0.NNs)
   --- PASS: TestCleaningAllRoutesRegistered (0.NNs)

5. Write the report (§9), set `Status: review` in this file and commit "1573 step 5". Do not open a PR (one big PR mode); the owner or the orchestrator opens it with the PR text of §2.

## 5. Do not touch

`App/` (no Python file changes; the Python routes stay the live ones), `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, every file of briefs 1570 to 1572 and the existing files of the package. Hard rules of AGENTS.md: no secret or guest datum in a file or a log (the test data is made up), nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 2 and 4). No test-map row exists yet for `go/internal/web/cleaning` host pages; the coordinator adds one from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 3 files.
- [ ] The format, build and vet step printed nothing.
- [ ] The test step printed `ok` for both packages, and each of the 9 named tests printed `--- PASS` (none `SKIP`, none `FAIL`) on PostgreSQL.
- [ ] `git log --oneline --grep='^1573 step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1573 step') | tail -40` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed to `main`.
- [ ] UI: not applicable in this PR (rules 7 and 10): the pages are dormant (no path routes to them) and the Python-side browser tests cannot reach the Go service. The UX gate of rule 10 (`test_layout_lint_browser.py`, the 390, 768 and 1280 px screenshots of each page, a line per page in the PR) runs on staging before the owner adds the paths; see Owner steps.

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

Write `docs/tasks/1573-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git diff --stat` as in §7).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of: `host_codes.go`: `saveManual` and `activate` (the previous code is revoked or detached, never left active next to the new one), `removeCode` (both codes handled in one transaction), `queuePermanent` and `lockProviderAllowed` (the plan rule; nothing calls the provider), `lockProperty` (same advisory key as Python), `codeAction` (property check before the action, unknown action is 404).

## Owner steps

Nothing is switched on by this series. When all of 1570 to 1573 are merged and green, and only then:

1. Open the staging site, sign in as a host with two properties, and walk through `/cleaning`: add a cleaning from the calendar and from `+ Add`, edit it, remove it, open the cleaner share page, create and revoke a share, open the property settings, save instructions, save a manual door code and remove it. Run `test_layout_lint_browser.py` and open the 390, 768 and 1280 px screenshots of the five host pages; write one line per page in the PR (rule 10). Never leave a finding open.
2. If everything holds, add these paths to `UBYHOST_GO_PATHS` in the server's `.env` (see `docs/ENVIRONMENT.md`, keep the value in double quotes and never empty): `/cleaning /cleaning/new /cleaning/schedule /cleaning/events /cleaning/events/* /cleaning/events/*/edit /cleaning/events/*/delete /cleaning/properties /cleaning/properties/* /cleaning/properties/*/code/* /cleaning/shares /cleaning/shares/* /cleaning/shares/*/revoke /cleaning/shared/* /cleaning/shared/*/schedule`.
3. Validate and reload Caddy: `deploy/lightsail/scripts/caddy-validate.sh`, then `docker compose up -d caddy`. Rollback: remove the paths again and repeat this step.
4. Open one cleaner share link (a revoked one answers JSON until a Go error page exists, see brief 1310 difference 1), add and remove one test cleaning, then watch `/metrics` for the `/cleaning` routes for a day.
