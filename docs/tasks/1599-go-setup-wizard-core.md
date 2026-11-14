# 1599: Go setup wizard, part 1: the entry route, the step route, the frame, the calendar and guest link pages

Status: todo
Tier: A
Depends on: none (the onboarding package `go/internal/web/onboarding` with `setup.go` is on go-wave3) | Base commit: current tip of the working branch | Branch: task/1599-go-setup-wizard-core
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1599 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1599 step'` and `git show --stat <commit>`, never a fixed base commit.

## 1. Objective

Port the two GET routes of the setup wizard of `App/app/routes/onboarding_wizard.py` to `go/internal/web/onboarding`: `GET /apartments/{apartment_id}/setup` (`setup_entry`) and `GET /apartments/{apartment_id}/setup/{step}` (`setup_step`), with the whole page context of `_wizard_context` and `render_wizard`, the wizard frame (`setup_wizard/_layout.html`) and two step pages: `calendar` and `guest_link`. Steps whose page is not ported yet (`property`, `police`, `done`, `try_it`) answer 501; briefs 1600 and 1601 add them, 1602 adds `POST /apartments/{apartment_id}/setup`. A golden file made by the real Python routes pins every case. Everything is dormant: no path is routed to it.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (the pages read the police settings, they do not file and do not save them); 2 privacy: no new personal-data field, no new retention line, no outbound request; 3 fixtures are made up (`@example.test`, test-only keys); 4 no new dependency (stdlib, pgx and packages already in `go.mod`: `golang.org/x/text/unicode/norm` for the slug fold, `time/tzdata` for Prague); 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, no schema change; 6 light mode, the pages are plain forms and links that work without JavaScript; 11 Go first. **Go-first exception used:** exception 1 (port plumbing): `App/scripts/onboarding_wizard_golden.py` writes the golden file from the live Python routes and `App/tests/test_go_onboarding_wizard.py` checks that the committed golden still matches them. No file under `App/app/` changes.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The pages read the host's own property row, the decrypted police password (only to say whether one is stored), stays and guests (counts only), as Python does. Like Python, a GET writes a little: a missing permalink PIN is created, a finished legacy guide is closed, the guest link slug is created once (`apartment_slug`, under an advisory lock) and the finish page records that the celebration was shown.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1599-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `8aeb52fc05ea53b491bc4d12f7ca5bbca6cfada83be35a7e6a2740138284da51` | `App/scripts/onboarding_wizard_golden.py` | create | 338 |
| `a1e405c6847d62ee21b808a35a7b249a24b38e7bce88c96a78fb58c0b2ecdc3a` | `App/tests/test_go_onboarding_wizard.py` | create | 32 |
| `dec594c3c35a64c1547b55ab758158d90535f50a6de7d6170664c316decfc9a1` | `go/cmd/ubyhost-web/register_web_onboarding_wizard.go` | create | 21 |
| `767c3a25f2d48deb6b46ccc8e3cd01d1e57bf9bb105c6df316de59fb997ffe7e` | `go/cmd/ubyhost-web/register_web_onboarding_wizard_test.go` | create | 23 |
| `20d68296704d2fa23871e5307d63d1ad8c0883a9d566ed53ca2a8a4f43de83bc` | `go/internal/web/onboarding/testdata/wizard_golden_entry.json` | create | 1615 |
| `278a4cefd42745073767112202f648203daca1ca86d497b083a83338ddc6cc0f` | `go/internal/web/onboarding/wizard.go` | create | 181 |
| `9811c14af3ac5907c61ef883ae8d623b28e952fdfa91c690c65d0fedc25505e2` | `go/internal/web/onboarding/wizard_data.go` | create | 568 |
| `f48e9eb1e5149ffaae1a4d60dcc890073c1af087fa56e21ec4c4e1db3f287438` | `go/internal/web/onboarding/wizard_entry.go` | create | 59 |
| `c309ae2221dae91d50ab66e4dbaec863efb2ef69ba008337381bb10cd1b18891` | `go/internal/web/onboarding/wizard_golden_test.go` | create | 432 |
| `bed4ea1779c2d9a6c62e6794534abd6567e5eba07154bc652d5141ff6da11e4b` | `go/internal/web/onboarding/wizard_slug.go` | create | 173 |
| `011311f0ede75226ada96db9f3507dbe05700c1794aee2c013746b1d05eee967` | `go/internal/web/onboarding/wizard_step.go` | create | 271 |
| `def767e1780c5559f1da90d5efa6d96a31cb5db3ba48b37a1249f583b474b664` | `go/internal/web/onboarding/wizard_test.go` | create | 182 |
| `ae64db321358567821db77b69aae7c8f7d707fab07c051876b449a09a6ab7574` | `go/internal/web/onboarding/wizardtemplates/_frame.tmpl` | create | 50 |
| `566444ce691d068791620cc05391f12ead0248facc428ef2fb040c6ff280a45f` | `go/internal/web/onboarding/wizardtemplates/calendar.tmpl` | create | 39 |
| `0c86a0fb752b3c49f46a9bc119a9f0c61358974cde3f5b4d12334ff2c1ac7ef4` | `go/internal/web/onboarding/wizardtemplates/guest_link.tmpl` | create | 41 |
| `e658d10ee04940707fbcc75fba380c1b1541f513bd5ba0ca23fd199fda40b243` | `go/internal/web/onboarding/wizardtext/i18n.json` | create | 1483 |
| `4216aac0f8b1c6363c9047fa3f5eaf3d6e289fd4d4f8d2941df17ab84d8dc409` | `go/internal/web/onboarding/wizardtext/i18n_keys.txt` | create | 35 |

