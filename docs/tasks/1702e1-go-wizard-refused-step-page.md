# 1702e1: Go property settings 3e1: the wizard step page a save draws again

Status: todo (exact-diff pass 2026-11-17: sidecars applied to a clean worktree of 4ae689e, gofmt/build/vet clean, Go tests green on PostgreSQL 16, 0 skips; no Python file changes)
Decision 2026-11-17 (owner/orchestrator, rule 11): option 1 of the old 1702e owner question: the wizard step saves are ported to Go. The wizard GET pages are already Go (briefs 1599-1602, `go/internal/web/onboarding/wizard*.go`), so no page port is needed; this brief adds only the extra context of a save that stays on its step.
Depends on: nothing open (independent of 1702d2: no file in common) | Base commit: current tip of the working branch | Branch: task/1702e1-go-wizard-refused-step-page
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (this brief needs about 10)
Tier: A (fresh review of the full diff before merge, see the risk list at the end)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1702e1 step k` (`k` is the step number) and `git add` only the paths the step names (never `-A`, never `.`). Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1702e1 step'`.

## 1. Objective

Give the onboarding package an exported `RenderSetupPage`: Python's `render_wizard(request, id, step, extra=..., status_code=...)` (`App/app/routes/onboarding_wizard.py` 199-215) with the extra context that `refuse_setup_save` (226-281) and `_wizard_rerender` (`App/app/routes/admin.py` 2646-2652) pass: `setup_notice`, `operator_error`, `police_errors`, `address_errors` and `draft`. Brief 1702e2 calls it from the Go `POST /apartments/{id}`. Nothing is written; no route changes.

## 2. Context

Rules (AGENTS.md): 1 filing correctness: no filing code; 2 privacy: no new field, no outbound request; 4 no new dependency; 5 the apartment is read only through the owner-scoped `wizardContext(ctx, h.Workspace.ID, id, ...)`; 6/9 no new copy (the messages come from the caller, already translated; no catalog change); 7/10 UX gate: **pending until 1705** (the wizard routes are dormant, not in `UBYHOST_GO_PATHS`; with no extra context the pages are byte-identical to today, the test checks that); 8 dormant; 11 Go.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1702e1-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Five files are replaced and two are new; step 0 checks the current hashes of the five.

| sha256 after | file | action | lines |
|---|---|---|---|
| `5eeeb7c57864026aa710c51e17902aeef4f6e422c2faf4bea335f886afaa8139` | `go/internal/web/onboarding/wizard_pages.go` | replace | 187 |
| `5da64457b629235811ae2be4cfa1e84dba002686436ea6b85571aef3f0ec327b` | `go/internal/web/onboarding/wizard_step.go` | replace | 274 |
| `f466b9e1b0b71f4a98d12af9e968f56e6b88da7a79800c9e75ab0af7d13fbef9` | `go/internal/web/onboarding/wizardtemplates/_frame.tmpl` | replace | 51 |
| `c0bad8a7e5fcebddcfc44dc4b445239dd4e26c8ca5ded992be8c9b153f4f1360` | `go/internal/web/onboarding/wizardtemplates/police.tmpl` | replace | 131 |
| `08a54ac76dd5641f88f0e383449a3dcf10fab61082edadefecf8b3fdcceec7be` | `go/internal/web/onboarding/wizardtemplates/property.tmpl` | replace | 114 |
| `9f27ef42fef9cd1aa71a061470a68ac662ab5b810ffc756b18f86d61b6bce7a4` | `go/internal/web/onboarding/wizard_refuse.go` | create | 121 |
| `aacbbb48a59911fa96f0497fb88e6a6709a97c05086c758fd6fb68382d0d265b` | `go/internal/web/onboarding/wizard_refuse_test.go` | create | 168 |

**What changed (for the reviewer; the executor reads no Go file).**

