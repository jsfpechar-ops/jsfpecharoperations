# 1445: Go guest guide editor, part 6: the guide overview page

Status: review
Depends on: 1440 | Base commit: 68c0e0985 | Branch: task/1445-go-guide-editor-index
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the overview page of the guest guide, `GET /apartments/{id}/guide` (`guide_index`), to `go/internal/web/ai`, with its template and the read sides it needs: the import state, drafted cards, open guest questions, the Leon switch and card state, and the usage line. It sends nothing out; it reads the same switches and counts as Python.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (guide pages only); 2 privacy: no new personal-data field, no new retention line, no outbound request; 3 fixtures are made up (`@example.test`, test-only secrets); 4 no new dependency (stdlib, pgx and packages already in `go.mod`); 5 plain PostgreSQL through `pgxpool`, the Python SQL with `$n` placeholders; 6 light mode, the forms work without JavaScript (they post plain forms); 7 and 10 see §7.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The page shows whether a listing import and Leon are on; it makes no call to Apify or to a model. The "feature switches and spend caps" are only read (`UBYHOST_APIFY_TOKEN`, `UBYHOST_AI_FEATURES`, the provider key, `UBYHOST_AI_TEST_EMAILS`, `UBYHOST_BILLING_ENABLED`); the budget checks that stop a call live in the job (`go/internal/guideimport`, `go/internal/anthropic`), not here.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1445-files/<repo path>.txt`.

| sha256 | file | action | lines |
|---|---|---|---|
| `02cfca92729762fd3ce6dcbc3e6ac56bf0736dc2c7cbb8d2abc846709d348ff8` | `go/internal/web/ai/guide_index.go` | create | 311 |
| `61ff68b2351eb6b8574d89cb0fb8f68aafaa7ebfabae8df733e9787c12527b2a` | `go/internal/web/ai/guide/templates/guide_index.tmpl` | create | 74 |
| `9a0864b69a029bcbc2b72d3fe6346ef7db1392cc72d2dace9426cc822c6a061c` | `go/internal/web/ai/guide_index_test.go` | create | 169 |

**How the code is built (for the reviewer; the executor reads no Go file, it only copies and runs).** The routes register through the table in `guide_common.go` (`guideAdd` in an `init()`), and `go/cmd/ubyhost-web/register_web_ai_guide.go` (brief 1440) hands them to `registerRoutes`; no other file of `go/cmd` changes. Every handler starts with `s.enter(w, r)`, which runs in FastAPI's order: for a POST `hostweb.CSRF` (header or `_csrf` field, multipart too), then the int path parameters (`422` when one is not an int), then `hostweb.Login` (`auth.require_login`), then `s.home(w, q)` (`_home`: the property of the signed-in workspace, not archived, else `404`). Redirects are `q.back` (`admin_helpers.back`, Starlette quoting), flashes are `q.flash(key, params)` from the guide catalog `guide/i18n.json`. Pages are `layout.Render` through `s.render` (host layout shell, `Cache-Control: no-store`). Every package-level name of these files starts with `guide`, so it cannot meet a name in the files of the other thread that works in `go/internal/web/ai` (`havel*.go`, `leon_setup*.go`); those files are not yours and not read.

**Parity notes:** `GET /apartments/{id}/guide` is `guide_index` (`routes/guest_guide.py` 61-96) and `guide_index` in `guide_index.go`. The page calls, in this order:

| Python | Go |
|---|---|
| `guest_guide.ensure_defaults` (a write), `guide_token.ensure` (a write), `items`, `progress` | `ensureDefaults`, `ensureToken`, `items`, `guideProgressOf` (brief 1440) |
| `guest_guide_import.imports_left` 130, `sources_left` 134-137, `in_progress` 209, `used_sources` 119-127, `imports` 199-206, `enabled` 111 | `usedSources`, `imports`, `importEnabled` (`guideimport.ConfigFromEnv(...).Token != ""`) |
| `guest_guide_merge.drafted_count` 255-261 | `draftedCount` |
| `guide_facts.next_step` | `nextStep` (brief 1440) |
| `ai.enabled_for_property("leon", id)` (`ai.py` 107-115, `enabled` 77-79, `owner_on_test_list` 87-94; `billing.entitlements(owner).leon`, which is false only for a `paused` account while billing is on) | `leonOffered` (`anthropic.ConfigFromEnv(...).Enabled`) |
| `leon.host_state` (`leon.py` 449-455, terms version `2026-10-25`) | `guideLeonState` |
| `guest_handoff.open_count` 57-58 | `openQuestions` |
| `guide_translate.usage` (`guide_translate.py` 226-237) with `ai.today().replace(day=1)` (Europe/Prague) | `usage`, `monthStart` (`anthropic.Service.Today`) |

The import section sits first while imports are enabled and there is something left, running or drafted; else it sits below the cards. The page links to `.../quick`, `.../questions` (Python, another thread) and `.../qr`.

**Known differences from Python, shared by every Go web area (not fixed here):** a missing or foreign record answers `404 {"detail":"Not Found"}` (and a non-integer id `422`), where Python shows the branded error page to a browser; `HEAD` and a wrong method answer `405` JSON (Python too); Go sets `Cache-Control` as the Python page routes do (`no-store`), and the `m.wrap` default `no-store, private` covers redirects.

**Anchors that must exist verbatim** (step 0): `def guide_index(request: Request, apartment_id: int):` in `App/app/routes/guest_guide.py`.

**Verified by the brief writer (in a throwaway worktree of this repo, sidecars copied exactly as step 1 does):** the four named tests PASS on PostgreSQL 16 (first visit creates the 17 cards and a 32-character token; import and Leon switches on and off; the import section moves; both sources used; Leon gated by feature, key, test-list and a paused account with billing on; Leon replies counted from the first of the month in Prague; cached guest languages; another account `404`, signed out redirect); the page body equals the Jinja render of `guest_guide.html` for a property with Leon offered, the import open for Booking, drafts, a failed import with a merge error, skipped, drafted and done cards and the usage line (whitespace between tags normalised). Not covered by a test: the open-questions count (`guest_question` needs a chat and a message row).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/ai/guide_index.go` | create | one route (the overview) and the read sides it needs |
| `go/internal/web/ai/guide/templates/guide_index.tmpl` | create | Go twin of guest_guide.html |
| `go/internal/web/ai/guide_index_test.go` | create | page and switch tests |
| `docs/tasks/1445-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1445-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints `task/1445-go-guide-editor-index`.
   - `grep -cF "def guide_index(request: Request, apartment_id: int):" App/app/routes/guest_guide.py | tail -1` prints `1`.
   - `ls go/internal/web/ai/guide_common.go go/internal/web/ai/guide_data.go go/cmd/ubyhost-web/register_web_ai_guide.go 2>&1 | tail -5` lists all three (brief 1440 is on this branch), and the files of §3 for this brief do not exist yet (`ls` says "No such file").
   - `find docs/tasks/1445-files -name '*.txt' | wc -l | tail -1` prints `3`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1445-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   02cfca92729762fd3ce6dcbc3e6ac56bf0736dc2c7cbb8d2abc846709d348ff8  go/internal/web/ai/guide_index.go
   61ff68b2351eb6b8574d89cb0fb8f68aafaa7ebfabae8df733e9787c12527b2a  go/internal/web/ai/guide/templates/guide_index.tmpl
   9a0864b69a029bcbc2b72d3fe6346ef7db1392cc72d2dace9426cc822c6a061c  go/internal/web/ai/guide_index_test.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1445 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/ai cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/ai/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all (gofmt lists nothing, build and vet are silent). Anything printed: STOP (§8). Commit "1445 step 2".

3. PostgreSQL: as brief 1440 step 3 (the server on port 55440 may still run: `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1440/data status' | tail -1` says `server is running`; if stopped, run only the `pg_ctl ... start` part of that step). Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres` below. No server: write "CI only" in the report and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres go test ./internal/web/ai/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
   ```

   Expected: two lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai	<seconds>s` and `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	<seconds>s`. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres go test ./internal/web/ai/ -count=1 -v -run '^TestGuideLeonStateAndTruthy$|^TestGuideMonthStartUsesPrague$|^TestGuideIndexPage$|^TestGuideIndexSwitchesAndCounts$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of 4 tests (times differ) and a final `ok` line; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestGuideLeonStateAndTruthy (0.NNs)
   --- PASS: TestGuideMonthStartUsesPrague (0.NNs)
   --- PASS: TestGuideIndexPage (0.NNs)
   --- PASS: TestGuideIndexSwitchesAndCounts (0.NNs)