**How the code is built (for the reviewer; the executor reads no Go file, it only copies and runs).** A parallel series (briefs 1595 to 1598) works in the same package on `GET /onboarding` and the demo routes, so every file here is new, named `wizard*`, and every new unexported identifier starts with `wizard`; `setup.go`, `routes.go` and their tests are not changed (the golden test reuses `testPool` and `seedAccounts` of `routes_test.go`). `wizard.go` has the route table (`wizardAdd` called from an `init()` in each file, so the briefs 1600 to 1602 add files and edit none), `RegisterWizard`, the FastAPI order (path integer, then `require_login`), the 422 body of a non-integer id, the flash helper and the renderer: `hostweb/layout.Render` with nav `apartments`, body kind `form`, V2, an empty page header and the title `wizard.title`. Each step page is its own template set: the shared `wizardtemplates/_*.tmpl` plus `<step>.tmpl`, which fills the blocks `wizard_help`, `wizard_content`, `wizard_actions` and `wizard_notes` of `_frame.tmpl` (the port of `_layout.html`); a step without a file answers 501. `wizard_data.go` builds the context in Python's order (load the property scoped by owner, PIN backfill, feeds, stored password, report completeness through `validation.ValidateApartment`, the lock switch under billing, stays and guest facts, the setup state and the legacy finish, the current guide, the guest link key, the businesses, the celebration on `done`). `wizard_slug.go` ports `guest_slug.link_key` and `ensure` (fold, readable part, random code, one current slug under `pg_advisory_xact_lock`). The text catalog is `wizardtext/i18n.json`, written by the existing `App/scripts/go_host_i18n.py` from `wizardtext/i18n_keys.txt` (it already finds every `i18n_keys.txt`); it holds the keys of all four wizard pages, so the later briefs add no catalog. `register_web_onboarding_wizard.go` hands the routes to `registerRoutes`.

**Parity notes (Python `App/app/routes/onboarding_wizard.py` unless named):**

| Route | Python | Go |
|---|---|---|
| `GET /apartments/{id}/setup` | `setup_entry` 284-305 | `wizard_entry.go` |
| `GET /apartments/{id}/setup/{step}` | `setup_step` 307-340, `_wizard_context` 63-197, `render_wizard` 199-216, `setup_wizard/_layout.html`, `calendar.html`, `guest_link.html` | `wizard_step.go`, `wizard_data.go`, `wizardtemplates/` |
| guest link key | `App/app/guest_slug.py` `link_key` 143, `ensure` 170 | `wizard_slug.go` |

