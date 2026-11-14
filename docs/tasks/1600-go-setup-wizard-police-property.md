# 1600: Go setup wizard, part 2: the police and property step pages

Status: todo
Tier: A
Depends on: 1599 (its files must be on the branch: `go/internal/web/onboarding/wizard*.go`, `wizardtemplates/_frame.tmpl`, `App/scripts/onboarding_wizard_golden.py`) | Base commit: current tip of the working branch | Branch: task/1600-go-setup-wizard-police-property
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1600 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1600 step'` and `git show --stat <commit>`, never a fixed base commit.

## 1. Objective

Add the Go pages of two setup wizard steps to `go/internal/web/onboarding`: `GET /apartments/{id}/setup/police` (`setup_wizard/police.html` with `_police_fields.html` and `_police_letter_figure.html`) and `GET /apartments/{id}/setup/property` (`setup_wizard/property.html` with `_workflow.html`, `_property_identity_fields.html`, `_door_code_window.html`, `_property_operator.html`, `_property_address_fields.html`, `_ruian_suggest.html`). After brief 1599 these steps answered 501; after this brief they render as Python does. Both pages are forms that post to Python routes that stay Python (`POST /apartments/{id}`, `/test-connection`, `/police-letter`, `/entities`); only the police page's Wait button posts to the wizard route of brief 1602. Dormant: no path is routed.

## 2. Context

Rules (AGENTS.md): 1 filing correctness: the police page shows the stored UbyPort settings (IDUB, login, facility mark and name, contact) and whether a password is stored, never the password; the field names, `maxlength` values, hidden fields and form targets are the Python ones, pinned by the golden, so the Python save route receives exactly what it receives today (`docs/UBYPORT_CORE.md`, "Guest data → UbyPort mapping"); 2 privacy: no new personal-data field, no new retention line, no outbound request (the address suggestions script is the existing first-party `/static/ruian_suggest.js`); 3 fixtures are made up; 4 no new dependency; 5 no SQL in this brief (the pages read the context of 1599); 6 light mode, both forms work without JavaScript; 11 Go first. **Go-first exception used:** exception 1 (port plumbing): `App/scripts/onboarding_wizard_golden_pages.py` writes the golden from the live Python routes and `App/tests/test_go_onboarding_wizard_pages.py` checks it. No file under `App/app/` changes.

**PR text (hard rule 2):** no new outbound request and no new personal-data field; filing behaviour is unchanged (read-only pages; the forms post to the existing Python routes with the same fields).

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1600-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `e1d89861bde41918c861a3977f89513b749b440178647c671a806aead64c7c7f` | `App/scripts/onboarding_wizard_golden_pages.py` | create | 36 |
| `47cf595cd2c6c2955ae3bae30e64d3150c63a4231b735024f8299782684ee1c9` | `App/tests/test_go_onboarding_wizard_pages.py` | create | 16 |
| `d3d2c69a7129924ef61edff37a1c9c65cc8d8cb18c4a0ef02ea381d2b462fc0b` | `go/internal/web/onboarding/testdata/wizard_golden_pages.json` | create | 1375 |
| `db4e18c77e50943c91776acf88f740062324757db8fe18d2ace90dd61cfa9ebe` | `go/internal/web/onboarding/wizard_pages.go` | create | 166 |
| `e331afe05832bea266932bd72555cf336585d30f9114d0b93ef628b69d8d2373` | `go/internal/web/onboarding/wizard_pages_golden_test.go` | create | 8 |
| `f497342f233db0a7bb35ae25caf08decab85fa7340d7d56acfca4f0d24e9d061` | `go/internal/web/onboarding/wizard_pages_test.go` | create | 52 |
| `ebd7edeced1798711a49be4849fbe31455c28ef05e0ed95e48dcceb2a0bd6277` | `go/internal/web/onboarding/wizardtemplates/police.tmpl` | create | 127 |
| `7f12d777b6dd60930b5a4502581e3017e8b7ae50d0d8669c322b31f9cd0b263d` | `go/internal/web/onboarding/wizardtemplates/property.tmpl` | create | 113 |

