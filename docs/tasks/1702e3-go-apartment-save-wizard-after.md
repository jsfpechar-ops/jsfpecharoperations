# 1702e3: Go property settings 3e3: after a wizard save (_setup_after_save)

Status: done (executed 2026-11-17; orchestrator verified sidecars == repo, Go tests green on PG16, 0 skips). Was: review (exact-diff pass 2026-11-17: sidecars applied to a clean worktree of 1ee6306 (1702e2 step 1, i.e. the 1702e2 sidecars), gofmt/build/vet clean, Go tests green on PostgreSQL 16, 0 skips; no catalog, template or Python change)
Decision 2026-11-17 (owner/orchestrator, rule 11): the wizard saves are ported to Go. Owner decision: Go-only tests with hand-written expected output, no new Python test file, no golden script change.
Depends on: 1702e2 (step 1 applied; its step 7 report may still be open) | Base commit: current tip of the working branch | Branch: task/1702e3-go-apartment-save-wizard-after
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (this brief needs about 10)
Tier: A (fresh review of the full diff before merge, see the risk list at the end)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1702e3 step k` (`k` is the step number) and `git add` only the paths the step names (never `-A`, never `.`). Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1702e3 step'`.

## 1. Objective

Replace the 1702e2 seam in `apartmentWizardSave` (`notPorted` "a wizard save that goes back into the setup wizard (brief 1702e3)") with `_setup_after_save` (`App/app/routes/admin.py` 2655-2737), called where Python calls it (2576: after the fee return, before `?saved=1`): a validated `return_to` under `/apartments/{id}/setup/` decides where a written property or police wizard save goes.

## 2. Context

Rules (AGENTS.md): 1 filing correctness: no filing code changes; the police write is 1702e2's owner-scoped `writeApartmentSave`, unchanged; 2 privacy: no new field, no outbound request; 4 no new dependency; 5 every read owner-scoped (`AfterSave` loads the property with `wizardLoadApt`, `owner_user_id IS NOT DISTINCT FROM` the workspace); the only writes are the `property_setup:<id>` setting through the existing `onboarding.Mark`/`Finish`; 6/9 no new copy and no catalog change: the keys are `flash.apartments.saved` (apartmentupdate catalog), `flash.setup.complete` and `wizard.step.<step>` (wizardtext catalog), all already in the Go catalogs; 7/10 UX gate: **pending until 1705** (route dormant, not in `UBYHOST_GO_PATHS`; the 200 notice uses the existing `_frame.tmpl` notice line of 1702e1); 8 dormant; 11 Go. CSRF: unchanged, the handler is the existing `POST /apartments/{id}` behind `enter`.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1702e3-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Four files are replaced (step 0 checks their current hashes: three are the 1702e2 sidecars, `wizard_data.go` is unchanged since 1702e1), two are created.

| sha256 after | file | action | lines |
|---|---|---|---|
| `ebf3c17314e3da9774d714fd0e146d34d22bd2a3fb969e8d11c1874b9a2758cd` | `go/internal/web/properties/apartment_update.go` | replace | 892 |
| `fbff2295b373f1f40a4ad4fd0e8cbac11f3d5745da6bcead586309d9bcf04ea0` | `go/internal/web/properties/apartment_update_test.go` | replace | 581 |
| `c0f6c93b063d02b271da0c2222e2b3d0ee4ae8abbfe06fa7a4e8dc7600a83a1f` | `go/internal/web/properties/apartment_update_wizard.go` | replace | 309 |
| `31c8db05805335f93f8bf702cd362ca5aea618598202ddfca40bd666d73454f8` | `go/internal/web/onboarding/wizard_data.go` | replace | 580 |
| `c1b307bd7dd8cb1898d1a6df47cbcbea16d37e2ca434d8956088b14eb6adfc91` | `go/internal/web/onboarding/wizard_after_save.go` | create | 100 |
| `d68f2a8d526ca7d3e813213cc4cc3129c6377de5c61ca241f21dcc8c370ff402` | `go/internal/web/properties/apartment_update_wizard_after_test.go` | create | 156 |

