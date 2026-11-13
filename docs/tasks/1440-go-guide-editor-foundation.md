# 1440: Go guest guide editor, part 1: shared gate, ownership check, data rules, catalog and test helpers

Status: todo
Depends on: none | Base commit: 68c0e0985 | Branch: task/1440-go-guide-editor-foundation
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the shared base of the guest guide editor to `go/internal/web/ai`: the route table, the CSRF/path/login/ownership gate, the guide catalog, the data rules of `guest_guide.py`, `guide_token.py`, the photo rows and the reading half of `guide_facts.py`, the test helpers, and `go/cmd/ubyhost-web/register_web_ai_guide.go`. It adds no route yet: briefs 1441 to 1446 add the 20 routes of `App/app/routes/guest_guide.py` (the photo upload stays on Python, brief 1447). The code is dormant: nothing routes to it until the owner adds paths to `UBYHOST_GO_PATHS`.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (guide pages only); 2 privacy: no new personal-data field, no new retention line, no outbound request; 3 fixtures are made up (`@example.test`, test-only secrets); 4 no new dependency (stdlib, pgx and packages already in `go.mod`); 5 plain PostgreSQL through `pgxpool`, the Python SQL with `$n` placeholders; 6 light mode, the forms work without JavaScript (they post plain forms); 7 and 10 see §7.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. This brief only reads and writes `guide_item`, `guide_fact`, `guide_photo` rows and `apartment.guide_token`, which Python already does.

