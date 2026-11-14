# 1601: Go setup wizard, part 3: the finish page and the try-it page

Status: todo
Tier: A
Depends on: 1600 (and through it 1599; their files must be on the branch) | Base commit: current tip of the working branch | Branch: task/1601-go-setup-wizard-finish-try-it
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1601 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1601 step'` and `git show --stat <commit>`, never a fixed base commit.

## 1. Objective

Add the Go pages of the last two wizard views to `go/internal/web/onboarding`: the finish page `GET /apartments/{id}/setup/done` (`setup_wizard/done.html` with `_setup_ready_card.html` and `_workflow.html`'s `workflow_strip(apartment, heading=false)`) and the rehearsal page `GET /apartments/{id}/setup/try_it` (`setup_wizard/try_it.html`). After brief 1599 they answered 501. With this brief every page of the wizard renders in Go. Dormant: no path is routed.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (the try-it page shows a demo stay, which is never reported; nothing here files or saves police data); 2 privacy: no new personal-data field, no new retention line, no outbound request (the QR image is made in-process by the existing `payments.QRDataURI`); 3 fixtures are made up; 4 no new dependency; 5 no new SQL (the data comes from the 1599 context: the checklist, the next stay window, the demo stay and its guest progress); 6 light mode; the page works without JavaScript (the demo button opens a new tab; a `<noscript>` link reloads); 11 Go first. **Go-first exception used:** exception 1 (port plumbing): `App/scripts/onboarding_wizard_golden_finish.py` and `App/tests/test_go_onboarding_wizard_finish.py`. No file under `App/app/` changes.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. Like Python, the first finish page of a property records that the celebration was shown (`property_setup:<id>` setting, written by the 1599 context).

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1601-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `f337b946e52608f271c0dcdd83465d6b174b49db09264243e817e9872564aab8` | `App/scripts/onboarding_wizard_golden_finish.py` | create | 45 |
| `35c1957173fbc76985ee4603a30a3d0546dab2bf4becb97a941b6c70c5964cf3` | `App/tests/test_go_onboarding_wizard_finish.py` | create | 16 |
| `d03321b984cf48134a88832e9dd3d3288f194ae215a96f2ae71a07b124103339` | `go/internal/web/onboarding/testdata/wizard_golden_finish.json` | create | 1405 |
| `ec279ef590b4d1321e691c2b1353d6b2f6df18ffeecd09f05e71555f911ef3ac` | `go/internal/web/onboarding/wizard_finish.go` | create | 71 |
| `99daf8ae253bdf9a1113837476ca92036ac2bedf220e40ffa8ac84ea5918697b` | `go/internal/web/onboarding/wizard_finish_golden_test.go` | create | 8 |
| `1c89ef6bf3d6f7793baee1d24d1a9b71e2d669f362e1f32e6d956715cd33d51d` | `go/internal/web/onboarding/wizard_more_test.go` | create | 77 |
| `c9e856e477975594beca6c338dea4384d936a62b4c3023d988284864ec889bd3` | `go/internal/web/onboarding/wizardtemplates/done.tmpl` | create | 108 |
| `04dde879fd72372f8ddd648fa72045e42976de0d291a07e66d6a92d190390f4e` | `go/internal/web/onboarding/wizardtemplates/try_it.tmpl` | create | 92 |

**How the code is built (for the reviewer; the executor reads no Go file).** As in 1600, the two template files are picked up by the 1599 page sets; no earlier file changes. `wizard_finish.go` adds the inline Jinja logic as page-data methods: `MissingRow` (the first checklist row that is waiting or todo), `SummaryStatus` and `SummaryIcon` (the badge and icon maps of `done.html`), `ReadyQRURL` (the QR data URI as a `template.URL`, so html/template keeps the `data:` scheme; it writes `+` as `&#43;`, which the browser reads back), `OperatorMark` (`lstrip('[')[:1]`), `RehearsalHours` (`submit_after_hours or 24`) and `DemoMessage` (the guest message split at the link, as `str.split`). The demo state (`none`, `open`, `registered`: at least one complete guest) and the finish data come from the 1599 context.

**Parity notes:** the golden (`testdata/wizard_golden_finish.json`, 17 cases on the 1599 seed, in order) covers the finish page: ready (tested, report complete) with the QR card and the confetti on the first visit and without it on the second (Czech), all set without a test, the police login waiting (partial banner, fix button), a guide still open (Vietnamese), ready after the celebration with a demo stay, a legacy property, signed out and another host's; the try-it page: no demo stay, an open demo stay (also Vietnamese), a registered one (the rehearsal list with "scheduled, 12 h", also Czech), immediate mode with a company signatory, a legacy property and another host's. The golden runner replaces the QR image by one token (the PNG encoders differ); `TestWizardReadyCardQR` checks that the Go page carries a real PNG.

**Known differences from Python:** those of brief 1599. **Paths that become fully served by Go:** none yet (the POST is brief 1602). **Assumption:** as in 1599.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/onboarding_wizard_golden_finish.py` | create | golden writer, part "finish" |
| `App/tests/test_go_onboarding_wizard_finish.py` | create | the committed golden matches the Python routes |
| `go/internal/web/onboarding/testdata/wizard_golden_finish.json` | create | golden |
| `go/internal/web/onboarding/wizard_finish.go` | create | page data of the two pages |
| `go/internal/web/onboarding/wizard_finish_golden_test.go` | create | `TestWizardFinishMatchesPython` |
| `go/internal/web/onboarding/wizard_more_test.go` | create | QR test and unit tests |
| `go/internal/web/onboarding/wizardtemplates/done.tmpl`, `try_it.tmpl` | create | Go twins of the templates |
| `docs/tasks/1601-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1601-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `ls go/internal/web/onboarding/wizard_pages.go go/internal/web/onboarding/wizardtemplates/police.tmpl go/internal/web/onboarding/wizard_step.go 2>&1 | tail -3` lists all three (briefs 1599 and 1600 are done).
   - `grep -cF '{% include "_setup_ready_card.html" %}' App/app/templates/setup_wizard/done.html | tail -1` prints `1`.
   - `grep -cF 'id="setup-create-demo"' App/app/templates/setup_wizard/try_it.html | tail -1` prints `1`.
   - `grep -rlF "func QRDataURI(" go/internal/payments | wc -l | tail -1` prints `1` (the QR helper the 1599 context calls exists).
   - `ls go/internal/web/onboarding/wizard_finish.go 2>&1 | tail -1` says "No such file".
   - `find docs/tasks/1601-files -name '*.txt' | wc -l | tail -1` prints `8`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1601-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -10
   f337b946e52608f271c0dcdd83465d6b174b49db09264243e817e9872564aab8  App/scripts/onboarding_wizard_golden_finish.py
   35c1957173fbc76985ee4603a30a3d0546dab2bf4becb97a941b6c70c5964cf3  App/tests/test_go_onboarding_wizard_finish.py
   d03321b984cf48134a88832e9dd3d3288f194ae215a96f2ae71a07b124103339  go/internal/web/onboarding/testdata/wizard_golden_finish.json
   ec279ef590b4d1321e691c2b1353d6b2f6df18ffeecd09f05e71555f911ef3ac  go/internal/web/onboarding/wizard_finish.go
   99daf8ae253bdf9a1113837476ca92036ac2bedf220e40ffa8ac84ea5918697b  go/internal/web/onboarding/wizard_finish_golden_test.go
   1c89ef6bf3d6f7793baee1d24d1a9b71e2d669f362e1f32e6d956715cd33d51d  go/internal/web/onboarding/wizard_more_test.go
   c9e856e477975594beca6c338dea4384d936a62b4c3023d988284864ec889bd3  go/internal/web/onboarding/wizardtemplates/done.tmpl
   04dde879fd72372f8ddd648fa72045e42976de0d291a07e66d6a92d190390f4e  go/internal/web/onboarding/wizardtemplates/try_it.tmpl
   EOF
   ```

   Every line must end with `: OK`. Then commit "1601 step 1".

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
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55599/postgres go test ./internal/web/onboarding/ -count=1 -v -run '^TestWizardFinishMatchesPython$|^TestWizardReadyCardQR$|^TestWizardFinishHelpers$|^TestWizardPagesMatchesPython$|^TestWizardEntryMatchesPython$|^TestWizardTemplatesUseKnownKeys$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of the 6 tests and a final `ok`; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestWizardFinishMatchesPython (0.NNs)
   --- PASS: TestWizardEntryMatchesPython (0.NNs)
   --- PASS: TestWizardReadyCardQR (0.NNs)
   --- PASS: TestWizardFinishHelpers (0.NNs)
   --- PASS: TestWizardPagesMatchesPython (0.NNs)
   --- PASS: TestWizardTemplatesUseKnownKeys (0.NNs)

5. Run the Python side (one call, from `App/`; no `App/.venv`: write "CI only" and go on):

   ```bash
   cd App && .venv/bin/python -m pytest tests/test_go_onboarding_wizard.py tests/test_go_onboarding_wizard_pages.py tests/test_go_onboarding_wizard_finish.py tests/test_go_host_i18n.py -q --tb=short -x 2>&1 | tail -5
   ```

   Expected: `5 passed`, no skip.

6. Write the report (§9), set `Status: review` in this file and commit "1601 step 6". Do not open a PR.

## 5. Do not touch

`App/app/`, `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, every file of briefs 1599 and 1600 and every other file under `go/`, `go/go.mod`. No secret or guest datum in a file or a log; nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 2, 4 and 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5`.

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 8 files.
- [ ] The format, build and vet step printed nothing.
- [ ] Step 4 printed `ok` for both packages, and each of the 6 named tests printed `--- PASS` (none `SKIP`, none `FAIL`).
- [ ] Step 5 printed `5 passed` (or "CI only" is written in the report).
- [ ] `git show --stat --format=%s $(git log --format=%h --grep='^1601 step') | tail -40` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or `App/app/` file changed; nothing was pushed to `main`.
- [ ] UI: the UX gate of rule 10 is **pending** for both pages (dormant; it runs on staging before the owner adds the paths, brief 1602 Owner steps).

**Verified by the brief writer:** in a throwaway copy of go-wave3 (an archive of this branch, so none of the writer's untracked files) with the steps of briefs 1599, 1600 and 1601 applied exactly and in order (`sha256sum -c` all OK), `gofmt -l` printed nothing, build and vet were silent, step 4 passed on PostgreSQL 16 (port 55599) with the 6 named tests `--- PASS` and 0 SKIP, and step 5 printed `5 passed`.

## 8. Stop and ask

Stop, and write the report, if: an anchor, a hash or a file count is not as stated; a test fails twice (fix nothing in the sidecars: report); you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency or a file outside §3 seems needed; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1601-report.md` (600 tokens at most) and set this brief's `Status: review`: the files changed, each command with the last 5 lines of its output, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`wizardtemplates/try_it.tmpl` (the three demo states and their forms: every POST form has `_csrf`; the demo form keeps Python's duplicate `action=demo` field), `wizardtemplates/done.tmpl` (the ready card only when `wizard_ready` and nothing is missing; the finish note order), `wizard_finish.go` (`ReadyQRURL` trusts only the in-process QR data URI).

## Owner steps

None: nothing is switched on. The path switch is in the owner steps of brief 1602.