**What changed (for the reviewer; the executor reads no Go file).**

- `wizard_data.go`: the facts/state/guide half of `wizardContext` moved unchanged into `wizardBundle` (admin `_setup_guide_bundle`: feed count, stays, guests, `report_complete`, `lock_available`, `_setup_state` with its legacy finish, `current`). `wizardContext` calls it; the PIN backfill, link key, entities and `CelebrateOnce` stay in `wizardContext` only (Python's `_setup_after_save` does none of them). No behaviour change; the wizard golden tests stay green.
- `wizard_after_save.go` (new, onboarding): `AfterSave` in Python's order: stored guide finished or hidden -> `back`; step not in `Steps` -> `back`; owner-scoped load (gone -> `""`, Python's `None`); `wizardBundle`; police with `automation_mode` posted marks `automation` done; property marks done when `PropertyDetailsComplete`, police when `ReportComplete`; state reloaded (or `LegacyState`); `return_to` path (before `?`, trailing `/` stripped) ending `/done`: `WizardUnresolved` -> `guide` to `Current(...).URL` (else `/setup/police`), resolved -> `Finish` and `done` with `flash.setup.complete`; else `StepStatus` not done/skipped/not_needed -> `notice` with `wizard.step.<step>`; else `back`. Not ported (dead in Python, the steps are not in `STEPS`): the stay_fee/door_lock/automation marks, `step == "automation"` in the `/done` test, the `door_lock` notice.
- `apartment_update.go`: `apartmentSaved` computes the validated `return_to` once (`formReturnTo`, as before) and, when it starts with `/apartments/{id}/setup/`, calls `apartmentAfterWizardSave` before the `?saved=1` path (and before the letter test, as Python). `apartmentUpdateNotPorted` messages lose "(brief 1702e3)"; the two cases stay `notPorted`: a non-property/police `setup_step`, and a save **without** `setup_step` whose `return_to` is in the wizard (decision of this pass: `refuse_fee_save` draws the retired `stay_fee` wizard page, which has no Go template; keep it in Python). Header comment updated.
- `apartment_update_wizard.go`: the seam is removed (the write now always follows the checks); new `apartmentAfterWizardSave` maps the result: `back` -> `return_to` with the saved message (`flash.apartments.saved`/`saved_ready`, already computed by `apartmentSaved`), `guide` -> URL without message, `done` -> URL with `flash.setup.complete`, `notice` -> `RenderSetupPage` status 200 with `flash.apartments.saved` naming the missing police labels (`_missing_report_labels`, the labels `apartmentSaved` built) or else the step label; `""` -> the caller goes on.
- `apartment_update_test.go`: `TestApartmentUpdateNotPorted` drops the two "step, to wizard" cases (they now save; gofmt realigned the map).
- `apartment_update_wizard_after_test.go` (new) `TestApartmentUpdateWizardAfter`, hand-written on the golden seed: property saved and complete -> `return_to` with the "missing: Password" warning toast, guide `{property: done}`, legacy; police without password -> 200 police page with the notice, draft escaped, row written, guide unchanged; `/done` with calendar open -> `/apartments/201/setup/calendar`, no message; police complete with `automation_mode` -> `automation` and `police` done, "ready to report"; `/done/` with every step answered -> finished, `/setup/done?msg=Setup%20complete.&toast_kind=success`; finished guide -> plain back even with a blank IDUB, guide unchanged; property 203 with every police field set but no name -> 200 notice "Property details", nothing stored.
- Accepted differences (put in the report): a save without `setup_step` whose `return_to` is in the wizard stays `notPorted` (no current wizard form posts it; Python draws the retired fee page on its refusal); until 1705 the route is dormant.

## 3. Files