**All code is pre-written and was compiled and tested.** Sidecars are `docs/tasks/1440-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Write nothing outside §3.

| sha256 | file (repo path; sidecar = `docs/tasks/1440-files/<path>.txt`) | action | lines |
|---|---|---|---|
| `b331489a871dde09757e6b6d7ab488571009b4b863a9aedc3aed6d9f7f2185f5` | `go/internal/web/ai/guide_common.go` | create | 317 |
| `48ae19dffb13759c5201d29bbdcb02c7702b56c11c9447ea69d30957ba4cab23` | `go/internal/web/ai/guide_data.go` | create | 615 |
| `18ee75dd8e70cd1fe068a00cfcb54f82a02206f0ac2f24cd018eaf2c55a872dd` | `go/internal/web/ai/guide/i18n_keys.txt` | create | 27 |
| `0d8e3f4f945ecf041237146338ec39f46b7bf3a828e43b0053fe31704d288fa8` | `go/internal/web/ai/guide/i18n.json` | create | 725 |
| `02764f4d54caeaf2c676bece286b1a7981cb9fc9f521f798c79626fb00d4096e` | `go/internal/web/ai/guide/templates/guide_shared.tmpl` | create | 2 |
| `7f46022d36cb97fe06e982898de52819d99cdd9f7f6a87f63ab9d181d9d9c635` | `go/internal/web/ai/guide_testutil_test.go` | create | 287 |
| `fd085871ff740ba6690d2fd8f3e81f6513173b06691c63c18abd9dce0d2b46e2` | `go/internal/web/ai/guide_common_test.go` | create | 107 |
| `e1f36b9f0f461c7c203a700729126db6b9b27d148272397d072d679244a7f117` | `go/internal/web/ai/guide_data_test.go` | create | 304 |
| `7fb3a5c468427474a1d1f011214269441f2b9a79dd5bdd0c87e355c3fc98e145` | `go/cmd/ubyhost-web/register_web_ai_guide.go` | create | 26 |

**How the code is built (for the reviewer; the executor reads no Go file, it only copies and runs).** The routes register through the table in `guide_common.go` (`guideAdd` in an `init()`), and `go/cmd/ubyhost-web/register_web_ai_guide.go` (brief 1440) hands them to `registerRoutes`; no other file of `go/cmd` changes. Every handler starts with `s.enter(w, r)`, which runs in FastAPI's order: for a POST `hostweb.CSRF` (header or `_csrf` field, multipart too), then the int path parameters (`422` when one is not an int), then `hostweb.Login` (`auth.require_login`), then `s.home(w, q)` (`_home`: the property of the signed-in workspace, not archived, else `404`). Redirects are `q.back` (`admin_helpers.back`, Starlette quoting), flashes are `q.flash(key, params)` from the guide catalog `guide/i18n.json`. Pages are `layout.Render` through `s.render` (host layout shell, `Cache-Control: no-store`). Every package-level name of these files starts with `guide`, so it cannot meet a name in the files of the other thread that works in `go/internal/web/ai` (`havel*.go`, `leon_setup*.go`); those files are not yours and not read.

**The thread.** Another brief writer ports `havel.py` and `leon_setup.py` into the same Go package at the same time. Package `ai` therefore holds files that are not in this brief. This brief owns `go/internal/web/ai/guide*.go`, the folder `go/internal/web/ai/guide/` (catalog, templates; a data folder without Go files) and the registration file. The catalog sits in `guide/` because `App/scripts/go_host_i18n.py` writes `i18n.json` next to each `i18n_keys.txt`; a second key list in the package folder itself would collide with the other thread.

**What the data layer mirrors (Python, file and lines):**

| Go (`guide_data.go`) | Python |
|---|---|
| `guideKinds`, `guideTopics`, `guideDefaultKinds`, `guideMustHave`, `guideLimits` | `App/app/guest_guide.py` 18-100 (a test pins them to `go/internal/guideimport`, which has its own golden) |
| `items`, `getItem` | `guest_guide.py` `items` 152-166, `get` 169-174 |
| `addKind`, `ensureDefaults` | `add_kind` 115-127, `ensure_defaults` 130-149 |
| `guideClean`, `save` | `_clean` 177-193, `save` 196-210 |
| `skip`, `discardDraft` | `skip` 213-227, `discard_draft` 230-240 |
| `addCustom`, `deleteCustom` | `add_custom` 243-264, `delete_custom` 267-275 |
| `guideProgressOf`, `guideNextOpen` | `progress` 278-295, `routes/guest_guide.py` `_next_open` 50-58 |
| `ensureToken`, `rotateToken` | `App/app/guide_token.py` `ensure` 31-42, `rotate` 44-49 |
| `photos`, `photo`, `deletePhoto` | `App/app/guide_photos.py` `photos` 45-52, `get` 55-62, `delete` 98-104 |
| `answers`, `nextStep` | `App/app/guide_facts.py` `answers` 50-52, `next_step` 97-100 |
| `guide_common.go` `enter`, `home` | `routes/guest_guide.py` `_home` 23-27, router dependency `security.protect_host_post` |

Python `str.strip()` is `guidePyStrip` (also trims `\x1c`-`\x1f`); lengths count code points; `form.get` is last-value-wins (`guideFormValue`).

**Known differences from Python, shared by every Go web area (not fixed here):** a missing or foreign record answers `404 {"detail":"Not Found"}` (and a non-integer id `422`), where Python shows the branded error page to a browser; `HEAD` and a wrong method answer `405` JSON (Python too); Go sets `Cache-Control` as the Python page routes do (`no-store`), and the `m.wrap` default `no-store, private` covers redirects.

**Anchors that must exist verbatim** (step 0): `App/app/routes/guest_guide.py` has `def _home(request: Request, apartment_id: int) -> Dict[str, Any]:` and `def _next_open(apartment_id: int, after_id: int) -> Optional[int]:`.

**Verified by the brief writer (in a throwaway worktree of this repo, sidecars copied exactly as step 1 does):** gofmt empty, `go build ./...` and `go vet ./internal/web/ai/... ./cmd/...` silent, `go test ./internal/web/ai/ ./cmd/ubyhost-web/` ok on PostgreSQL 16 (the 11 named tests PASS, none skipped). Mutations that each made the Go tests fail: the owner condition removed from the apartment query, the CSRF gate switched off, the apartment join removed from the photo query. Not run: the Python test suite (no application environment here).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/ai/guide_common.go` | create | route table, CSRF/path/login gate, ownership check, flash and redirect helpers, render helper, page funcs |
| `go/internal/web/ai/guide_data.go` | create | guest_guide.py, guide_token.py, guide_photos.py (rows) and guide_facts.py (reading) as Go |
| `go/internal/web/ai/guide/i18n_keys.txt` | create | host keys of the guide pages (all briefs 1440 to 1446) |
| `go/internal/web/ai/guide/i18n.json` | create | generated from host_i18n.py by `App/scripts/go_host_i18n.py` (do not edit) |
| `go/internal/web/ai/guide/templates/guide_shared.tmpl` | create | the card title define the pages share |
| `go/internal/web/ai/guide_testutil_test.go` | create | test helpers: database, session, CSRF, one seeded world |
| `go/internal/web/ai/guide_common_test.go` | create | tests of the gate helpers, route table, catalog |
| `go/internal/web/ai/guide_data_test.go` | create | tests of the data rules (pure and PostgreSQL) |
| `go/cmd/ubyhost-web/register_web_ai_guide.go` | create | registers `ai.GuideRoutes` through `registerRoutes` |
| `docs/tasks/1440-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1440-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints `task/1440-go-guide-editor-foundation`.
   - `grep -cF "def _home(request: Request, apartment_id: int) -> Dict[str, Any]:" App/app/routes/guest_guide.py | tail -1` prints `1`.
   - `grep -cF "def _next_open(apartment_id: int, after_id: int) -> Optional[int]:" App/app/routes/guest_guide.py | tail -1` prints `1`.
   - `ls go/internal/web/ai/guide_common.go 2>&1 | tail -1` says "No such file" (nothing of this brief is there yet), and `grep -c "skip2/go-qrcode" go/go.mod` prints `1`.
   - `find docs/tasks/1440-files -name '*.txt' | wc -l | tail -1` prints `9`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1440-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   b331489a871dde09757e6b6d7ab488571009b4b863a9aedc3aed6d9f7f2185f5  go/internal/web/ai/guide_common.go
   48ae19dffb13759c5201d29bbdcb02c7702b56c11c9447ea69d30957ba4cab23  go/internal/web/ai/guide_data.go
   18ee75dd8e70cd1fe068a00cfcb54f82a02206f0ac2f24cd018eaf2c55a872dd  go/internal/web/ai/guide/i18n_keys.txt
   0d8e3f4f945ecf041237146338ec39f46b7bf3a828e43b0053fe31704d288fa8  go/internal/web/ai/guide/i18n.json
   02764f4d54caeaf2c676bece286b1a7981cb9fc9f521f798c79626fb00d4096e  go/internal/web/ai/guide/templates/guide_shared.tmpl
   7f46022d36cb97fe06e982898de52819d99cdd9f7f6a87f63ab9d181d9d9c635  go/internal/web/ai/guide_testutil_test.go
   fd085871ff740ba6690d2fd8f3e81f6513173b06691c63c18abd9dce0d2b46e2  go/internal/web/ai/guide_common_test.go
   e1f36b9f0f461c7c203a700729126db6b9b27d148272397d072d679244a7f117  go/internal/web/ai/guide_data_test.go
   7fb3a5c468427474a1d1f011214269441f2b9a79dd5bdd0c87e355c3fc98e145  go/cmd/ubyhost-web/register_web_ai_guide.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1440 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/ai cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/ai/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all (gofmt lists nothing, build and vet are silent). Anything printed: STOP (§8). Commit "1440 step 2".

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1440 && chown postgres /var/tmp/pg1440 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1440/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1440/data -o "-p 55432 -k /var/tmp/pg1440" -l /var/tmp/pg1440/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres go test ./internal/web/ai/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
   ```

   Expected: two lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai	<seconds>s` and `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	<seconds>s`. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres go test ./internal/web/ai/ -count=1 -v -run '^TestGuideParseID$|^TestGuideStamp$|^TestGuideRoutesUniqueAndPoolFree$|^TestGuideTemplatesUseKnownKeys$|^TestGuideCatalogHasEveryKey$|^TestGuideCatalogMatchesGuideImport$|^TestGuideClean$|^TestGuideNextOpenAndProgress$|^TestGuidePyStripAndTruncate$|^TestGuideDataLayer$|^TestGuideHomeOwnership$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of 11 tests (times differ) and a final `ok` line; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestGuideParseID (0.NNs)
   --- PASS: TestGuideStamp (0.NNs)
   --- PASS: TestGuideRoutesUniqueAndPoolFree (0.NNs)
   --- PASS: TestGuideTemplatesUseKnownKeys (0.NNs)
   --- PASS: TestGuideCatalogHasEveryKey (0.NNs)
   --- PASS: TestGuideCatalogMatchesGuideImport (0.NNs)
   --- PASS: TestGuideClean (0.NNs)
   --- PASS: TestGuideNextOpenAndProgress (0.NNs)
   --- PASS: TestGuidePyStripAndTruncate (0.NNs)
   --- PASS: TestGuideDataLayer (0.NNs)
   --- PASS: TestGuideHomeOwnership (0.NNs)

5. Write the report (§9), set `Status: review` and commit "1440 step 5". Open one PR titled "1440: Go guest guide editor, part 1: shared gate, ownership check, data rules, catalog and test helpers" with the PR text of §2 in its description.

## 5. Do not touch

`go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/internal/anthropic/`, `go/internal/guideimport/`, `go/internal/web/properties/`, `go/cmd/ubyhost-web/main.go`, `registry.go` and every other `register_*.go`, `App/` (no Python file), `docs/context/*`, and every file in `go/internal/web/ai/` that is not in §3 (the other thread's `havel*.go`, `leon_setup*.go`). AGENTS.md rules 3 (nothing from a real host or guest in a fixture) and 4 (no new dependency).

## 6. Commands

Exactly the commands of §4 (steps 2 and 4). No test-map row exists yet for `go/internal/web/ai`; the coordinator adds one from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | tail -30` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 9 files.
- [ ] Step 2 printed nothing (gofmt, build and vet clean).
- [ ] Step 4 printed `ok` for both packages, and each of the 11 named tests printed `--- PASS` (none `SKIP`, none `FAIL`) on PostgreSQL.
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

Write `docs/tasks/1440-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git diff --stat main...HEAD | tail -20`; `origin/main...HEAD` if there is no local `main`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of: `guide_common.go` (`enter` must run CSRF, then the int check, then login; `home` must scope by `owner_user_id IS NOT DISTINCT FROM <workspace>` and refuse an archived property), `guide_data.go` (every query that takes an item or photo id also takes the apartment id; `deletePhoto` removes the file only as a best effort because the Go container mounts `/data` read-only, the Python `purge_orphans` sweep removes what is left; `ensureToken` never replaces a token). Everything else is mechanical. Known and accepted: `ensureDefaults` and `ensureToken` write on a GET page (Python does too).

## Owner steps

None: nothing is switched on.
