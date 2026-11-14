# 1603: Go setup wizard, part 5: delete the demo stay on "Delete and continue" (try-it skip)

Status: todo
Tier: A (deletes guest rows and passport photo files; must never touch a real stay)
Depends on: 1602 and 1596 (both done: `wizard_post.go`, `demoDeletePhoto`), 1640 (writable data volume, needed in production only) | Base commit: current branch (One big PR mode) | Branch: current branch
Executor: Haiku 5.5 | Fits one session: 20 tool calls, 45k tokens

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1603 step k`. Never create a branch, never push, never open a PR.

## 1. Objective

Serve the last branch of `POST /apartments/{apartment_id}/setup` on Go: `step=try_it`, `action=skip` while the property has a demo stay. Python (`App/app/routes/onboarding_wizard.py` 362-366) calls `demo.delete_demo_stay` (`App/app/demo.py` 126-144), audits `apartment=N step=try_it action=skip` and goes back to the finish page with the flash `flash.setup.demo_deleted`. After brief 1602 Go answers 501 there and writes nothing (`wizard_post.go`, `TestWizardSkipWithDemoStayIs501`). The owner allowed a writable data volume on 2026-11-14 (brief 1640), so this brief replaces the 501.

## 2. Context

Rules (AGENTS.md): 2 privacy: this deletes personal data (a demo guest's rows and passport photo files) and adds none; no new outbound request. 3 test data is made up. 4 no dependency. 5 plain PostgreSQL through `pgxpool`. 11 Go first.

The first version of this brief said an exported photo delete in `photosweep` was missing. It is not needed: brief 1596 already added `demoDeletePhoto(dataDir, guestID)` and `errDemoDataDir` in `go/internal/web/onboarding/demo_reset.go` (package `onboarding`, the same package as the wizard), the port of `passport_photos.delete_photo`. This brief reuses them; it does not copy file code.

**PR text (hard rule 2):** the button deletes the property's own demo stay (source `demo`) and its made-up guests, including their passport photo files; real stays are never touched. No new personal-data field, no new outbound request.

**Python `delete_demo_stay`, in order:** the stay must belong to the property and have `source = 'demo'` (else nothing happens); for each guest of the stay `passport_photos.delete_photo` (every `<guest id>.<ext>` and `.enc` file); `DELETE FROM alert WHERE reservation_id`; `DELETE FROM guest WHERE reservation_id`; `DELETE FROM reservation WHERE id AND source = 'demo'`. The route then audits `property_setup_step` with `apartment=N step=try_it action=skip` (also when there was nothing to delete) and answers a 303 to the finish page, with `flash.setup.demo_deleted` only when a stay was deleted.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1603-files/<repo path>.txt`.

| sha256 | file | action | lines |
|---|---|---|---|
| `db25e75f484c4136086185d675b39ce12e8c678fbcd033789c0e567703865dd7` | `go/internal/web/onboarding/wizard_demo_delete.go` | create | 65 |
| `c1436cde1118af25c6ff1ee6dd48b941cbe2f48366186c830a7fe2d7134b9573` | `go/internal/web/onboarding/wizard_post_test.go` | replace (the old file only holds `TestWizardSkipWithDemoStayIs501` and `TestWizardAutomationTiming`; the second test is kept unchanged in the new file) | 195 |

**How the code is built (for the reviewer).** `wizardDeleteDemoStay` reads the stay with `apartment_id` and `source` (the guard of `is_demo_stay`), lists the guest ids, removes the photo files first (a missing `UBYHOST_DATA_DIR` or a file that cannot be removed fails the call before any row is touched, as in `demoClear`), then deletes alerts, guests and the stay in one transaction. In `wizard_post.go` the `skip` case calls it when the property has a demo stay (`wizardDemoStayID`), always writes the audit line, and on success answers with `hostweb.Back(... wizardFlash(r, "flash.setup.demo_deleted") ...)`; with no stay it falls through to the plain redirect, as before. The catalog already holds `flash.setup.demo_deleted` (`wizardtext/i18n.json`).