5. Write the report (§9), set `Status: review` and commit "1445 step 5". Open one PR titled "1445: Go guest guide editor, part 6: the guide overview page" with the PR text of §2 in its description.

## 5. Do not touch

As brief 1440 §5, plus every file of briefs 1440 to 1444. `go/internal/anthropic` and `go/internal/guideimport` are only imported (`ConfigFromEnv`, `Service.Today`).

## 6. Commands

Exactly the commands of §4 (steps 2 and 4). No test-map row exists yet for `go/internal/web/ai`; the coordinator adds one from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | tail -30` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 3 files.
- [ ] Step 2 printed nothing (gofmt, build and vet clean).
- [ ] Step 4 printed `ok` for both packages, and each of the 4 named tests printed `--- PASS` (none `SKIP`, none `FAIL`) on PostgreSQL.
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

Write `docs/tasks/1445-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git diff --stat main...HEAD | tail -20`; `origin/main...HEAD` if there is no local `main`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `guide_index.go`: `leonOffered` (the feature switch and spend gates: feature listed, provider key set, test list, paused account), `importEnabled`, `buildIndex` (every read takes the apartment id of the owner-scoped `home`), and the template's three forms (`_csrf`, actions `.../import` and `.../cards`). Nothing in this file calls out.

## Owner steps

None: nothing is switched on.
