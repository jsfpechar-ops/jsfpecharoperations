# 1602: Go setup wizard, part 4: POST /apartments/{id}/setup (marks, hide and show, the police Wait, the demo stay)

Status: review
Tier: A
Depends on: 1601 (and through it 1599 and 1600; their files must be on the branch) | Base commit: current tip of the working branch | Branch: task/1602-go-setup-wizard-post
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1602 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1602 step'` and `git show --stat <commit>`, never a fixed base commit.

## 1. Objective

Port `setup_action` of `App/app/routes/onboarding_wizard.py` (`POST /apartments/{apartment_id}/setup`, lines 342-418) to `go/internal/web/onboarding`: the CSRF, id, login and property guards; hide and show; the step marks (skip, wait, none, done) for the guide's own step only; the police step's Wait, which also saves the automation choice with Python's checks and normaliser (`admin.automation_choice_error`, `admin._automation_timing_values`) or re-renders the police page with 400; the next guide or the finish; and the try-it actions (create the demo stay, keep it, skip when there is none). One branch is not ported: **skip on the try-it page while a demo stay exists** deletes the stay with `demo.delete_demo_stay`, which also removes the demo guests' passport photo files; Go answers 501 there and writes nothing (brief 1603, blocked). Dormant: no path is routed.

## 2. Context

Rules (AGENTS.md): 1 filing correctness: the Wait button writes `apartment.automation_mode` and `submit_after_hours`, which the auto-submit worker reads (`docs/UBYPORT_CORE.md`, "Auto-submit & scheduler"). Go keeps Python's rules exactly: the mode must be `immediate`, `scheduled` or `manual`; scheduled needs whole hours 1 to 48; the stored hours are `min(int(hours) or 24, 48)` (so a manual or immediate save with no hours stores 24, as Python). The golden pins the stored rows. A demo stay is created with `source = 'demo'`, as Python, so it is never reported. 2 privacy: no new personal-data field, no new retention line, no outbound request. 3 fixtures are made up. 4 no new dependency (`crypto/rand` for the demo uid). 5 SQL through `pgxpool` with `$n`, Postgres-portable, no schema change. 6 light mode, every form works without JavaScript. 11 Go first. **Go-first exception used:** exception 1 (port plumbing): `App/scripts/onboarding_wizard_golden_post.py` and `App/tests/test_go_onboarding_wizard_post.py`. No file under `App/app/` changes.

**PR text (hard rule 2 and UBYPORT_CORE "Guidance" 4):** no new outbound request and no new personal-data field. Filing behaviour does not change: the Go route stores the same automation mode and delay as the Python route for every input (golden on PostgreSQL against the Python route on SQLite, plus a unit table of edge values); it writes the same audit lines (`property_setup_step` with `apartment=N step=S action=A`, `apartment=N action=hide|show`, `apartment_updated` with `id=N`) and the same `property_setup:<id>` settings.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1602-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `f04b710b0ee52ceac890b348eb1b3623c4ebc65475ab0c4502a67d7b365918be` | `App/scripts/onboarding_wizard_golden_post.py` | create | 71 |
| `1990d6591e50920f780f4d913fce03ec0264fe6ae958e7df9f1f13eda2ec9953` | `App/tests/test_go_onboarding_wizard_post.py` | create | 17 |
| `7c7c3d7fc883c09a536fe982a3c07d04da105a0d3a91d606426e45bcfd980a3e` | `go/cmd/ubyhost-web/register_web_onboarding_wizard_post_test.go` | create | 17 |
| `33c8d666ae6065b49b43390ed6bffc60692cb4ca630037fe6cd4d4fc210171e7` | `go/internal/web/onboarding/testdata/wizard_golden_post.json` | create | 1815 |
| `b3e94c5491f509aff76998f8cb5e9826858b3b995add6f1035e93a60738376ca` | `go/internal/web/onboarding/wizard_post.go` | create | 349 |
| `9b3c502098965a31163733a02dd88b0836445edc5d22d8d6ee873595d9e9c51e` | `go/internal/web/onboarding/wizard_post_golden_test.go` | create | 8 |
| `2e42a194f5432089cc2d53592c402e29102c3fdde0ea1672d50b54a260a6e7f6` | `go/internal/web/onboarding/wizard_post_test.go` | create | 77 |