**Known difference from Python:** the three DELETEs run in one transaction (Python runs them one after another). The only visible effect is that a failure leaves the stay whole.

**Verified by the brief writer** in a throwaway copy of `go/` with these files and the two edits of step 2, PostgreSQL 16 on a disposable port: `gofmt -l` empty, `go build ./...` and `go vet` clean, `go test ./internal/web/onboarding/ -count=1` ok with the database tests run. The three new tests cover: apartment 22 (demo stay 106, guest 501, one alert, photo files `501.jpg.enc`, `501.png` and another guest's `502.jpg.enc`): 303 to the finish page with `?msg=`, stay, guest and alert gone, only `502.jpg.enc` left, stays 105, 101 and 107 untouched, one audit line, and a second press giving a 303 without a message; a host stay (103 on apartment 19) and a demo stay of another property (106 asked on apartment 20) are never deleted; a missing data directory answers 500 with the guest and its rows in place and no audit line (the read-only-volume case runs only when the tests are not run as root).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/onboarding/wizard_demo_delete.go` | create | `wizardDeleteDemoStay` |
| `go/internal/web/onboarding/wizard_post_test.go` | replace | three new tests, the timing test kept |
| `go/internal/web/onboarding/wizard_post.go` | edit | the `skip` case and the header comment (step 2) |
| `docs/tasks/1603-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1603-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `grep -cF 'wizardNotPorted(w, "deleting a demo stay (brief 1603)")' go/internal/web/onboarding/wizard_post.go | tail -1` prints `1`.
   - `grep -cF "func TestWizardSkipWithDemoStayIs501" go/internal/web/onboarding/wizard_post_test.go | tail -1` prints `1`.
   - `grep -cE "^func (demoDeletePhoto|demoIDs)\(|^var errDemoDataDir" go/internal/web/onboarding/demo_reset.go | tail -1` prints `3`.
   - `grep -c 'flash.setup.demo_deleted' go/internal/web/onboarding/wizardtext/i18n.json | tail -1` prints `3` or more.
   - `ls go/internal/web/onboarding/wizard_demo_delete.go 2>&1 | tail -1` says "No such file".
   - `find docs/tasks/1603-files -name '*.txt' | wc -l | tail -1` prints `2`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1603-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -4
   db25e75f484c4136086185d675b39ce12e8c678fbcd033789c0e567703865dd7  go/internal/web/onboarding/wizard_demo_delete.go
   c1436cde1118af25c6ff1ee6dd48b941cbe2f48366186c830a7fe2d7134b9573  go/internal/web/onboarding/wizard_post_test.go
   EOF
   ```

   Both lines must end with `: OK`. Commit "1603 step 1".

2. Two edits in `go/internal/web/onboarding/wizard_post.go` (editor tool; each old text must be found exactly once, else STOP). The three-space indent of the code blocks is markdown only; the Go lines start with tabs, as in the file.

   a. Replace the comment lines

   ```
   // Not ported (brief 1603, blocked): "skip" on the try-it page while a demo
   // stay exists deletes it with demo.delete_demo_stay, which also removes the
   // demo guests' passport photo files. The Go web container mounts /data
   // read-only, so that branch answers 501 and writes nothing.
   ```

   by

   ```
   // Brief 1603: "skip" on the try-it page while a demo stay exists deletes it with
   // demo.delete_demo_stay (wizard_demo_delete.go), which also removes the demo
   // guests' passport photo files and so needs the writable data volume of brief 1640.
   ```

   b. Replace

   ```
   			if stayID != 0 {
   				// demo.delete_demo_stay also deletes passport photo files (brief 1603).
   				wizardNotPorted(w, "deleting a demo stay (brief 1603)")
   				return nil
   			}
   			if err := s.wizardAudit(ctx, h, at, "property_setup_step", fmt.Sprintf("apartment=%d step=try_it action=skip", a.ID)); err != nil {
   				return err
   			}
   ```

   by

   ```
   			deleted := false
   			if stayID != 0 {
   				if deleted, err = s.wizardDeleteDemoStay(ctx, a.ID, stayID); err != nil {
   					return err
   				}
   			}
   			if err := s.wizardAudit(ctx, h, at, "property_setup_step", fmt.Sprintf("apartment=%d step=try_it action=skip", a.ID)); err != nil {
   				return err
   			}
   			if deleted {
   				hostweb.Back(w, r, doneURL, wizardFlash(r, "flash.setup.demo_deleted"), hostweb.Flash{})
   				return nil
   			}
   ```

   Check: `grep -c 'wizardNotPorted(w, "deleting' go/internal/web/onboarding/wizard_post.go | tail -1` prints `0`. Commit "1603 step 2".

3. Format, build, vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/onboarding cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/onboarding/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8).