The golden (`testdata/wizard_golden_entry.json`, 31 cases, made by the Python routes on SQLite with the same seed and the clock pinned to 2026-05-10) covers: the entry redirects (current guide, finished, hidden, finished but unresolved, legacy property, archived, another host's and missing property, text id, signed out), the calendar and guest link pages in English, Czech and Vietnamese (feeds, PIN and password present or not, the next stay window, the business name in the message), every redirect of the step route (a retired step to `done`, an unknown step to the entry, a step not yet allowed to the current guide) and the rows a GET writes (PIN, slug, finished guide). The Go test compares status, `Location`, title and the normalised `setup-wizard` fragment of each case, then the final rows.

**Known differences from Python, shared by every Go web area (not fixed here):** a missing or foreign property follows Python (back to `/apartments` with the error flash); a non-integer id answers FastAPI's 422 JSON; `HEAD` is served by the `GET` pattern; a server error is plain text 500, where Python shows the branded page. The steps `automation`, `stay_fee` and `door_lock` left the wizard in 0884: Python redirects them to `done` and so does Go, and their templates are not ported.

**Paths that become fully served by Go:** none yet. `/apartments/*/setup` and `/apartments/*/setup/*` also take a POST (brief 1602), and four step pages come in 1600 and 1601. **Assumption:** no `/apartments` path is in `UBYHOST_GO_PATHS` today (brief 1527's owner step 1 removes it). If the owner added `/apartments` or `/apartments/*`, these GET pages go live with 501 on four steps the moment this deploys.

**Verified by the brief writer** (in a throwaway worktree of go-wave3, with the steps of this brief applied exactly, sidecars copied as step 1 does): see the paragraph at the end of §7.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/onboarding_wizard_golden.py` | create | golden writer (seed, cases, normaliser); later briefs import it |
| `App/tests/test_go_onboarding_wizard.py` | create | the committed golden matches the Python routes |
| `go/cmd/ubyhost-web/register_web_onboarding_wizard.go` | create | hands the wizard routes to `registerRoutes` |
| `go/cmd/ubyhost-web/register_web_onboarding_wizard_test.go` | create | route registration test |
| `go/internal/web/onboarding/testdata/wizard_golden_entry.json` | create | golden of the entry and step routes |
| `go/internal/web/onboarding/wizard.go` | create | route table, `RegisterWizard`, helpers, renderer |
| `go/internal/web/onboarding/wizard_data.go` | create | page context and its queries |
| `go/internal/web/onboarding/wizard_entry.go` | create | `GET /apartments/{id}/setup` |
| `go/internal/web/onboarding/wizard_golden_test.go` | create | golden runner and `TestWizardEntryMatchesPython` |
| `go/internal/web/onboarding/wizard_slug.go` | create | guest link slug |
| `go/internal/web/onboarding/wizard_step.go` | create | `GET /apartments/{id}/setup/{step}`, page data |
| `go/internal/web/onboarding/wizard_test.go` | create | unit tests |
| `go/internal/web/onboarding/wizardtemplates/_frame.tmpl`, `calendar.tmpl`, `guest_link.tmpl` | create | Go twins of the templates |
| `go/internal/web/onboarding/wizardtext/i18n.json`, `i18n_keys.txt` | create | wizard catalog |
| `docs/tasks/1599-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1599-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `grep -cF "def setup_entry(apartment_id: int, request: Request):" App/app/routes/onboarding_wizard.py | tail -1` prints `1`.
   - `grep -cF "def setup_step(apartment_id: int, step: str, request: Request):" App/app/routes/onboarding_wizard.py | tail -1` prints `1`.
   - `grep -cF "def ensure(apartment) -> Optional[str]:" App/app/guest_slug.py | tail -1` prints `1`.
   - `grep -cE "^func (MayViewStep|Checklist|CelebrateOnce|WizardURL|Current|LegacyState|WizardUnresolved|Finish|NextApplicableStep|PrevApplicableStep)\(" go/internal/web/onboarding/setup.go | tail -1` prints `10`.
   - `grep -cE "^func (testPool|seedAccounts)\(" go/internal/web/onboarding/routes_test.go | tail -1` prints `2`.
   - `grep -cE "^func (stamp|serverError)\(" go/internal/web/onboarding/routes.go | tail -1` prints `2`, and `grep -cE "^func (pyStrip|in|indexOf)\(" go/internal/web/onboarding/setup.go | tail -1` prints `3` (helpers of the parallel series that these files call).
   - `grep -cF "func MustParseFuncs(" go/internal/hostweb/layout/pagefuncs.go | tail -1` prints `1`.
   - `ls go/internal/web/onboarding/wizard.go 2>&1 | tail -1` says "No such file" (nothing of this brief exists yet).
   - `find docs/tasks/1599-files -name '*.txt' | wc -l | tail -1` prints `17`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1599-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -20
   8aeb52fc05ea53b491bc4d12f7ca5bbca6cfada83be35a7e6a2740138284da51  App/scripts/onboarding_wizard_golden.py
   a1e405c6847d62ee21b808a35a7b249a24b38e7bce88c96a78fb58c0b2ecdc3a  App/tests/test_go_onboarding_wizard.py
   dec594c3c35a64c1547b55ab758158d90535f50a6de7d6170664c316decfc9a1  go/cmd/ubyhost-web/register_web_onboarding_wizard.go
   767c3a25f2d48deb6b46ccc8e3cd01d1e57bf9bb105c6df316de59fb997ffe7e  go/cmd/ubyhost-web/register_web_onboarding_wizard_test.go
   20d68296704d2fa23871e5307d63d1ad8c0883a9d566ed53ca2a8a4f43de83bc  go/internal/web/onboarding/testdata/wizard_golden_entry.json
   278a4cefd42745073767112202f648203daca1ca86d497b083a83338ddc6cc0f  go/internal/web/onboarding/wizard.go
   9811c14af3ac5907c61ef883ae8d623b28e952fdfa91c690c65d0fedc25505e2  go/internal/web/onboarding/wizard_data.go
   f48e9eb1e5149ffaae1a4d60dcc890073c1af087fa56e21ec4c4e1db3f287438  go/internal/web/onboarding/wizard_entry.go
   c309ae2221dae91d50ab66e4dbaec863efb2ef69ba008337381bb10cd1b18891  go/internal/web/onboarding/wizard_golden_test.go
   bed4ea1779c2d9a6c62e6794534abd6567e5eba07154bc652d5141ff6da11e4b  go/internal/web/onboarding/wizard_slug.go
   011311f0ede75226ada96db9f3507dbe05700c1794aee2c013746b1d05eee967  go/internal/web/onboarding/wizard_step.go
   def767e1780c5559f1da90d5efa6d96a31cb5db3ba48b37a1249f583b474b664  go/internal/web/onboarding/wizard_test.go
   ae64db321358567821db77b69aae7c8f7d707fab07c051876b449a09a6ab7574  go/internal/web/onboarding/wizardtemplates/_frame.tmpl
   566444ce691d068791620cc05391f12ead0248facc428ef2fb040c6ff280a45f  go/internal/web/onboarding/wizardtemplates/calendar.tmpl
   0c86a0fb752b3c49f46a9bc119a9f0c61358974cde3f5b4d12334ff2c1ac7ef4  go/internal/web/onboarding/wizardtemplates/guest_link.tmpl
   e658d10ee04940707fbcc75fba380c1b1541f513bd5ba0ca23fd199fda40b243  go/internal/web/onboarding/wizardtext/i18n.json
   4216aac0f8b1c6363c9047fa3f5eaf3d6e289fd4d4f8d2941df17ab84d8dc409  go/internal/web/onboarding/wizardtext/i18n_keys.txt
   EOF
   ```

   Every line must end with `: OK`. Then commit "1599 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/onboarding cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/onboarding/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). Nothing changed, so no commit.

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if an earlier brief of this series left it running (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55599/data status' | tail -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55599 && chown postgres /var/tmp/pg55599 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55599/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55599/data -o "-p 55599 -k /var/tmp/pg55599" -l /var/tmp/pg55599/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55599/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the Go tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55599/postgres go test ./internal/web/onboarding/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: two `ok` lines, one for `go/internal/web/onboarding` and one for `go/cmd/ubyhost-web`. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55599/postgres go test ./internal/web/onboarding/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestWizardEntryMatchesPython$|^TestWizardSlugIsCreatedOnce$|^TestWizardLockAllowed$|^TestWizardOperatorFirstName$|^TestWizardDateFilters$|^TestWizardStepWithoutPageIs501$|^TestWizardTemplatesUseKnownKeys$|^TestWizardRoutesRegistered$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of the 8 tests and two final `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestWizardEntryMatchesPython (N.NNs)
   --- PASS: TestWizardSlugIsCreatedOnce (0.NNs)
   --- PASS: TestWizardLockAllowed (0.NNs)
   --- PASS: TestWizardOperatorFirstName (0.NNs)
   --- PASS: TestWizardDateFilters (0.NNs)
   --- PASS: TestWizardStepWithoutPageIs501 (0.NNs)
   --- PASS: TestWizardTemplatesUseKnownKeys (0.NNs)
   --- PASS: TestWizardRoutesRegistered (0.NNs)

5. Run the Python side (one call, from `App/`). If `App/.venv` does not exist, write "CI only" for this step in the report and go on:

   ```bash
   cd App && .venv/bin/python -m pytest tests/test_go_onboarding_wizard.py tests/test_go_host_i18n.py -q --tb=short -x 2>&1 | tail -5
   ```

   Expected: `3 passed` (the golden matches the Python routes; the catalog matches `go_host_i18n.py`), no skip.

6. Write the report (§9), set `Status: review` in this file and commit "1599 step 6". Do not open a PR (one big PR mode); the owner or the orchestrator opens it with the PR text of §2.

## 5. Do not touch

`App/app/` (the Python routes stay the live ones), `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, every other file under `go/` (in this package `setup.go`, `routes.go`, their tests and templates belong to the parallel series), `go/go.mod`. Hard rules of AGENTS.md: no secret or guest datum in a file or a log (the test data is made up), nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 2, 4 and 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 17 files.
- [ ] The format, build and vet step printed nothing.
- [ ] Step 4 printed `ok` for both packages, and each of the 8 named tests printed `--- PASS` (none `SKIP`, none `FAIL`) on PostgreSQL.
- [ ] Step 5 printed `3 passed` (or "CI only" is written in the report).
- [ ] `git log --oneline --grep='^1599 step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1599 step') | tail -40` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or `App/app/` file changed; nothing was pushed to `main`.
- [ ] UI: the UX gate of rule 10 is **pending**. The pages are dormant (no path routes to them) and the Python-side browser tests cannot reach the Go service. `test_layout_lint_browser.py`, the 390, 768 and 1280 px screenshots of each wizard page and a line per page in the PR run on staging before the owner adds the paths (brief 1602, Owner steps).

**Verified by the brief writer:** in a throwaway worktree of go-wave3 with the steps of this brief applied exactly (sidecars copied as step 1 does, `sha256sum -c` all OK), `gofmt -l` printed nothing, `go build ./...` and `go vet ./internal/web/onboarding/... ./cmd/...` were silent, step 4 passed on PostgreSQL 16 (port 55599) with the 8 named tests `--- PASS` and 0 SKIP, and step 5 printed `3 passed`. Running `App/scripts/onboarding_wizard_golden.py` twice wrote a byte-identical golden.

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

Write `docs/tasks/1599-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git diff --stat` as in §7).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of: `wizard_data.go` (`wizardAptSQL` scopes by `owner_user_id IS NOT DISTINCT FROM $2`; the order of the writes a GET makes; `wizardLockAllowed` under billing; the password is decrypted only to a yes or no), `wizard_slug.go` (the advisory lock and the second read after a unique violation), `wizard_entry.go` and `wizard_step.go` (the redirect order against `setup_entry` and `setup_step`), `wizardtemplates/_frame.tmpl` (the step list, the help and the counter). The golden runner normalises only CSRF values, QR images and whitespace.

## Owner steps

None: nothing is switched on. The path switch for the wizard is in the owner steps of brief 1602.