**How the code is built (for the reviewer; the executor reads no Go file).** `wizard_post.go` registers `POST /apartments/{id}/setup` through the 1599 route table (`wizardAdd` in an `init()`), so no earlier file changes. Order as FastAPI runs it: the router's CSRF dependency (`hostweb.CSRF`, which also parses the form), the integer path id, `require_login`, then `access.apartment` (owner scope, no PIN backfill; a missing or foreign property goes back to `/apartments` with the error flash). Form values are read as Starlette does (last value, stripped: `formStr` of `routes.go`); `_form_int` uses `pyInt` of `routes.go`. For a step action the 1599 context is built (it has Python's side effects: PIN backfill, guest link slug, celebration on `done`), the guide must be on that step and the action must be allowed for it (`_SETUP_ACTIONS`), then `Mark`, the audit line, and the next guide from the stored state with the facts of this request (`_guide_after`), else `Finish` and the finish page with the "Setup complete" flash. The one refusal re-renders the police page of 1600 with status 400, the posted police fields and timing as the draft (`refuse_setup_save`), and the error key in the `operator_error` slot; without `setup_step=police` it goes back to the guide. The audit line uses `auditSQL` of `routes.go` with the detail text.

**Parity notes:** the golden (`testdata/wizard_golden_post.json`, 29 cases run in order on one database, plus the final rows: setup states, PIN presence, the audit lines, demo stays, every property's timing) covers: no CSRF token, a text id, signed out, another host's and a missing property; hide, show, show when not hidden, show of a hidden property in Czech; a step that is not the guide's, no guide, an action the step does not take (property skip, retired `door_lock` none, calendar done); calendar skip; the police Wait with bad hours, a bad mode (Vietnamese), a bad choice without `setup_step`, a valid immediate choice with 100 hours (stored 48), a plain Wait; guest link done that finishes the guide and once more after; the try-it demo (created, the same one again, an existing one in Czech, a property without a guest link token), keep, skip without a demo stay and an unknown action. `TestWizardSkipWithDemoStayIs501` covers the unported branch (501, the demo stay and the audit table unchanged) and `TestWizardAutomationTiming` the edge values of the timing rules.

**Known differences from Python:** those of brief 1599, and the 501 of the try-it skip with a demo stay (brief 1603). A form field value with digits grouped by underscores (`1_2`) parses as Python does; a number past the 64-bit range counts as not a number (Python keeps it and then refuses it or caps it to 48, the same result).

**Paths that become fully served by Go:** `/apartments/*/setup` (GET and POST) and `/apartments/*/setup/*` (GET), except the one 501 branch above. **Assumption:** as in 1599, no `/apartments` path is in `UBYHOST_GO_PATHS`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/onboarding_wizard_golden_post.py` | create | golden writer, part "post" |
| `App/tests/test_go_onboarding_wizard_post.py` | create | the committed golden matches the Python route |
| `go/cmd/ubyhost-web/register_web_onboarding_wizard_post_test.go` | create | route registration test |
| `go/internal/web/onboarding/testdata/wizard_golden_post.json` | create | golden |
| `go/internal/web/onboarding/wizard_post.go` | create | `POST /apartments/{id}/setup` |
| `go/internal/web/onboarding/wizard_post_golden_test.go` | create | `TestWizardPostMatchesPython` |
| `go/internal/web/onboarding/wizard_post_test.go` | create | the 501 branch, timing edge values |
| `docs/tasks/1602-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1602-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `ls go/internal/web/onboarding/wizard_finish.go go/internal/web/onboarding/wizard_pages.go go/internal/web/onboarding/wizard_step.go 2>&1 | tail -3` lists all three (briefs 1599 to 1601 are done).
   - `grep -cF "async def setup_action(apartment_id: int, request: Request):" App/app/routes/onboarding_wizard.py | tail -1` prints `1`.
   - `grep -cF "def automation_choice_error(form) -> Optional[str]:" App/app/routes/admin.py | tail -1` prints `1`, and the same for `"def _automation_timing_values(form) -> Dict[str, Any]:"`.
   - `grep -cF "def create_demo_stay(apartment_id: int) -> int:" App/app/demo.py | tail -1` prints `1`.
   - `grep -cE "^func (formStr|pyInt|stamp|serverError)\(" go/internal/web/onboarding/routes.go | tail -1` prints `4`, and `grep -c "^const auditSQL = " go/internal/web/onboarding/routes.go | tail -1` prints `1`.
   - `grep -cE "^func (Mark|SetHidden|Load|Finish|PoolSettings)\(" go/internal/web/onboarding/setup.go | tail -1` prints `5`, and `grep -cE "^var (Skippable|Teaching) = " go/internal/web/onboarding/setup.go | tail -1` prints `2`.
   - `ls go/internal/web/onboarding/wizard_post.go 2>&1 | tail -1` says "No such file".
   - `find docs/tasks/1602-files -name '*.txt' | wc -l | tail -1` prints `7`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1602-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -10
   f04b710b0ee52ceac890b348eb1b3623c4ebc65475ab0c4502a67d7b365918be  App/scripts/onboarding_wizard_golden_post.py
   1990d6591e50920f780f4d913fce03ec0264fe6ae958e7df9f1f13eda2ec9953  App/tests/test_go_onboarding_wizard_post.py
   7c7c3d7fc883c09a536fe982a3c07d04da105a0d3a91d606426e45bcfd980a3e  go/cmd/ubyhost-web/register_web_onboarding_wizard_post_test.go
   33c8d666ae6065b49b43390ed6bffc60692cb4ca630037fe6cd4d4fc210171e7  go/internal/web/onboarding/testdata/wizard_golden_post.json
   b3e94c5491f509aff76998f8cb5e9826858b3b995add6f1035e93a60738376ca  go/internal/web/onboarding/wizard_post.go
   9b3c502098965a31163733a02dd88b0836445edc5d22d8d6ee873595d9e9c51e  go/internal/web/onboarding/wizard_post_golden_test.go
   2e42a194f5432089cc2d53592c402e29102c3fdde0ea1672d50b54a260a6e7f6  go/internal/web/onboarding/wizard_post_test.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1602 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/onboarding cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/onboarding/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8).