**How the code is built (for the reviewer; the executor reads no Go file).** Brief 1599 parses one template set per file in `wizardtemplates/` (the shared `_*.tmpl` plus the page), so adding `police.tmpl` and `property.tmpl` is all it takes for the step route to render them; no 1599 file changes. `wizard_pages.go` holds what the Jinja templates compute inline, as methods of the page data: `FacilityHelp` (the facility name hint with its example line, markup as the Jinja `set` block is), `AutoMode` (the stored mode, manual when it is none of the three), `HoursField` (the scheduled card's hours box), `WaitHelpKey` (reads the stored mode, not the draft, as Python's `apartment.automation_mode`), `GenericWorkflow` (`workflow_steps(None)`), `HourSelects` (stored hour else 15 and 10), `DoorWindow` (Python's `%` for the hour before check-in and after check-out), `OperatorSelected` (the stored operator if it is the host's, else the only one, else none) and `AddressRows`. The letter helpers start open and empty: `letter_status`, `letter_prefill`, `letter_saved`, `police_errors`, `address_errors`, `name_error` and the property `draft` are set only by Python POST re-renders, which stay Python. The door-code window shows when the lock is allowed for the owner (`ttlock.allowed_for`, the `LockAvailable` of 1599); the lock list of `_door_code_context` is not read by these pages.

**Parity notes:** the golden (`testdata/wizard_golden_pages.json`, 15 cases on the 1599 seed) covers the police page on the guide's step with nothing filled and no password, filled with a password, scheduled (6 h) while waiting, immediate in Czech and scheduled (12 h) in Vietnamese, a police page ahead of the guide (redirect) and signed out; the property page of a new property (two operators, none chosen, default hours, no window), an operator chosen, a finished property, an escaped name (`Iota <b>`) in Czech, one operator chosen for the host with the hours 0 and 23 (window 23:00 the day before, 00:00 the day after), a host without a business (the register lookup form, Vietnamese), a step not allowed (redirect) and another host's property.

