# 1596: Go onboarding part 3: clear the demo dataset (POST /demo/reset)

Status: todo
Depends on: 1595 (its `onboardingPageStrings` catalog and test seed helpers; verified in the order 1595, 1596) | Base commit: current tip of the working branch | Branch: task/1596-go-demo-reset
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (deletion; exact files; fresh Fable review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1596 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1596 step'` and `git show --stat <commit>`, never a fixed base commit.

## 1. Objective

Port `reset_demo` (`App/app/routes/onboarding.py` 37-44) and `demo.clear` (`App/app/demo.py` 880-942, with `passport_photos.delete_photo`) to `go/internal/web/onboarding`, and register `POST /demo/reset` in ubyhost-web. The route is dormant: nothing is added to `UBYHOST_GO_PATHS`. `POST /demo` (`demo.seed`) is not part of this brief (brief 1597, blocked).

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (only the made-up demo dataset is removed); 2 privacy: no new personal-data field, no retention line, no outbound request; deletion: the route deletes rows and passport photo files exactly where Python does, scoped to the signed-in workspace; 3 fixtures are made up (`@example.test`, test-only keys); 4 no new dependency; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, no schema change; 6 the form is the one on the dashboard (Python); 11 Go first: this brief is the Go port. The two files under `App/` are **go-first exception 1** (port plumbing: a golden script and its parity test); no Python application file changes.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. `POST /demo/reset` deletes the built-in demo dataset of the signed-in workspace (rows and the passport photo files of its made-up guests), as `demo.clear` does.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1596-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `b7edf5352bcd372cec70dee7af108727f1ac544d27ff09e2d4b5cf0e7d9758e0` | `go/internal/web/onboarding/demo_reset.go` | create | 187 |
| `0b47dea12b4e3845d4bcd658fc91e2baf1c9a5c4a28d8e67c166e6161be8c165` | `go/internal/web/onboarding/demo_reset_test.go` | create | 288 |
| `dbf4daee3989b4a33f310b0a039a233d615c18abf287ac424c9649f6e079df3f` | `go/internal/web/onboarding/testdata/demo_reset_golden.json` | create | 848 |
| `7b66faf43418a3f482a0e04e7cd25569e6974b0691075bdb7a478f8604c4cfdc` | `go/cmd/ubyhost-web/register_web_onboarding_demo.go` | create | 25 |
| `ab94b610de0973df56622a63e35a4bbd5f688cb3f2a5c24e9d2f822a0269b3da` | `go/cmd/ubyhost-web/register_web_onboarding_demo_test.go` | create | 23 |
| `85cf82e6c1cc281fb963d1ff3f663ab47193df801e53c6d4769b110b24f462df` | `App/scripts/go_demo_reset_golden.py` | create | 185 |
| `4bf71e17b5776e14ca9f8c5edbe0ef968d35d3f0172a7ef4d540ceea8d01874e` | `App/tests/test_go_demo_reset_golden.py` | create | 29 |

**How the code is built (for the reviewer; the executor reads no Go file, it only copies and runs).**

- `DemoResetHandler` runs `guard` of routes.go (CSRF first, as `admin.router`'s `protect_host_post`, then `require_login`), then `demoClear`, then `hostweb.Back("/", ...)` with `flash.demo.cleared` as `msg` or `flash.error.demo_missing` as `err`, translated in the request language (the keys are in the 1595 catalog).
- `demoClear` is `demo.clear(owner)` with the owner `session.Host.Workspace.ID` (never 0 after login, so Python's "owner is None: every owner" branch cannot happen): the entities named `Josef Novák (demo)` or `Demo Controller s.r.o.` of the owner; none: false. The owner's properties whose name is `Vinohrady Studio (demo)` or `Karlín Loft (demo)` or whose operator or controller is one of those entities (archived ones too, as Python); none: false (the entities stay, as Python). Then the passport photo files of every guest of those properties (`<UBYHOST_DATA_DIR>/passport_photos/<id><ext>[.enc]` for `.jpg .pdf .png .webp`, regular files only: the twin of `retention.deletePhoto`, kept in this package so no live package changes), then in **one transaction**: per property `alert`, `apartment_slug`, the 13 feature tables in Python's order, the property (the schema cascades reservations, guests, feeds and the rest); the entities; the `demo_cleared` audit row (`detail` "", actor, `actor_user_id`, `impersonator_user_id` only while previewing, as `db.audit` after `require_login`).
- `register_web_onboarding_demo.go`: an `init()` that adds `POST /demo/reset`; `POST /demo` still falls to the catch-all (the registration test asserts both).
- `App/scripts/go_demo_reset_golden.py` seeds a throwaway SQLite database (two demos with a renamed property on a demo controller and an archived property with a demo name, real properties of the same hosts, a host with only a demo entity, a host without a demo, a row on a demo and on a real property in every table Python clears) and photo files, sends 7 requests in order (signed out, no CSRF token, no demo, entity without a property in Czech, clear, clear again, an admin clearing a previewed workspace in Vietnamese) and records the answers, the ids left per table, the photo files left and the audit rows. `TestDemoResetMatchesPython` replays it on PostgreSQL and a temporary data directory.

**Differences from Python (intended, tested):**
1. Python deletes statement by statement, so a refused delete (for example an invoice or another owner's property still pointing at a demo row) leaves a half-cleared demo and a 500. Go deletes all rows in one transaction: the same 500, but no row is gone (`TestDemoResetRollsBack`).
2. Guests exist but `UBYHOST_DATA_DIR` is empty, or a photo file cannot be checked or removed: Go answers 500 before any row is deleted (`TestDemoResetStopsBeforeDeleting`). Python falls back to its default data directory or raises in the middle.

**Production note (owner item 4):** the Go service mounts the data volume read-only (`ubyhost-data:/data:ro` in `deploy/lightsail/docker-compose.yml`). With that mount, a clear that has a photo file to remove answers 500 and deletes nothing (difference 2), so `/demo/reset` must not be switched to Go before the owner makes `/data` writable for `ubyhost-go` (the same decision as brief 1447). Production runs the real UbyPort, so it has no demo dataset in normal use.

**Verified by the brief writer** (in a throwaway copy of go-wave3 at 859d114d5, with the steps of briefs 1595 and then 1596 applied exactly as written, sidecars copied as step 1 does): `sha256sum -c` all OK, `gofmt -l` printed nothing, `go build ./...` and `go vet ./internal/web/onboarding/... ./cmd/...` were silent, `go test ./internal/web/onboarding/... ./cmd/ubyhost-web/... -count=1` passed on PostgreSQL 16 with no test skipped, and the named tests of step 5 printed `--- PASS`. With `App/.venv`: `tests/test_go_demo_reset_golden.py` and `tests/test_go_onboarding_page_golden.py` passed (2 passed, 0 skipped).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/onboarding/demo_reset.go` | create | `demoClear`, `demoDeletePhoto`, `DemoResetHandler` |
| `go/internal/web/onboarding/demo_reset_test.go` | create | golden parity, stop-before-delete, rollback |
| `go/internal/web/onboarding/testdata/demo_reset_golden.json` | create | golden written by the Python script |
| `go/cmd/ubyhost-web/register_web_onboarding_demo.go` | create | registers `POST /demo/reset` |
| `go/cmd/ubyhost-web/register_web_onboarding_demo_test.go` | create | route registration test |
| `App/scripts/go_demo_reset_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_demo_reset_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1596-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1596-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `git log --oneline --grep='^1595 step' | wc -l | tail -1` prints a number of at least `2` (brief 1595 ran on this branch).
   - `grep -cF 'var onboardingPageStrings = hostweb.Load(onboardingPageJSON)' go/internal/web/onboarding/onboarding_page.go | tail -1` prints `1`.
   - `grep -cF 'func onboardingPageSeed(t *testing.T, pool *pgxpool.Pool, g onboardingPageGolden, getenv func(string) string) {' go/internal/web/onboarding/onboarding_page_test.go | tail -1` prints `1`.
   - `grep -cF 'flash.demo.*' go/internal/web/onboarding/onboardingpage/i18n_keys.txt | tail -1` prints `1`.
   - `grep -cF '@router.post("/demo/reset")' App/app/routes/onboarding.py | tail -1` prints `1`.
   - `grep -cF 'def clear(owner_user_id: Optional[int] = None) -> bool:' App/app/demo.py | tail -1` prints `1`.
   - `grep -cF 'func guard(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) (*session.Host, bool) {' go/internal/web/onboarding/routes.go | tail -1` prints `1`.
   - `ls go/internal/web/onboarding/demo_reset.go 2>&1 | tail -1` says "No such file".
   - `find docs/tasks/1596-files -name '*.txt' | wc -l | tail -1` prints `7`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1596-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -8
   b7edf5352bcd372cec70dee7af108727f1ac544d27ff09e2d4b5cf0e7d9758e0  go/internal/web/onboarding/demo_reset.go
   0b47dea12b4e3845d4bcd658fc91e2baf1c9a5c4a28d8e67c166e6161be8c165  go/internal/web/onboarding/demo_reset_test.go
   dbf4daee3989b4a33f310b0a039a233d615c18abf287ac424c9649f6e079df3f  go/internal/web/onboarding/testdata/demo_reset_golden.json
   7b66faf43418a3f482a0e04e7cd25569e6974b0691075bdb7a478f8604c4cfdc  go/cmd/ubyhost-web/register_web_onboarding_demo.go
   ab94b610de0973df56622a63e35a4bbd5f688cb3f2a5c24e9d2f822a0269b3da  go/cmd/ubyhost-web/register_web_onboarding_demo_test.go
   85cf82e6c1cc281fb963d1ff3f663ab47193df801e53c6d4769b110b24f462df  App/scripts/go_demo_reset_golden.py
   4bf71e17b5776e14ca9f8c5edbe0ef968d35d3f0172a7ef4d540ceea8d01874e  App/tests/test_go_demo_reset_golden.py
   EOF
   ```

   Every line must end with `: OK` (7 lines). Then commit "1596 step 1" (`git add -A && git commit -m "1596 step 1"`).

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/onboarding cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/onboarding/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). No commit.

3. Python checks (repo root). If `App/.venv/bin/python` does not exist, write "Python checks: CI only (no App/.venv)" in the report and go to step 4. Else run:

   ```bash
   cd App && .venv/bin/python -m pytest tests/test_go_demo_reset_golden.py tests/test_go_onboarding_page_golden.py -q --tb=short -rs 2>&1 | tail -5
   ```

   Expected: `2 passed`, no `skipped`. No commit.

4. PostgreSQL: exactly step 4 of brief 1595 (port 55595, data dir `/var/tmp/pg55595`); skip the start if `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55595/data status' | tail -1` says `server is running`. No PostgreSQL 16 binaries: write "CI only" in the report and STOP before step 5.

5. Run the tests on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55595/postgres go test ./internal/web/onboarding/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: two `ok` lines. Then:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55595/postgres go test ./internal/web/onboarding/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestDemoResetMatchesPython$|^TestDemoResetStopsBeforeDeleting$|^TestDemoResetRollsBack$|^TestOnboardingDemoRouteRegistered$|^TestOnboardingPageMatchesPython$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of these 5 tests and two `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestDemoResetMatchesPython
   --- PASS: TestDemoResetStopsBeforeDeleting
   --- PASS: TestDemoResetRollsBack
   --- PASS: TestOnboardingPageMatchesPython
   --- PASS: TestOnboardingDemoRouteRegistered

   Then `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55595/postgres go test ./internal/web/onboarding/... ./cmd/ubyhost-web/... -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` must print `0`.

6. Write the report (§9), set `Status: review` in this file and commit "1596 step 6".

## 5. Do not touch

`App/app/` (no Python application file changes; Python still serves `/demo` and `/demo/reset`), `docs/ENVIRONMENT.md`, Caddy and compose files (the read-only `/data` mount is the owner's decision), `UBYHOST_GO_PATHS`, every other file under `go/`: the files of brief 1595, `setup.go`, `routes.go`, their tests, any `wizard*.go` file (briefs 1599-1604), `go/internal/retention/`, `go/internal/hostweb/`, `go/internal/session/`. Hard rules of AGENTS.md: no secret or guest datum in a file or a log, nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 2, 3 and 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 7 files.
- [ ] The format, build and vet step printed nothing.
- [ ] Step 3: `2 passed`, or "CI only (no App/.venv)" in the report.
- [ ] Step 5: two `ok` lines, the 5 named tests `--- PASS`, SKIP count `0`.
- [ ] `git show --stat --format=%s $(git log --format=%h --grep='^1596 step') | tail -30` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed to `main`.
- [ ] UI: none (a POST that redirects).

## 8. Stop and ask

Stop, and write the report, if: an anchor, a hash or a file count of step 0 or 1 is not as stated; a test fails twice (fix nothing in the sidecars yourself); you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1596-report.md` (600 tokens at most) and set this brief's `Status: review`: files changed, each command with its last 5 lines and the SKIP count, §7 ticked, Deviations, Questions, Owner steps left.

## Risk list (for the reviewer)

Read the full diff of `demo_reset.go`: every SELECT is scoped by `owner_user_id = <workspace>`; the property query matches Python's three conditions and nothing wider; no row is deleted when a photo cannot be handled; the deletes and the audit row are one transaction; `demoDeletePhoto` only touches `<id><ext>` and `<id><ext>.enc` of the four extensions and only regular files. In `demo_reset_test.go`, the expected rows, files and audit rows come from the Python golden, not from Go.

## Owner steps

None now: nothing is switched on. Later, only after both (a) the owner made the data volume writable for `ubyhost-go` (owner item 4, same as brief 1447) and (b) brief 1597 (`POST /demo`) is unblocked and merged, so both demo buttons move together:

1. On the server, open the env file that holds `UBYHOST_GO_PATHS` (see docs/ENVIRONMENT.md).
2. Add `/demo/reset` (and `/demo` from brief 1597) to the list.
3. Run `scripts/caddy-validate.sh`, then `docker compose up -d caddy`.
4. Rollback: remove the two paths again and repeat step 3.