- `wizard_refuse.go` (new): `FieldError{Field, Message}`; `SetupPage{Status, Notice, OperatorError, PoliceErrors, AddressErrors, Draft}`; `RenderSetupPage(w, r, pool, getenv, now, h, id, step, p)`: `wizardContext` scoped to `h.Workspace.ID` (nil: `wizardMissing`, Python's redirect to `/apartments` with `flash.error.no_such_apartment`), then the existing `wizardShow` with `p.Status` and `applySetupPage`. `applySetupPage` overlays `Draft` (column -> posted text) on `Values` and on a **copy** of `Apt` (a drafted `legal_entity_id` moves the operator picker, as Jinja's `apartment = draft`; not a whole number: None), keeps an earlier `OperatorError` when `p.OperatorError` is empty, sets `Notice`, `PoliceErrors`, `AddressErrors`. Columns no wizard form prints are ignored.
- `wizard_step.go` (+3 view fields): `Notice`, `PoliceErrors`, `AddressErrors`.
- `wizard_pages.go`: `wizardAddressInput` gains `Error` and `Described()` (`name-help` then `name-error`, the macro's `described | join(' ')`); `AddressRows` fills `Error` from `AddressErrors`; imports `strings`.
- Templates (Go twins of the Jinja lines, no new string): `_frame.tmpl` +1 line after the required legend: `{{if .Notice}}<p class="err-text" role="alert">{{.Notice}}</p>{{end}}` (`_layout.html` 45). `police.tmpl`: after the operator error, one `<p class="err-text" id="{field}-error" role="alert">` per police error (`police.html` 8-10); header comment updated. `property.tmpl`: each address input prints `aria-describedby` from `Described`, `aria-invalid="true"` and the error line when refused (`_property_address_fields.html` 11-22); header comment updated.
- `wizard_refuse_test.go` (new, hand-written expected lines, seed `testdata/wizard_golden_post.json`): police refusal (notice escaped, errors in the given order, draft escaped in the box), property refusal (draft name/hour/operator, two address errors with `aria-describedby`/`aria-invalid`, no other error), an empty `SetupPage` draws exactly the GET page (property of apartment 12, police of 11), another host's apartment redirects to `/apartments?err=`, and a unit test of the draft and `Described`.
- Accepted differences (put in the report): the caller translates `validation_message`; the stay-fee, door-lock and automation drafts (`fee_account_error`, `lock_draft`) are not ported: those steps are retired (0884), Python sends their posts to `/done` before any refusal.

## 3. Files

| Path | Action |
|---|---|
| the seven files of the table above | replace or create |
| `docs/tasks/1702e1-files/**` | keep (sidecars, committed with this brief; do not edit) |
| `docs/tasks/1702e1-report.md` | create (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `find docs/tasks/1702e1-files -name '*.txt' | wc -l | tail -1` prints `7`.
   - `ls go/internal/web/onboarding/wizard_refuse.go go/internal/web/onboarding/wizard_refuse_test.go 2>&1 | grep -c 'No such file' | tail -1` prints `2`.
   - The five files are exactly the ones the sidecars were built on (one call):

     ```bash
     sha256sum -c - <<'EOF0' 2>&1 | tail -6
     db4e18c77e50943c91776acf88f740062324757db8fe18d2ace90dd61cfa9ebe  go/internal/web/onboarding/wizard_pages.go
     011311f0ede75226ada96db9f3507dbe05700c1794aee2c013746b1d05eee967  go/internal/web/onboarding/wizard_step.go
     ae64db321358567821db77b69aae7c8f7d707fab07c051876b449a09a6ab7574  go/internal/web/onboarding/wizardtemplates/_frame.tmpl
     ebd7edeced1798711a49be4849fbe31455c28ef05e0ed95e48dcceb2a0bd6277  go/internal/web/onboarding/wizardtemplates/police.tmpl
     7f12d777b6dd60930b5a4502581e3017e8b7ae50d0d8669c322b31f9cd0b263d  go/internal/web/onboarding/wizardtemplates/property.tmpl
     EOF0
     ```

     Five lines ending `: OK`. A `FAILED` line: STOP, the orchestrator re-bases the sidecars.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1702e1-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF1' 2>&1 | tail -8
   5eeeb7c57864026aa710c51e17902aeef4f6e422c2faf4bea335f886afaa8139  go/internal/web/onboarding/wizard_pages.go
   5da64457b629235811ae2be4cfa1e84dba002686436ea6b85571aef3f0ec327b  go/internal/web/onboarding/wizard_step.go
   f466b9e1b0b71f4a98d12af9e968f56e6b88da7a79800c9e75ab0af7d13fbef9  go/internal/web/onboarding/wizardtemplates/_frame.tmpl
   c0bad8a7e5fcebddcfc44dc4b445239dd4e26c8ca5ded992be8c9b153f4f1360  go/internal/web/onboarding/wizardtemplates/police.tmpl
   08a54ac76dd5641f88f0e383449a3dcf10fab61082edadefecf8b3fdcceec7be  go/internal/web/onboarding/wizardtemplates/property.tmpl
   9f27ef42fef9cd1aa71a061470a68ac662ab5b810ffc756b18f86d61b6bce7a4  go/internal/web/onboarding/wizard_refuse.go
   aacbbb48a59911fa96f0497fb88e6a6709a97c05086c758fd6fb68382d0d265b  go/internal/web/onboarding/wizard_refuse_test.go
   EOF1
   ```

   Seven lines ending `: OK`. Then commit (one call):

   ```bash
   git add go/internal/web/onboarding/wizard_pages.go go/internal/web/onboarding/wizard_step.go go/internal/web/onboarding/wizardtemplates/_frame.tmpl go/internal/web/onboarding/wizardtemplates/police.tmpl go/internal/web/onboarding/wizardtemplates/property.tmpl go/internal/web/onboarding/wizard_refuse.go go/internal/web/onboarding/wizard_refuse_test.go && git commit -m "1702e1 step 1" 2>&1 | tail -2
   ```

2. Format, build and vet (one call, repo root):

   ```bash
   cd go && gofmt -l internal/web/onboarding cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/onboarding/... ./cmd/ubyhost-web/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8).

3. Python checks: none. No Python file changes and no golden is regenerated. Write "Python checks: none (no Python change)" in the report.

4. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (skip the start if `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg56441/data status' | head -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg56441 && chown postgres /var/tmp/pg56441 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg56441/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg56441/data -o "-p 56441 -k /var/tmp/pg56441" -l /var/tmp/pg56441/log start' 2>&1 | tail -3
   ```

   Expected: `server started`. No PostgreSQL 16 binaries at that path: write "CI only" in the report and STOP before step 5.

5. Go tests on PostgreSQL (one call, repo root):

   ```bash
   cd go && export UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:56441/postgres && go test ./internal/web/onboarding/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30; go test ./internal/web/onboarding/ -count=1 -v -run '^TestWizard(Refuse|SetupPageDraft)' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -8; go test ./internal/web/onboarding/... -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1
   ```

   Expected: two `ok` lines; then `--- PASS` for `TestWizardRefusePolice`, `TestWizardRefuseProperty`, `TestWizardRefuseEmptyIsTheStepPage`, `TestWizardRefuseForeign`, `TestWizardSetupPageDraft`, and one `ok`; then `0`. A failure: run once more; a second failure: STOP (§8). Then stop the server if you started it: `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg56441/data stop' 2>&1 | tail -2 && rm -rf /var/tmp/pg56441`.

6. UX gate: **pending until 1705.** The routes are dormant and an empty `SetupPage` draws the GET page unchanged (step 5 checks it). Write in the report: "UX: wizard error lines only appear through 1702e2's dormant route; the 390/768/1280 screenshots of the refused property and police steps are taken in 1705". Nothing to commit.

7. Write the report (§9), set `Status: review` in this file, and commit (one call): `git add docs/tasks/1702e1-report.md docs/tasks/1702e1-go-wizard-refused-step-page.md && git commit -m "1702e1 step 7" 2>&1 | tail -2`.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `App/`; every other file under `go/` (in particular `go/internal/web/properties/`, which 1702d2 changes; no catalog, no `i18n_keys.txt`); filing code (`go/internal/ubyport`); never regenerate a golden JSON.

## 6. Commands

Exactly the commands of §4 (steps 2 and 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about this brief's files).

## 7. Acceptance

- [ ] Step 0: `7`, `2`, five `: OK`; step 1: seven `: OK`.
- [ ] Step 2 printed nothing.
- [ ] Step 5: two `ok` lines, the five named tests `--- PASS`, SKIP count `0`.
- [ ] `git log --oneline --grep='^1702e1 step' | tail -5` lists steps 1 and 7; `git show --stat --format=%s $(git log --format=%h --grep='^1702e1 step') | tail -20` lists only the paths of §3.
- [ ] Nothing in `App/` or `UBYHOST_GO_PATHS` changed.

## 8. Stop and ask

An anchor, hash or count of steps 0-1 not as stated; a test fails twice (fix nothing in the sidecars: report); 25 tool calls or about 50k tokens (report as `blocked`); a file outside §3 needs a change; push, merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/1702e1-report.md` (500 tokens at most): the files (`git show --stat` as in §7); each command with its last 5 lines and the SKIP count; §7 ticked; deviations; the accepted differences of §2; "UX pending until 1705"; "1702e2 is next (after 1702d2)".

## Risk list (Tier A review)

- Queries and scoping: `wizard_refuse.go` lines 33-49 (`RenderSetupPage`: the only read is `wizardContext` with `h.Workspace.ID`; nil answers the no-such-apartment redirect). The caller must pass the logged-in host.
- Draft on a copy: `wizard_refuse.go` 51-68 (`applySetupPage` copies `*v.Apt` before setting `LegalEntityID`, so the loaded row is never changed; tested in `TestWizardSetupPageDraft`).
- CSRF: no new form; the step forms keep `{{csrf}}` (`police.tmpl`, `property.tmpl` unchanged there). The test route skips the CSRF check on purpose: it exercises the renderer, not a POST handler (1702e2's handler checks CSRF through `enter`).
- Templates: `_frame.tmpl` line 37 (notice), `police.tmpl` 16-18 (errors), `property.tmpl` 102-103 (address input attributes and error line). All values go through `html/template` escaping (`TestWizardRefusePolice` checks `<b>` and `"`).
- Route registration: none. 1702e2 calls `onboarding.RenderSetupPage` from `go/internal/web/properties/apartment_update.go`, which 1702d2 changes; `properties` already imports `onboarding`, so no import cycle.