**Known differences from Python:** those of brief 1599. **Paths that become fully served by Go:** none yet (brief 1602 adds the POST). **Assumption:** as in 1599, no `/apartments` path is in `UBYHOST_GO_PATHS`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/onboarding_wizard_golden_pages.py` | create | golden writer, part "pages" |
| `App/tests/test_go_onboarding_wizard_pages.py` | create | the committed golden matches the Python routes |
| `go/internal/web/onboarding/testdata/wizard_golden_pages.json` | create | golden |
| `go/internal/web/onboarding/wizard_pages.go` | create | page data of the two steps |
| `go/internal/web/onboarding/wizard_pages_golden_test.go` | create | `TestWizardPagesMatchesPython` |
| `go/internal/web/onboarding/wizard_pages_test.go` | create | unit tests |
| `go/internal/web/onboarding/wizardtemplates/police.tmpl`, `property.tmpl` | create | Go twins of the templates |
| `docs/tasks/1600-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1600-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `git log --oneline --grep='^1599 step' | wc -l | tail -1` prints a number of at least `2`, and `ls go/internal/web/onboarding/wizard_step.go go/internal/web/onboarding/wizardtemplates/_frame.tmpl App/scripts/onboarding_wizard_golden.py 2>&1 | tail -3` lists all three (brief 1599 is done).
   - `grep -cF '<form method="post" action="/apartments/{{ apartment.id }}" class="setup-wizard-form" id="police-form">' App/app/templates/setup_wizard/police.html | tail -1` prints `1`.
   - `grep -cF '{% include "_property_address_fields.html" %}' App/app/templates/setup_wizard/property.html | tail -1` prints `1`.
   - `ls go/internal/web/onboarding/wizard_pages.go 2>&1 | tail -1` says "No such file".
   - `find docs/tasks/1600-files -name '*.txt' | wc -l | tail -1` prints `8`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1600-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -10
   e1d89861bde41918c861a3977f89513b749b440178647c671a806aead64c7c7f  App/scripts/onboarding_wizard_golden_pages.py
   47cf595cd2c6c2955ae3bae30e64d3150c63a4231b735024f8299782684ee1c9  App/tests/test_go_onboarding_wizard_pages.py
   d3d2c69a7129924ef61edff37a1c9c65cc8d8cb18c4a0ef02ea381d2b462fc0b  go/internal/web/onboarding/testdata/wizard_golden_pages.json
   db4e18c77e50943c91776acf88f740062324757db8fe18d2ace90dd61cfa9ebe  go/internal/web/onboarding/wizard_pages.go
   e331afe05832bea266932bd72555cf336585d30f9114d0b93ef628b69d8d2373  go/internal/web/onboarding/wizard_pages_golden_test.go
   f497342f233db0a7bb35ae25caf08decab85fa7340d7d56acfca4f0d24e9d061  go/internal/web/onboarding/wizard_pages_test.go
   ebd7edeced1798711a49be4849fbe31455c28ef05e0ed95e48dcceb2a0bd6277  go/internal/web/onboarding/wizardtemplates/police.tmpl
   7f12d777b6dd60930b5a4502581e3017e8b7ae50d0d8669c322b31f9cd0b263d  go/internal/web/onboarding/wizardtemplates/property.tmpl
   EOF
   ```

   Every line must end with `: OK`. Then commit "1600 step 1".

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

   Expected: two `ok` lines. Then:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55599/postgres go test ./internal/web/onboarding/ -count=1 -v -run '^TestWizardPagesMatchesPython$|^TestWizardDoorWindow$|^TestWizardOperatorSelected$|^TestWizardEntryMatchesPython$|^TestWizardTemplatesUseKnownKeys$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of the 5 tests and a final `ok`; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestWizardEntryMatchesPython (0.NNs)
   --- PASS: TestWizardPagesMatchesPython (0.NNs)
   --- PASS: TestWizardDoorWindow (0.NNs)
   --- PASS: TestWizardOperatorSelected (0.NNs)
   --- PASS: TestWizardTemplatesUseKnownKeys (0.NNs)

5. Run the Python side (one call, from `App/`; no `App/.venv`: write "CI only" and go on):

   ```bash
   cd App && .venv/bin/python -m pytest tests/test_go_onboarding_wizard.py tests/test_go_onboarding_wizard_pages.py tests/test_go_host_i18n.py -q --tb=short -x 2>&1 | tail -5
   ```

   Expected: `4 passed`, no skip.

6. Write the report (§9), set `Status: review` in this file and commit "1600 step 6". Do not open a PR.

## 5. Do not touch

`App/app/`, `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, every file of brief 1599 and every other file under `go/` (in this package `setup.go`, `routes.go` and their tests belong to the parallel series), `go/go.mod`. No secret or guest datum in a file or a log; nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 2, 4 and 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5`.

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 8 files.
- [ ] The format, build and vet step printed nothing.
- [ ] Step 4 printed `ok` for both packages, and each of the 5 named tests printed `--- PASS` (none `SKIP`, none `FAIL`).
- [ ] Step 5 printed `4 passed` (or "CI only" is written in the report).
- [ ] `git show --stat --format=%s $(git log --format=%h --grep='^1600 step') | tail -40` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or `App/app/` file changed; nothing was pushed to `main`.
- [ ] UI: the UX gate of rule 10 is **pending** for both pages (dormant; it runs on staging before the owner adds the paths, brief 1602 Owner steps).

**Verified by the brief writer:** in a throwaway copy of go-wave3 (an archive of this branch, so none of the writer's untracked files) with the steps of briefs 1599 and 1600 applied exactly and in order (`sha256sum -c` all OK), `gofmt -l` printed nothing, build and vet were silent, step 4 passed on PostgreSQL 16 (port 55599) with the 5 named tests `--- PASS` and 0 SKIP, and step 5 printed `4 passed`.

## 8. Stop and ask

Stop, and write the report, if: an anchor, a hash or a file count is not as stated; a test fails twice (fix nothing in the sidecars: report); you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency or a file outside §3 seems needed; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1600-report.md` (600 tokens at most) and set this brief's `Status: review`: the files changed, each command with the last 5 lines of its output, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`wizardtemplates/police.tmpl` (field names, `maxlength`, hidden fields and the three form targets against `police.html` and `_police_fields.html`; the password input never carries a value), `wizardtemplates/property.tmpl` (the operator select and the hint link), `wizard_pages.go` (`FacilityHelp` is the only markup built in Go; every translated part is escaped). The golden compares the whole `setup-wizard` fragment of each page.

## Owner steps

None: nothing is switched on. The path switch is in the owner steps of brief 1602.
