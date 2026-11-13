# 1444: Go guest guide editor, part 5: Quick answers (five steps and the done page)

Status: todo
Depends on: 1440 | Base commit: 68c0e0985 | Branch: task/1444-go-guide-editor-quick
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the four Quick answers routes of `App/app/routes/guest_guide.py` to `go/internal/web/ai`: `GET /apartments/{id}/guide/quick` (go to the first open step), `GET .../quick/done`, `GET .../quick/{step}` and `POST .../quick/{step}`, with the two templates and the rest of `guide_facts.py` (save, fields, guest lines). The fact table and the guest sentences are read from `guide/guide_facts.json`, which a new script writes from the Python so the two cannot drift.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (guide pages only); 2 privacy: no new personal-data field, no new retention line, no outbound request; 3 fixtures are made up (`@example.test`, test-only secrets); 4 no new dependency (stdlib, pgx and packages already in `go.mod`); 5 plain PostgreSQL through `pgxpool`, the Python SQL with `$n` placeholders; 6 light mode, the forms work without JavaScript (they post plain forms); 7 and 10 see §7.

**PR text (hard rule 2):** no new outbound request and no new personal-data field: a Quick answer is a yes/no or a time about the property (`guide_fact` rows), never about a person.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1444-files/<repo path>.txt`.

| sha256 | file | action | lines |
|---|---|---|---|
| `0bd9c782d4cf3b02a88331c634413521092e86171f8cbe3b70b23eab13b42a6a` | `go/internal/web/ai/guide_quick.go` | create | 338 |
| `9de71fdd3f105908cd75ad3fc02f09e3a937082234c35d59d268d656c7d5b0b8` | `go/internal/web/ai/guide/guide_facts.json` | create | 231 |
| `6b0dcd77fc48de6ce5a099d476331ed734aeea53f2eb1aa03592dc6794a049d4` | `go/internal/web/ai/guide/templates/guide_quick.tmpl` | create | 35 |
| `ab3599cbe5baf134201c87cc814a0026607684887c9b0bcecd154bbf27b2fc70` | `go/internal/web/ai/guide/templates/guide_quick_done.tmpl` | create | 29 |
| `1df60696248d89820474429d990de577f713223ba2700e47e87e89d754f61271` | `go/internal/web/ai/guide_quick_test.go` | create | 164 |
| `3197988680e96f78cf97e65f19d35645625a1ee01a7a7b7020aa4b5c8b4bd79a` | `App/scripts/go_guide_facts_i18n.py` | create | 57 |
| `488e5b7553cb9e76d36eb90ae8477a091536e408814e1c61d5c0b9f152380245` | `App/tests/test_go_guide_facts_i18n.py` | create | 11 |

**How the code is built (for the reviewer; the executor reads no Go file, it only copies and runs).** The routes register through the table in `guide_common.go` (`guideAdd` in an `init()`), and `go/cmd/ubyhost-web/register_web_ai_guide.go` (brief 1440) hands them to `registerRoutes`; no other file of `go/cmd` changes. Every handler starts with `s.enter(w, r)`, which runs in FastAPI's order: for a POST `hostweb.CSRF` (header or `_csrf` field, multipart too), then the int path parameters (`422` when one is not an int), then `hostweb.Login` (`auth.require_login`), then `s.home(w, q)` (`_home`: the property of the signed-in workspace, not archived, else `404`). Redirects are `q.back` (`admin_helpers.back`, Starlette quoting), flashes are `q.flash(key, params)` from the guide catalog `guide/i18n.json`. Pages are `layout.Render` through `s.render` (host layout shell, `Cache-Control: no-store`). Every package-level name of these files starts with `guide`, so it cannot meet a name in the files of the other thread that works in `go/internal/web/ai` (`havel*.go`, `leon_setup*.go`); those files are not yours and not read.

**Parity notes:**

| Route | Python | Go |
|---|---|---|
| `GET /apartments/{id}/guide/quick` | `guide_quick` 238-244; `guide_facts.next_step` 97-100 | `quickIndex` |
| `GET /apartments/{id}/guide/quick/done` | `guide_quick_done` 247-275; `guide_facts.lines` 116-133 | `quickDone`, `factLines` |
| `GET /apartments/{id}/guide/quick/{step}` | `guide_quick_step` 278-291; `guide_facts.step_fields` 103-113 | `quickStep`, `stepFields` |
| `POST /apartments/{id}/guide/quick/{step}` | `guide_quick_save` 294-309; `guide_facts.save_step` 78-94, `mark_seen` 74-75, `_put` 55-60, `_clean` 63-71 | `quickSave`, `saveStep` |

- A step that is not one of `times, rules, access, kitchen, comfort` is `404` after the login and ownership checks (also for the POST). A blank or invalid answer deletes the fact; "skip" only marks the step seen; the last step goes to `.../quick/done`.
- The "done" page opens like the overview: `ensure_defaults` runs (a write on a GET, as in Python). Guest sentences come from the **guest** catalog (`app/i18n.py`, keys `guide_fact_*`) in the host's language; the host language `vi` has no guest table and reads English (`i18n.normalise_language("vi")`), so `guide_facts.json` holds `en` and `cs` only.
- A time matches `^([01]\d|2[0-3]):[0-5]\d$` where Python's `\d` also accepts other decimal digits; the Go pattern uses `\p{Nd}`.
- `App/scripts/go_guide_facts_i18n.py` (new) writes `guide/guide_facts.json`: the steps, the fact table in order and the guest sentences. `App/tests/test_go_guide_facts_i18n.py` (new) runs it with `--check` in CI. `TestGuideFactTableMatchesCatalog` checks the Go steps and every key against the file.

**Known differences from Python, shared by every Go web area (not fixed here):** a missing or foreign record answers `404 {"detail":"Not Found"}` (and a non-integer id `422`), where Python shows the branded error page to a browser; `HEAD` and a wrong method answer `405` JSON (Python too); Go sets `Cache-Control` as the Python page routes do (`no-store`), and the `m.wrap` default `no-store, private` covers redirects.

**Anchors that must exist verbatim** (step 0): the four function lines in `App/app/routes/guest_guide.py`.

**Verified by the brief writer (in a throwaway worktree of this repo, sidecars copied exactly as step 1 does):** the four named tests PASS on PostgreSQL 16 (answers stored, invalid ones refused, blank removes, ranges, skip, redirect chain to `done`, `done` page content and states, ownership on all four routes, Czech and Vietnamese lines); the step and done page bodies equal the Jinja render of `guest_guide_quick.html` (steps `times` and `rules` with answers) and `guest_guide_quick_done.html` (whitespace between tags normalised). `App/scripts/go_guide_facts_i18n.py` ran on the real Python modules (with a stub for the missing `fastapi` import of `host_i18n`) and its `--check` is clean; the pytest file was not run (no application environment).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/ai/guide_quick.go` | create | four routes and the Quick answers rules |
| `go/internal/web/ai/guide/guide_facts.json` | create | generated from guide_facts.py and i18n.py (do not edit) |
| `go/internal/web/ai/guide/templates/guide_quick.tmpl` | create | Go twin of guest_guide_quick.html |
| `go/internal/web/ai/guide/templates/guide_quick_done.tmpl` | create | Go twin of guest_guide_quick_done.html |
| `go/internal/web/ai/guide_quick_test.go` | create | rules and route tests |
| `App/scripts/go_guide_facts_i18n.py` | create | writes/checks guide_facts.json |
| `App/tests/test_go_guide_facts_i18n.py` | create | runs the script with --check |
| `docs/tasks/1444-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1444-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints `task/1444-go-guide-editor-quick`.
   - `grep -cF "def guide_quick(request: Request, apartment_id: int):" App/app/routes/guest_guide.py | tail -1` prints `1`.
   - `grep -cF "def guide_quick_done(request: Request, apartment_id: int):" App/app/routes/guest_guide.py | tail -1` prints `1`.
   - `grep -cF "def guide_quick_step(request: Request, apartment_id: int, step: str):" App/app/routes/guest_guide.py | tail -1` prints `1`.
   - `grep -cF "async def guide_quick_save(request: Request, apartment_id: int, step: str):" App/app/routes/guest_guide.py | tail -1` prints `1`.
   - `ls go/internal/web/ai/guide_common.go go/internal/web/ai/guide_data.go go/cmd/ubyhost-web/register_web_ai_guide.go 2>&1 | tail -5` lists all three (brief 1440 is on this branch), and the files of §3 for this brief do not exist yet (`ls` says "No such file").
   - `find docs/tasks/1444-files -name '*.txt' | wc -l | tail -1` prints `7`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1444-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   0bd9c782d4cf3b02a88331c634413521092e86171f8cbe3b70b23eab13b42a6a  go/internal/web/ai/guide_quick.go
   9de71fdd3f105908cd75ad3fc02f09e3a937082234c35d59d268d656c7d5b0b8  go/internal/web/ai/guide/guide_facts.json
   6b0dcd77fc48de6ce5a099d476331ed734aeea53f2eb1aa03592dc6794a049d4  go/internal/web/ai/guide/templates/guide_quick.tmpl
   ab3599cbe5baf134201c87cc814a0026607684887c9b0bcecd154bbf27b2fc70  go/internal/web/ai/guide/templates/guide_quick_done.tmpl
   1df60696248d89820474429d990de577f713223ba2700e47e87e89d754f61271  go/internal/web/ai/guide_quick_test.go
   3197988680e96f78cf97e65f19d35645625a1ee01a7a7b7020aa4b5c8b4bd79a  App/scripts/go_guide_facts_i18n.py
   488e5b7553cb9e76d36eb90ae8477a091536e408814e1c61d5c0b9f152380245  App/tests/test_go_guide_facts_i18n.py
   EOF
   ```

   Every line must end with `: OK`. Then commit "1444 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/ai cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/ai/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all (gofmt lists nothing, build and vet are silent). Anything printed: STOP (§8). Commit "1444 step 2".

