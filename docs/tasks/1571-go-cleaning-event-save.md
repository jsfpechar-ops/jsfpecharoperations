# 1571: Go cleaning host pages, part 2: saving a cleaning (create and update)

Status: todo
Depends on: 1570 | Base commit: current tip of the working branch | Branch: task/1571-go-cleaning-event-save
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1571 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1571 step'` and `git show --stat <commit>`, never a fixed base commit.

## 1. Objective

Add the two writes of one cleaning to `go/internal/web/cleaning`: create (`POST /cleaning/events`) and update (`POST /cleaning/events/{id}`), with `cleaning.save_event`, including the JSON answers the calendar script reads. Dormant until the owner routes the paths.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (cleaning pages only); 2 privacy: no new personal-data field, no new retention line, no outbound request; 3 fixtures are made up (`@example.test`, test-only keys); 4 no new dependency (stdlib, pgx and packages already in `go.mod`); 5 plain PostgreSQL through `pgxpool`, the Python SQL with `$n` placeholders, no schema change; 6 light mode, the forms work without JavaScript; 11 Go first (this brief is the Go port; no file under `App/app/` changes).

**PR text (hard rule 2):** no new outbound request and no new personal-data field. A cleaning note (existing field, already in `retention.py`) is stored encrypted with the first data key, as `db.encrypt_field` does.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1571-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `5a2b750e6bef7b11a219016795ca7e87e19481b5fef020feacc44d9e090df64c` | `go/cmd/ubyhost-web/register_web_cleaning_host_events_test.go` | create | 22 |
| `1ddfb4faef56fc490680c16136f6c3935b6b1e5695500100ac9078adeb613244` | `go/internal/web/cleaning/host_events.go` | create | 339 |
| `a3ae7019612639918a8dd8362deee8d8ed1f3c6113c2079821c7974aa75ac1c2` | `go/internal/web/cleaning/host_events_test.go` | create | 326 |