3. PostgreSQL: exactly step 3 of brief 1599 (port 55599, data dir `/var/tmp/pg55599`); skip the start if `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55599/data status' | tail -1` says `server is running`. No PostgreSQL 16 binaries: write "CI only" in the report and STOP before step 4.

4. Run the Go tests on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55599/postgres go test ./internal/web/onboarding/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: two `ok` lines. Then show that the whole wizard series ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55599/postgres go test ./internal/web/onboarding/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestWizardEntryMatchesPython$|^TestWizardSlugIsCreatedOnce$|^TestWizardLockAllowed$|^TestWizardOperatorFirstName$|^TestWizardDateFilters$|^TestWizardStepWithoutPageIs501$|^TestWizardTemplatesUseKnownKeys$|^TestWizardRoutesRegistered$|^TestWizardPagesMatchesPython$|^TestWizardDoorWindow$|^TestWizardOperatorSelected$|^TestWizardFinishMatchesPython$|^TestWizardReadyCardQR$|^TestWizardFinishHelpers$|^TestWizardPostMatchesPython$|^TestWizardSkipWithDemoStayIs501$|^TestWizardAutomationTiming$|^TestWizardPostRouteRegistered$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of the 18 tests of briefs 1599 to 1602 and two final `ok` lines; no `--- SKIP`, no `--- FAIL`. The four new ones of this brief:

   --- PASS: TestWizardPostMatchesPython (0.NNs)
   --- PASS: TestWizardSkipWithDemoStayIs501 (0.NNs)
   --- PASS: TestWizardAutomationTiming (0.NNs)
   --- PASS: TestWizardPostRouteRegistered (0.NNs)

   and the 14 of briefs 1599 to 1601: `TestWizardEntryMatchesPython`, `TestWizardSlugIsCreatedOnce`, `TestWizardLockAllowed`, `TestWizardOperatorFirstName`, `TestWizardDateFilters`, `TestWizardStepWithoutPageIs501`, `TestWizardTemplatesUseKnownKeys`, `TestWizardRoutesRegistered`, `TestWizardPagesMatchesPython`, `TestWizardDoorWindow`, `TestWizardOperatorSelected`, `TestWizardFinishMatchesPython`, `TestWizardReadyCardQR`, `TestWizardFinishHelpers`.