| Path | Action |
|---|---|
| the six files of the table above | replace (4) / create (2) |
| `docs/tasks/1702e3-files/**` | keep (sidecars, committed with this brief; do not edit) |
| `docs/tasks/1702e3-report.md` | create (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `git log --oneline --grep='^1702e2 step 1$' | wc -l | tail -1` prints `1`.
   - `find docs/tasks/1702e3-files -name '*.txt' | wc -l | tail -1` prints `6`.
   - `ls go/internal/web/onboarding/wizard_after_save.go go/internal/web/properties/apartment_update_wizard_after_test.go 2>&1 | grep -c 'No such file' | tail -1` prints `2`.
   - The four replaced files are exactly the ones the sidecars were built on (one call):

     ```bash
     sha256sum -c - <<'EOF0' 2>&1 | tail -5
     b6b4f55ec48e91eb55cf01df272cf9194e81acd4a73cc1350b377e0f4c9cc77d  go/internal/web/properties/apartment_update.go
     b1713929dca66f69d4f764833e63fd84fb23dc0beeecaf920d0b3485a6c90e04  go/internal/web/properties/apartment_update_test.go
     89c1d9c3b852bac1877b515e200a2aa6bdb6aad37bd4f331c9aa83a8b08a4673  go/internal/web/properties/apartment_update_wizard.go
     9811c14af3ac5907c61ef883ae8d623b28e952fdfa91c690c65d0fedc25505e2  go/internal/web/onboarding/wizard_data.go
     EOF0
     ```

     Four lines ending `: OK`. A `FAILED` line: STOP, the orchestrator re-bases the sidecars.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1702e3-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF1' 2>&1 | tail -7
   ebf3c17314e3da9774d714fd0e146d34d22bd2a3fb969e8d11c1874b9a2758cd  go/internal/web/properties/apartment_update.go
   fbff2295b373f1f40a4ad4fd0e8cbac11f3d5745da6bcead586309d9bcf04ea0  go/internal/web/properties/apartment_update_test.go
   c0f6c93b063d02b271da0c2222e2b3d0ee4ae8abbfe06fa7a4e8dc7600a83a1f  go/internal/web/properties/apartment_update_wizard.go
   31c8db05805335f93f8bf702cd362ca5aea618598202ddfca40bd666d73454f8  go/internal/web/onboarding/wizard_data.go
   c1b307bd7dd8cb1898d1a6df47cbcbea16d37e2ca434d8956088b14eb6adfc91  go/internal/web/onboarding/wizard_after_save.go
   d68f2a8d526ca7d3e813213cc4cc3129c6377de5c61ca241f21dcc8c370ff402  go/internal/web/properties/apartment_update_wizard_after_test.go
   EOF1
   ```

   Six lines ending `: OK`. Then commit (one call):

   ```bash
   git add go/internal/web/properties/apartment_update.go go/internal/web/properties/apartment_update_test.go go/internal/web/properties/apartment_update_wizard.go go/internal/web/onboarding/wizard_data.go go/internal/web/onboarding/wizard_after_save.go go/internal/web/properties/apartment_update_wizard_after_test.go && git commit -m "1702e3 step 1" 2>&1 | tail -2
   ```

2. Format, build and vet (one call, repo root):

   ```bash
   cd go && gofmt -l internal/web/properties internal/web/onboarding cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/properties/... ./internal/web/onboarding/... ./cmd/ubyhost-web/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8).

3. Python checks: none. No Python file and no catalog changes; write "Python checks: none (no Python or catalog change)" in the report.

4. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`; skip the start if `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55483/data status' | head -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55483 && chown postgres /var/tmp/pg55483 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55483/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55483/data -o "-p 55483 -k /var/tmp/pg55483" -l /var/tmp/pg55483/log start' 2>&1 | tail -3
   ```

   Expected: `server started`. No PostgreSQL 16 binaries at that path: write "CI only" in the report and STOP before step 5.

5. Go tests on PostgreSQL (one call, repo root):

   ```bash
   cd go && export UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55483/postgres && go test ./internal/web/properties/... ./internal/web/onboarding/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30; go test ./internal/web/properties/ -count=1 -v -run '^TestApartmentUpdate(WizardAfter|Wizard|NotPorted|MatchesPython)$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -8; go test ./internal/web/properties/... ./internal/web/onboarding/... -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1
   ```

   Expected: three `ok` lines; then `--- PASS` for `TestApartmentUpdateMatchesPython`, `TestApartmentUpdateNotPorted`, `TestApartmentUpdateWizard`, `TestApartmentUpdateWizardAfter`, and one `ok`; then `0`. A failure: run once more; a second failure: STOP (§8). Then stop the server if you started it: `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55483/data stop' 2>&1 | tail -2 && rm -rf /var/tmp/pg55483`.

6. UX gate: **pending until 1705.** The route is dormant. Write in the report: "UX: the 200 notice on the property and police steps only appears through the dormant POST /apartments/{id}; the 390/768/1280 screenshots are taken in 1705". Nothing to commit.

7. Write the report (§9), set `Status: review` in this file, and commit (one call): `git add docs/tasks/1702e3-report.md docs/tasks/1702e3-go-apartment-save-wizard-after.md && git commit -m "1702e3 step 7" 2>&1 | tail -2`.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `App/`; every other file under `go/` (no catalog, no template, no filing code in `go/internal/ubyport`); never regenerate a golden JSON.

## 6. Commands

Exactly the commands of §4 (steps 2 and 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about this brief's files).

## 7. Acceptance

- [ ] Step 0: `1`, `6`, `2`, four `: OK`; step 1: six `: OK`.
- [ ] Step 2 printed nothing.
- [ ] Step 5: three `ok` lines, the four named tests `--- PASS`, SKIP count `0`.
- [ ] `git log --oneline --grep='^1702e3 step' | tail -5` lists steps 1 and 7; `git show --stat --format=%s $(git log --format=%h --grep='^1702e3 step') | tail -20` lists only the paths of §3.
- [ ] Nothing in `App/` or `UBYHOST_GO_PATHS` changed.

## 8. Stop and ask

An anchor, hash or count of steps 0-1 not as stated; a test fails twice (fix nothing in the sidecars: report); 25 tool calls or about 50k tokens (report as `blocked`); a file outside §3 needs a change; push, merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/1702e3-report.md` (500 tokens at most): the files (`git show --stat` as in §7); each command with its last 5 lines and the SKIP count; §7 ticked; deviations; the accepted differences of §2; "UX pending until 1705"; "1703 may start; 1705 switches POST /apartments/{id} with the wizard paths".

## Risk list (Tier A review)

- Decision logic: `wizard_after_save.go` 39-100 (`AfterSave`): order of the finished/hidden check, the marks (63-73), the `/done` path test (82-95: `Cut` at `?`, `TrimRight` `/`), the `StepStatus` notice (96-99). Writes only `property_setup:<id>` via `Mark`/`Finish`; the property read is owner-scoped (`wizardLoadApt`, 54).
- Refactor: `wizard_data.go` 116-189 (`wizardContext` now calls `wizardBundle` 155-189; the PIN backfill stays before it, `CelebrateOnce` uses `PoolSettings(s.pool)`). `AfterSave` must not backfill the PIN or spend the celebration.
- Call site: `apartment_update.go` 734-738 (the prefix test on the validated `return_to`, after the fee return, before `?saved=1` and the letter test); 221-246 (`apartmentUpdateNotPorted` still keeps a no-`setup_step` wizard `return_to` in Python).
- Mapping: `apartment_update_wizard.go` 256-262 (the seam is gone; the write follows the checks) and 276-309 (`apartmentAfterWizardSave`: 200 notice through `RenderSetupPage`, no draft; message keys from existing catalogs only).
- CSRF: no new form or route; `enter` checks it before the load.
