# 1702: Go property settings 3: door-code switch (POST /apartments/{id}/door-codes)

Status: todo — ready (exact-diff pass 2026-11-17; Opus wrote, compiled and tested every sidecar on PostgreSQL 16)
Depends on: 1701, 1701b (both done) | Base commit: current tip of the working branch | Branch: task/1702-go-apartment-update-door-codes
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (this brief needs about 10)
Tier: A (exact files only; fresh review of the full diff before merge, see the risk list at the end)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1702 step k` (`k` is the step number) and `git add` only the paths the step names (never `-A`, never `.`). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1702 step'`, never a fixed base commit.

## 1. Objective

Port `apartment_door_codes` (`App/app/routes/admin.py` 2500-2532: the Turn on / Turn off buttons of the Door lock section, form `action="/apartments/{id}/door-codes"` with the hidden `mode` input that 1701 already renders) to Go, exactly as Python behaves today. The route stays dormant: nothing is added to `UBYHOST_GO_PATHS` (brief 1705).

**Split (exact-diff pass, 2026-11-17).** The scoped brief also held `apartment_update` (POST /apartments/{id}: `_save_apartment_form` 2791-3046 with the hour rules, operator check, wizard steps, `_refuse_apartment_save` re-render of the whole page, the signature save, the police-letter connection test). That is several times the session cap, so it moved to [1702b](1702b-go-apartment-update.md) (scoped), together with the fee-field error lines on a POST re-render that 1701b §8 (b) left to "1702". Nothing of that is in this brief.

## 2. Context

Rules (AGENTS.md): 1 filing correctness: this route writes only `lock_provider`/`lock_id` (door codes), no police field; 2 privacy: no new personal-data field, no retention line, no outbound request (the lock list is the stored `lock_account.locks_json`, as Python's `ttlock.locks_of`); 3 fixtures are made up (the 1701 test world, `@example.test`); 4 no new dependency; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, no schema change; 6 no new markup (the form and its `_csrf` are 1701's); 11 Go first, tests Go only with hand-written expected strings (no Python golden script: owner rule "golden only for filing data", and this route writes none).

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1702-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. All six files are new.

| sha256 | file | action | lines |
|---|---|---|---|
| `ebc226a7b793c29c8e7c8e2f6746bd0800ba819bddb7d5ad4066b52455be909a` | `go/internal/web/properties/apartment_door_codes.go` | create | 130 |
| `1101cb9ecf395e53a70843a20c39c25c23f2a710d0f8fac815cbcd583b46c6d6` | `go/internal/web/properties/apartment_door_codes_test.go` | create | 175 |
| `b47129dde56a0ed38c424248cca24ef2b35ff0e3013052c9d41e703e71c4c8ee` | `go/internal/web/properties/apartmentdoorcodes/i18n_keys.txt` | create | 6 |
| `cfd49e0bca4eea6852a3a67f60c50022b8b356b524339be1b41f7f52c805c7f3` | `go/internal/web/properties/apartmentdoorcodes/i18n.json` | create | 20 |
| `ae80280fe062c848d86457b26b1e428aa92ddb90e5be00a86d4bad72ccd3c144` | `go/cmd/ubyhost-web/register_web_properties_apartment_door_codes.go` | create | 25 |
| `0795b2087fe1f185a359928f71414885d9f05b73e80ff50c74cf0d39e08d3ffe` | `go/cmd/ubyhost-web/register_web_properties_apartment_door_codes_test.go` | create | 25 |

**How the code is built (for the reviewer; the executor reads no Go file, it only copies and runs).**