4. PostgreSQL: as brief 1596 or 1602 (a throwaway server, `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres`; brief 1440 step 3 starts one). No server: write "CI only" in the report and STOP before step 5.

5. Tests (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres go test ./internal/web/onboarding/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
   ```

   Expected: `ok` for both packages (the golden `TestWizardPostMatchesPython` and every older test still pass). Then:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres go test ./internal/web/onboarding/ -count=1 -v -run '^(TestWizardSkipDeletesDemoStay|TestWizardSkipNeverDeletesARealStay|TestWizardSkipStopsWhenAPhotoStays|TestWizardAutomationTiming|TestWizardPostMatchesPython)$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -10
   ```

   Expected: five `--- PASS` lines and a final `ok`; no `--- SKIP`, no `--- FAIL`.

6. Write the report (§9), set `Status: review`, commit "1603 step 6". Last, from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 5. Do not touch

`go/cmd/`, every other file under `go/` (including `demo_reset.go` and the 1602 golden `testdata/wizard_golden_post.json`), `App/`, `deploy/`, Caddy files, `docs/context/*`. Never set `UBYHOST_GO_PATHS`.

## 6. Commands

Exactly those of §4 (steps 3 and 5). Test-map: the coordinator adds a row for `go/internal/web/onboarding` from the report. Never the full suite.

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for both files.
- [ ] Step 3 printed nothing; step 5 printed `ok` for both packages and five `--- PASS` on PostgreSQL.
- [ ] `grep -rn 'TestWizardSkipWithDemoStayIs501' go | tail -3` prints nothing.
- [ ] `git diff --stat main...HEAD | tail -20` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no compose, Caddy, env or Python file changed; nothing was pushed to `main`.
- [ ] UI: not applicable in this PR (rules 7 and 10): no template or CSS changes; the finish page is the one brief 1601 already covers.

## 8. Stop and ask

Stop, and write the report, if an anchor, hash or count of step 0, 1 or 2 is not as stated; a test fails twice (do not edit the sidecar files: report); you reach 20 tool calls or about 45k tokens (report as `blocked`); a new dependency seems needed; a file outside §3 needs a change; or you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1603-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with the last 5 lines of its output, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`wizard_demo_delete.go`: the guard `source = 'demo'` and `apartment_id` in the first query and again in the final DELETE; photo files are removed before the rows and a failure leaves every row; nothing is deleted when `UBYHOST_DATA_DIR` is empty and the stay has guests. `wizard_post.go`: the audit line is written whether or not a stay was deleted (as Python); the flash is only on a real delete.

## Owner steps

1. Deploy brief 1640 first (the data volume is writable); without it, a stay with a guest photo answers 500 and nothing is deleted.
2. The wizard paths go to Go with brief 1604's owner steps (`/apartments/*/setup` and `/apartments/*/setup/*`). If you already switched them without 1603, "Delete and continue" has been answering 501; after this brief is deployed it works. Check on staging: start the try-it rehearsal, register a demo guest with a photo, press "Delete and continue" and see the flash "Demo stay deleted." on the finish page.
3. Rollback: remove the two wizard paths from `UBYHOST_GO_PATHS` and run `docker compose up -d`.