3. PostgreSQL: as brief 1440 step 3 (the server on port 55440 may still run: `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1440/data status' | tail -1` says `server is running`; if stopped, run only the `pg_ctl ... start` part of that step). Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres` below. No server: write "CI only" in the report and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres go test ./internal/web/ai/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
   ```

   Expected: two lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai	<seconds>s` and `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	<seconds>s`. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres go test ./internal/web/ai/ -count=1 -v -run '^TestGuideFactTableMatchesCatalog$|^TestGuideCleanFact$|^TestGuideQuickRoutes$|^TestGuideFactLinesCzechAndVietnamese$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of 4 tests (times differ) and a final `ok` line; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestGuideFactTableMatchesCatalog (0.NNs)
   --- PASS: TestGuideCleanFact (0.NNs)
   --- PASS: TestGuideQuickRoutes (0.NNs)
   --- PASS: TestGuideFactLinesCzechAndVietnamese (0.NNs)

5. Generated files and Python test (from `App/`; needs the application environment: `ls .venv/bin/python` exists). Else write "CI only" in the report and skip this step:

   ```bash
   cd App && .venv/bin/python scripts/go_guide_facts_i18n.py --check 2>&1 | tail -5; .venv/bin/python -m pytest tests/test_go_guide_facts_i18n.py tests/test_go_host_i18n.py -q --tb=short -x 2>&1 | tail -30
   ```

   Expected: the script prints nothing (no `stale:` line); pytest ends with `2 passed` (one test in each file). A `stale:` line: STOP (Python moved; never edit the JSON to match). Commit "1444 step 5".

6. Write the report (§9), set `Status: review` and commit "1444 step 6". Open one PR titled "1444: Go guest guide editor, part 5: Quick answers (five steps and the done page)" with the PR text of §2 in its description.

## 5. Do not touch

As brief 1440 §5, plus every file of briefs 1440 to 1443, 1445 and 1446. `App/app/` stays untouched: the two Python files are new and only import it.

## 6. Commands

Exactly the commands of §4 (steps 2 and 4, and the Python commands of step 5). No test-map row exists yet for `go/internal/web/ai`; the coordinator adds one from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | tail -30` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 7 files.
- [ ] Step 2 printed nothing (gofmt, build and vet clean).
- [ ] Step 4 printed `ok` for both packages, and each of the 4 named tests printed `--- PASS` (none `SKIP`, none `FAIL`) on PostgreSQL.
- [ ] Step 5 printed no `stale:` line and `2 passed` (or the report says "CI only" with the reason).
- [ ] `git diff --stat main...HEAD | tail -20` (`origin/main...HEAD` if there is no local `main`) lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed to `main`.
- [ ] UI: not applicable in this PR (rules 7 and 10): the pages are dormant (no path routes to them) and the Python-side browser tests cannot reach the Go service. The UX gate of rule 10 runs on staging before the owner adds the paths (brief 1412 is the pattern); see Owner steps.

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

Write `docs/tasks/1444-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git diff --stat main...HEAD | tail -20`; `origin/main...HEAD` if there is no local `main`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `guide_quick.go` (`saveStep` and `guideCleanFact`: what may reach `guide_fact`; `quickSave`: step check, then the form; every route calls `s.home`) and the new Python script. The templates are markup only. The `.json` file is generated: do not review it line by line, check that the script's `--check` is clean.

## Owner steps

None: nothing is switched on.