- Reuse, nothing copied: the gate is the package's `server.enter` (CSRF, path id, login, form, in FastAPI's order); the property is `Pages.detailLoad(ctx, workspace, id)` (`access.apartment`: `owner_user_id IS NOT DISTINCT FROM` the workspace); `ttlock.allowed_for` is `Pages.detailLockAllowed`; `_door_code_context` is `Pages.detailDoorContext` (its `Locks` and `DefaultLockID`); `_properties_using_lock` is `Pages.detailLockUsers`; `form_str` is `formStr` (last value, stripped); `db.audit` is `server.audit`; `_back` is `request.back` (Starlette quoting). The page and the switch therefore read the same lock list and the same "in use by" rule.
- `apartment_door_codes.go`: `RegisterApartmentDoorCodes` mounts `POST /apartments/{id}/door-codes`; the handler follows Python line by line: not found or not allowed: back to `/apartments` with `flash.error.smart_locks_unavailable`; `mode` `off`: `UPDATE apartment SET lock_provider = NULL WHERE id = $1` (keeps `lock_id`), audit `door_codes_off` / `apartment=<id>`; any other mode but `on`: back, nothing written; `on`: lock = stored `lock_id`, else the one free lock; refused with `flash.error.door_code_lock` (not in the account's list), `.door_code_lock_taken` (another property sends codes on it), `why.times_missing` (an hour missing); else `UPDATE apartment SET lock_provider = 'ttlock', lock_id = $1 WHERE id = $2`, audit `door_codes_on`. Every redirect goes to `/apartments/<id>?view=settings&section=lock#sec-lock`. Both `UPDATE`s use the id of the row `detailLoad` returned (already owner-scoped).
- `apartmentdoorcodes/i18n_keys.txt` / `i18n.json`: the four flash keys, written by `App/scripts/go_host_i18n.py` (the package's shared `i18n.json` is not touched).
- Tests: `TestApartmentDoorCodes` (off, neither, on, taken, unknown lock in English and Czech, missing hour with no write, the one-free-lock default, two free locks: no default, the audit rows with owner and actor); `TestApartmentDoorCodesAccess` (no `_csrf`: `/login?notice=form_expired`; signed out: `/login?next=...`; bad id: 422; another host's property, a missing one, door codes switched off, a plan without the TTLock add-on: all back to `/apartments` with the flash, no row and no audit written); `TestApartmentDoorCodesRouteRegistered` (the pattern, and the neighbouring routes keep theirs).

**Accepted differences:** none known. Python's `ctx is None` branch after `allowed_for` passed (a race) is kept as it is.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/apartment_door_codes.go` | create | the handler |
| `go/internal/web/properties/apartment_door_codes_test.go` | create | Go tests with hand-written expectations |
| `go/internal/web/properties/apartmentdoorcodes/i18n_keys.txt` | create | the four keys |
| `go/internal/web/properties/apartmentdoorcodes/i18n.json` | create | generated catalog |
| `go/cmd/ubyhost-web/register_web_properties_apartment_door_codes.go` | create | registers the route (`init()` through `registerRoutes`) |
| `go/cmd/ubyhost-web/register_web_properties_apartment_door_codes_test.go` | create | route registration test |
| `docs/tasks/1702-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1702-report.md` | create | the report (§9) |

No other file may change. No `App/` file.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `ls go/internal/web/properties/apartment_door_codes.go go/internal/web/properties/apartmentdoorcodes go/cmd/ubyhost-web/register_web_properties_apartment_door_codes.go 2>&1 | tail -3` says "No such file" three times.
   - `find docs/tasks/1702-files -name '*.txt' | wc -l | tail -1` prints `6`.
   - `grep -rl 'RegisterApartmentDoorCodes' go | wc -l | tail -1` prints `0` (the route is not registered yet).
   - Each of the following prints `1` (one call per line, `grep -cF '<text>' <file> | tail -1`):
     - `go/internal/web/properties/apartment_detail_data.go`: `func (s *Pages) detailLoad(ctx context.Context, owner, id int64) (*detailApt, error) {`, `func (s *Pages) detailLockAllowed(ctx context.Context, owner *int64) (bool, error) {`, `func (s *Pages) detailDoorContext(ctx context.Context, a *detailApt) (*detailDoor, error) {` and `func (s *Pages) detailLockUsers(ctx context.Context, owner int64, lockID string, except int64) (string, error) {`
     - `go/internal/web/properties/properties.go`: `func (s *server) enter(w http.ResponseWriter, r *http.Request) (*request, bool) {` and `func (s *server) audit(ctx context.Context, q *request, action, detail string) error {`
     - `go/internal/web/properties/localpath.go`: `func formStr(r *http.Request, key string) string {`
     - `go/internal/web/properties/apartment_detail_test.go`: `func adWorld(t *testing.T, pool *pgxpool.Pool) {` and `func adLockWorld(t *testing.T, pool *pgxpool.Pool) map[string]string {`
     - `go/internal/web/properties/apartment_new_test.go`: `const apartmentNewSecret = "apartment-new-test-secret-key-0123456789"`
     - `go/internal/web/properties/apartmentdetail/apartment_detail.tmpl`: `<form method="post" action="/apartments/{{$a.ID}}/door-codes" class="lock-state-form">`

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1702-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF2' 2>&1 | tail -10
   ebc226a7b793c29c8e7c8e2f6746bd0800ba819bddb7d5ad4066b52455be909a  go/internal/web/properties/apartment_door_codes.go
   1101cb9ecf395e53a70843a20c39c25c23f2a710d0f8fac815cbcd583b46c6d6  go/internal/web/properties/apartment_door_codes_test.go
   b47129dde56a0ed38c424248cca24ef2b35ff0e3013052c9d41e703e71c4c8ee  go/internal/web/properties/apartmentdoorcodes/i18n_keys.txt
   cfd49e0bca4eea6852a3a67f60c50022b8b356b524339be1b41f7f52c805c7f3  go/internal/web/properties/apartmentdoorcodes/i18n.json
   ae80280fe062c848d86457b26b1e428aa92ddb90e5be00a86d4bad72ccd3c144  go/cmd/ubyhost-web/register_web_properties_apartment_door_codes.go
   0795b2087fe1f185a359928f71414885d9f05b73e80ff50c74cf0d39e08d3ffe  go/cmd/ubyhost-web/register_web_properties_apartment_door_codes_test.go
   EOF2
   ```

   Every line must end with `: OK` (6 lines). Then commit (one call):

   ```bash
   git add go/internal/web/properties/apartment_door_codes.go go/internal/web/properties/apartment_door_codes_test.go go/internal/web/properties/apartmentdoorcodes/i18n_keys.txt go/internal/web/properties/apartmentdoorcodes/i18n.json go/cmd/ubyhost-web/register_web_properties_apartment_door_codes.go go/cmd/ubyhost-web/register_web_properties_apartment_door_codes_test.go && git commit -m "1702 step 1" | tail -3
   ```

2. Format, build and vet (one call, repo root):

   ```bash
   cd go && gofmt -l internal/web/properties cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/properties/... ./cmd/ubyhost-web/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). Nothing changed, so no commit.

3. Catalog check (repo root). If `App/.venv/bin/python` does not exist, write "Python checks: CI only (no App/.venv)" in the report and go to step 4. Else run (one call):

   ```bash
   cd App && .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -5; echo "i18n rc=${PIPESTATUS[0]}"; .venv/bin/python -m pytest tests/test_go_host_i18n.py -q --tb=short -rs 2>&1 | tail -5
   ```

   Expected: `i18n rc=0` with nothing before it, and a `passed` line with no `skipped`. Nothing changed, so no commit.

4. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if it is already running (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55472/data status' | head -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55472 && chown postgres /var/tmp/pg55472 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55472/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55472/data -o "-p 55472 -k /var/tmp/pg55472" -l /var/tmp/pg55472/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55472/postgres` in step 5. No PostgreSQL 16 binaries at that path: write "CI only" in the report and STOP before step 5.

5. Run the Go tests on PostgreSQL (one call, repo root):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55472/postgres go test ./internal/web/properties/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: two `ok` lines (`.../go/internal/web/properties`, `.../go/cmd/ubyhost-web`). Then show the named tests ran (one call):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55472/postgres go test ./internal/web/properties/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestApartmentDoorCodes|^TestApartmentDetailDoor$|^TestApartmentDetailRouteRegistered$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -10
   ```

   Expected: these five `--- PASS` lines (any order) and two `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestApartmentDoorCodes
   --- PASS: TestApartmentDoorCodesAccess
   --- PASS: TestApartmentDetailDoor
   --- PASS: TestApartmentDoorCodesRouteRegistered
   --- PASS: TestApartmentDetailRouteRegistered

   Then the skip count of the properties package: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55472/postgres go test ./internal/web/properties/... -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` must print `0`. (`cmd/ubyhost-web` has three probe tests that always skip without their own variables, `TestJobRunProbe`, `TestRouteProbe`, `TestJobProbe`; they are not counted.)

   Finally stop the throwaway server if you started it in step 4: `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55472/data stop' 2>&1 | tail -2` (expected: `server stopped`).

6. UX gate: nothing to do. This brief adds no markup, template, CSS or page (rule 7 and 10 do not apply); the redirect target is the 1701 page, whose gate is pending until 1705. Write "UX: no page change" in the report.

7. Write the report (§9), set `Status: review` in this file, and commit "1702 step 7" (`git add docs/tasks/1702-report.md docs/tasks/1702-go-apartment-update-door-codes.md`).

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `App/` (Python still serves the route); `docs/ENVIRONMENT.md`, Caddy and compose files; every other file under `go/`: in particular `apartment_detail*.go`, `properties.go`, `localpath.go`, the package `i18n.json`/`i18n_keys.txt`, `go/internal/ttlock/`, `go/internal/doorcodes/`, `go/internal/hostweb/`. Filing code (`go/internal/ubyport`, `App/app/reporting.py`). Hard rules of AGENTS.md: no secret or guest datum in a file or a log.

## 6. Commands

Exactly the commands of §4 (steps 2, 3 and 5). Test-map: the Go side has no row yet; the coordinator adds `go test ./internal/web/properties/... ./cmd/ubyhost-web/...` (PostgreSQL) from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about the files of this brief).

## 7. Acceptance

- [ ] Step 0: every anchor `1`, six sidecars; `sha256sum -c` of step 1 printed `: OK` for all 6 files.
- [ ] The format, build and vet step printed nothing.
- [ ] Step 3: `i18n rc=0` and a `passed` line, or "CI only (no App/.venv)" in the report.
- [ ] Step 5: two `ok` lines, the five named tests `--- PASS`, properties SKIP count `0`.
- [ ] Every refusal leaves `lock_provider`, `lock_id` and `audit` unchanged; the two writes add exactly one audit row each (`TestApartmentDoorCodes`, `TestApartmentDoorCodesAccess`).
- [ ] `git log --oneline --grep='^1702 step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1702 step') | tail -40` lists only the paths of §3.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python file changed; nothing was pushed to `main`.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor, a hash or a file count of step 0 or step 1 is not as stated (a missing anchor means 1703 or another brief changed the 1701 files first: the orchestrator re-bases the sidecars);
- a test fails twice (read the last 30 lines, fix nothing in the sidecar files yourself: report);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed, a file outside §3 needs a change, or §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1702-report.md` (500 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git show --stat` as in §7).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left, and "1702b (POST /apartments/{id}) and 1703 are next; the route must not be switched on before them".

## Risk list (for the reviewer)

- `apartment_door_codes.go` lines 44-69: the gate (`s.enter`: `_csrf`, id, login), the owner scope (`detailLoad` with `q.host.Workspace.ID`; a foreign or missing property and a plan without door codes all end at `/apartments` before any write).
- Lines 70-85: Turn off (the only write without a lock check, as in Python; it keeps `lock_id`).
- Lines 86-130: Turn on: the lock must be in the stored list and free (`detailLockUsers` excludes this property), both hours set; the write and the audit row. No transaction, as Python (`db.update` then `db.audit`).
- Test: `apartment_door_codes_test.go` lines 93-175 (the hand-written Locations, the audit rows, the refusals that write nothing).

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS`; the switch is brief 1705, after 1702b and 1703.
- **Rollback:** Revert the PR.

## Owner steps

None.