**How the code is built.** `host_events.go` adds `parseHostForm` (url-encoded or multipart, with the body caps), `saveEvent` (the port of `cleaning.save_event`; it returns an error key instead of Python's ValueError text) and the two handlers. The editor page of brief 1570 is reused for the 422 and 409 answers (`(*hostServer).editor`).

**Parity notes (Python `App/app/routes/cleaning.py` unless named):**

| Route | Python | Go |
|---|---|---|
| `POST /cleaning/events` | `create_event` 176-201 | `(*hostServer).createEvent` |
| `POST /cleaning/events/{id}` | `update_event` 216-234 | `(*hostServer).updateEvent` |
| both | `cleaning.save_event` (App/app/cleaning.py 122-156), `parse_date`, `parse_time` | `(*hostServer).saveEvent` |

Details that are easy to get wrong and are tested: the checks run in Python's order (dates, times, notes, then for an update: property, state, revision); a date that matches `YYYY-MM-DD` but is not a real day (`2026-02-30`) raises a ValueError whose text the route does not know, so create shows the `property` error and update shows `changed` (409); a year outside 1900 to 2100 is `dates`; without `start_time` and `end_time` in the form an update keeps the stored times byte for byte (legacy malformed values included); `overridden` becomes 1 for a new cleaning, an already overridden one, or a changed day; the write is compare-and-set on `revision` and `state = 'scheduled'`; a cleaning that came from a booking cannot change property (`property`, 422); the JSON branch is chosen by `application/json` anywhere in `Accept`, answers `201 {"id","url"}`, `422 {"errors":{field:text}}`, `422/409 {"error":key}` and `200 {"ok":true}`; the calendar posts multipart `FormData` with the token in `x-csrf-token`, so the handler reads multipart bodies (1 MiB cap, answer 413 beyond it); the notes are stripped like Python's `str.strip()` and counted in characters.

**Known differences from Python, shared by every Go web area (not fixed here):** a missing or foreign record answers `404 {"detail":"Not Found"}` (and a non-integer id `422`), where Python shows the branded error page to a browser; `HEAD` is served by the `GET` pattern; a repeated query key reads the last value in the code written here (as Starlette does) but the older `buildPayload` reads the first. Python's `int()` also accepts `1_0` and a leading `+`; Go's parser accepts the sign only.

**Paths that become fully served by Go:** `/cleaning/events` (POST only) and `/cleaning/events/*` (POST only; `/cleaning/events/*/edit` and `/cleaning/events/*/delete` are separate paths and were done before). **Goes live on deploy if** the owner has already routed `/cleaning/events` or `/cleaning/events/*` to Go (assumed not).

**Anchors that must exist verbatim** (step 0): the Python function lines and the Go function lines listed there.

**Verified by the brief writer** (in a throwaway worktree of this branch, with the steps of briefs 1570 to 1571 applied exactly and in order, sidecars copied as step 1 does): `gofmt -l` printed nothing, `go build ./...` and `go vet ./internal/web/cleaning/... ./cmd/...` were silent, and `go test ./internal/web/cleaning/... ./cmd/ubyhost-web/... -count=1` passed on PostgreSQL 16, with the golden test of brief 1310 still green and the named tests PASS. The tests cover: create by form (redirect, `PRIVATE` headers, the stored row: property, day, `overridden` 1, revision 1, note encrypted and stripped, times kept when posted together), create as the calendar sends it (multipart body, token in the header, `201` JSON with `id` and `url`), every error as JSON and as a 422 page (bad format, year 1899, impossible day, one time, end before start, malformed time, a note of 5001 characters, text and empty property; foreign, archived and missing property are 404; signed out and a missing CSRF token write nothing), update (new day sets `overridden`, a booking-based cleaning keeps it 0, legacy times kept when not posted, times stored when posted, JSON `{"ok":true}`), and update errors (stale, missing and text revision, impossible day and text property are `409 changed`, the other keys `422`, a booking-based cleaning cannot change property, a foreign or missing event is 404, a foreign target property is 404, a dismissed cleaning is 409, no row changes on any error).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_cleaning_host_events_test.go` | create | route registration test |
| `go/internal/web/cleaning/host_events.go` | create | create and update of one cleaning, `saveEvent`, multipart form reader |
| `go/internal/web/cleaning/host_events_test.go` | create | route tests and POST helpers |
| `docs/tasks/1571-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1571-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `git log --oneline --grep='^1570 step' | wc -l | tail -1` prints a number of 1 or more (brief 1570 is on this branch).
   - `grep -cF "async def create_event(request: Request):" App/app/routes/cleaning.py | tail -1` prints `1`.
   - `grep -cF "async def update_event(request: Request, event_id: int):" App/app/routes/cleaning.py | tail -1` prints `1`.
   - `grep -cF "def save_event(apartment_id: int, values: dict, existing: dict | None = None) -> int:" App/app/cleaning.py | tail -1` prints `1`.
   - `grep -cF "func (s *hostServer) editor(" go/internal/web/cleaning/host.go | tail -1` prints `1`.
   - `grep -cF "func eventFor(" go/internal/web/cleaning/host_data.go | tail -1` prints `1`.
   - `grep -cF "func homeFor(" go/internal/web/cleaning/host_data.go | tail -1` prints `1`.
   - `ls go/internal/web/cleaning/host_events.go 2>&1 | tail -1` says "No such file" (nothing of this brief exists yet).
   - `find docs/tasks/1571-files -name '*.txt' | wc -l | tail -1` prints `3`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1571-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -6
   5a2b750e6bef7b11a219016795ca7e87e19481b5fef020feacc44d9e090df64c  go/cmd/ubyhost-web/register_web_cleaning_host_events_test.go
   1ddfb4faef56fc490680c16136f6c3935b6b1e5695500100ac9078adeb613244  go/internal/web/cleaning/host_events.go
   a3ae7019612639918a8dd8362deee8d8ed1f3c6113c2079821c7974aa75ac1c2  go/internal/web/cleaning/host_events_test.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1571 step 1".

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
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55570/postgres go test ./internal/web/cleaning/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestHostCreateEvent$|^TestHostCreateEventJSON$|^TestHostCreateEventErrors$|^TestHostUpdateEvent$|^TestHostUpdateEventErrors$|^TestCleaningHostEventRoutesRegistered$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of 6 tests (times differ) and two final `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestHostCreateEvent (0.NNs)
   --- PASS: TestHostCreateEventJSON (0.NNs)
   --- PASS: TestHostCreateEventErrors (0.NNs)
   --- PASS: TestHostUpdateEvent (0.NNs)
   --- PASS: TestHostUpdateEventErrors (0.NNs)
   --- PASS: TestCleaningHostEventRoutesRegistered (0.NNs)

5. Write the report (§9), set `Status: review` in this file and commit "1571 step 5". Do not open a PR (one big PR mode); the owner or the orchestrator opens it with the PR text of §2.

## 5. Do not touch

`App/` (no Python file changes; the Python routes stay the live ones), `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, every file of brief 1570 and the existing files of the package (`handler.go`, `model.go`, `render.go`, `i18n.go`, `i18n.json`, `templates/`). Hard rules of AGENTS.md: no secret or guest datum in a file or a log (the test data is made up), nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 2 and 4). No test-map row exists yet for `go/internal/web/cleaning` host pages; the coordinator adds one from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 3 files.
- [ ] The format, build and vet step printed nothing.
- [ ] The test step printed `ok` for both packages, and each of the 6 named tests printed `--- PASS` (none `SKIP`, none `FAIL`) on PostgreSQL.
- [ ] `git log --oneline --grep='^1571 step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1571 step') | tail -40` lists only the paths of §3 and the sidecars.
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

Write `docs/tasks/1571-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git diff --stat` as in §7).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of: `host_events.go`: `saveEvent` (order of the checks, the compare-and-set `UPDATE ... WHERE id AND revision AND state = 'scheduled'`, `overridden`), `createEvent` and `updateEvent` (404 before any write, the apartment is taken from `homeFor` of the signed-in owner, the key mapping of the two `else` branches), `parseHostForm` (multipart body cap).

## Owner steps

None: nothing is switched on. The path switch for the whole area is described in the owner steps of brief 1573 and must wait for it.