5. Run the Python side (one call, from `App/`; no `App/.venv`: write "CI only" and go on):

   ```bash
   cd App && .venv/bin/python -m pytest tests/test_go_onboarding_wizard.py tests/test_go_onboarding_wizard_pages.py tests/test_go_onboarding_wizard_finish.py tests/test_go_onboarding_wizard_post.py tests/test_go_host_i18n.py -q --tb=short -x 2>&1 | tail -5
   ```

   Expected: `6 passed`, no skip.

6. Write the report (§9), set `Status: review` in this file and commit "1602 step 6". Do not open a PR.

## 5. Do not touch

`App/app/`, `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, every file of briefs 1599 to 1601 and every other file under `go/`, `go/go.mod`. No secret or guest datum in a file or a log; nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 2, 4 and 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5`.

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 7 files.
- [ ] The format, build and vet step printed nothing.
- [ ] Step 4 printed `ok` for both packages and each of the 18 named tests printed `--- PASS` (none `SKIP`, none `FAIL`).
- [ ] Step 5 printed `6 passed` (or "CI only" is written in the report).
- [ ] `git show --stat --format=%s $(git log --format=%h --grep='^1602 step') | tail -40` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or `App/app/` file changed; nothing was pushed to `main`.
- [ ] UI: the UX gate of rule 10 is **pending** for the wizard pages (see Owner steps).

**Verified by the brief writer:** in a throwaway copy of go-wave3 (an archive of this branch, so none of the writer's untracked files) with the steps of briefs 1599, 1600, 1601 and 1602 applied exactly and in order (`sha256sum -c` all OK), `gofmt -l` printed nothing, build and vet were silent, step 4 passed on PostgreSQL 16 (port 55599) with the 18 named tests `--- PASS` and 0 SKIP, and step 5 printed `6 passed`.

## 8. Stop and ask

Stop, and write the report, if: an anchor, a hash or a file count is not as stated; a test fails twice (fix nothing in the sidecars: report); you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency or a file outside §3 seems needed; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1602-report.md` (600 tokens at most) and set this brief's `Status: review`: the files changed, each command with the last 5 lines of its output, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`wizard_post.go`: the guard order (CSRF before the id, as the router dependency); the owner scope of `wizardLoadApt`; the guide check before any mark (`wizardSetupActions`); `wizardAutomationChoiceError` and `wizardAutomationTiming` against `admin.py` 1721-1745; the UPDATE touches only `automation_mode` and `submit_after_hours` of that one property; the demo stay insert (`source 'demo'`, one night from Prague's today, one guest); the 501 branch writes nothing.

## Owner steps

The wizard runs on Python until you switch it. Wait for brief 1603 first (blocked: without it, "Delete and continue" on the try-it page answers 501). When 1603 is merged:

1. Deploy to staging. Ask the orchestrator to run the UX gate of rule 10 on staging for the six wizard pages (calendar, guest link, police, property, finish, try-it): `test_layout_lint_browser.py`, the 390, 768 and 1280 px screenshots, a line per page in the PR.
2. On staging, add `/apartments/*/setup /apartments/*/setup/*` to `UBYHOST_GO_PATHS` in `.env` (keep the double quotes and the other paths), then run `deploy.sh`.
3. On staging, open a new property's wizard, go through every step, hide and resume it, run the try-it demo and delete it. Every page must look like the Python one.
4. Only then add the same two paths on production and deploy. To undo, remove them and deploy again.
