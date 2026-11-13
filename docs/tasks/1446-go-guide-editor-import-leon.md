# 1446: Go guest guide editor, part 7: queue a listing import and the Leon switch page

Status: todo
Depends on: 1445 | Base commit: 68c0e0985 | Branch: task/1446-go-guide-editor-import-leon
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add three routes of `App/app/routes/guest_guide.py` to `go/internal/web/ai`: queue a Booking or Airbnb listing import (`POST /apartments/{id}/guide/import`) and the host's Leon switch (`GET` and `POST /apartments/{id}/leon`), with the Leon page template and the Go copy of `guest_guide_import.normalise_url`, checked against the real Python by a golden file.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (guide pages only); 2 privacy: no new personal-data field, no new retention line, the import route makes none (see PR text); 3 fixtures are made up (`@example.test`, test-only secrets); 4 no new dependency (stdlib, pgx and packages already in `go.mod`); 5 plain PostgreSQL through `pgxpool`, the Python SQL with `$n` placeholders; 6 light mode, the forms work without JavaScript (they post plain forms); 7 and 10 see §7.

**PR text (hard rule 2):** no new outbound request. `POST .../guide/import` only checks the pasted links and inserts `guide_import` rows with status `queued`; the existing import job (`go/internal/guideimport`, or the Python worker while it still owns the kind) fetches them later from `https://api.apify.com/v2/acts/` with the owner's token, exactly as before. Switching Leon on stores the terms version the host ticked and an audit row; no model is called. No new personal-data field: `apartment.leon_terms_*` and `audit` already exist.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1446-files/<repo path>.txt`.

| sha256 | file | action | lines |
|---|---|---|---|
| `701ac7bbbd4d37a0c39c1d1ab3f8a8b3772fb26a91aa06fe0a79634955254384` | `go/internal/web/ai/guide_import.go` | create | 242 |
| `2f67e8bbc43c0e6d150c9abc5b954964f8d4f347917c1518bc3dae60aa79040e` | `go/internal/web/ai/guide_import_test.go` | create | 138 |
| `fe1a6f303c73a9f1e0ff22a953dd3055372c6b888b621823b0987045cb17e6d9` | `go/internal/web/ai/testdata/guide_import_urls.json` | create | 228 |
| `0f6c711f21b64a2323db2e9aac53036a03dba6ca0e8b82128f29029aed814a92` | `go/internal/web/ai/guide_leon.go` | create | 169 |
| `e278cecf3ce690f5a77895f299b1e60122cd82f46013e6e3a18158d50f4bde86` | `go/internal/web/ai/guide/templates/guide_leon.tmpl` | create | 47 |
| `ac8433f9ea35844f56d36bc4574ce6e500ad28fc30e0fbe01d7b49819be7d815` | `go/internal/web/ai/guide_leon_test.go` | create | 145 |
| `8e97ab00c9e2457d9f27841869c9bbf9458a8263893ad306abf7180a6833bdb8` | `App/scripts/guide_import_urls_golden.py` | create | 109 |
| `156374486ca00c885160a22ba5688bf7ddad24fcd2c7a83c3893ea3991cf8dd6` | `App/tests/test_go_guide_import_urls.py` | create | 11 |

**How the code is built (for the reviewer; the executor reads no Go file, it only copies and runs).** The routes register through the table in `guide_common.go` (`guideAdd` in an `init()`), and `go/cmd/ubyhost-web/register_web_ai_guide.go` (brief 1440) hands them to `registerRoutes`; no other file of `go/cmd` changes. Every handler starts with `s.enter(w, r)`, which runs in FastAPI's order: for a POST `hostweb.CSRF` (header or `_csrf` field, multipart too), then the int path parameters (`422` when one is not an int), then `hostweb.Login` (`auth.require_login`), then `s.home(w, q)` (`_home`: the property of the signed-in workspace, not archived, else `404`). Redirects are `q.back` (`admin_helpers.back`, Starlette quoting), flashes are `q.flash(key, params)` from the guide catalog `guide/i18n.json`. Pages are `layout.Render` through `s.render` (host layout shell, `Cache-Control: no-store`). Every package-level name of these files starts with `guide`, so it cannot meet a name in the files of the other thread that works in `go/internal/web/ai` (`havel*.go`, `leon_setup*.go`); those files are not yours and not read.

**Parity notes:**

| Route | Python | Go |
|---|---|---|
| `POST /apartments/{id}/guide/import` | `guide_import` 180-195; `guest_guide_import.request_imports` 163-191, `normalise_url` 80-108, `runs_this_month` 140-144 | `importPost`, `requestImports`, `guideNormaliseURL`, `runsThisMonth` |
| `GET /apartments/{id}/leon` | `leon_page` 125-145, `_leon_utc` 121-122 | `leonPage` |
| `POST /apartments/{id}/leon` | `leon_save` 148-177 | `leonSave`, `setLeon` |

- **Same checks, same order, same keys as `request_imports`:** import off (no `UBYHOST_APIFY_TOKEN`), no link, a bad link, two links of one source, an import already queued or running, a source already imported (a `failed` run does not use a source up), the monthly run budget (`UBYHOST_APIFY_MONTHLY_RUNS`, default 40, `0` means no cap; the count is `lock_api_usage` of the UTC month). Every check runs before the first row is written. The links are cut to 2048 characters first. `next=leon` sends the answer to `/apartments/{id}/leon/setup/import` (the wizard, another thread), else to `.../guide#import`.
- **`normalise_url` is checked against Python:** `App/scripts/guide_import_urls_golden.py` (new) writes `testdata/guide_import_urls.json` (52 links from the real function, including hosts with `@`, ports, IPv4, brackets, whitespace, Unicode digits); `TestGuideNormaliseURLMatchesPython` replays it. One difference, on purpose: where Python's `urlsplit` raises `ValueError` (a port that is not a number or above 65535, an unbalanced `[`), the route answers 500 in Python and Go refuses the link as a bad link (`guide_import_link`).
- `leon_save`: `action=off` is always allowed (and audited as `leon_switched_off`); `action=on` needs Leon offered (`404` otherwise, as in brief 1445), the `terms=1` tick (else the flash `flash.error.leon_terms`, back to the page or, with `next=setup`, to `.../leon/setup/switch_on`), then stores `leon_terms_version = 2026-10-25`, the time and the **signed-in account** id (not the workspace) and audits `leon_terms_accepted`.
- `leon_page`: `404` unless Leon is offered; state `off` or `terms` redirects to `/apartments/{id}/leon/setup` (the wizard, another thread); else the page with the version, time and e-mail of who accepted. Python prints `None` when that account has no e-mail; Go prints nothing.

**Known differences from Python, shared by every Go web area (not fixed here):** a missing or foreign record answers `404 {"detail":"Not Found"}` (and a non-integer id `422`), where Python shows the branded error page to a browser; `HEAD` and a wrong method answer `405` JSON (Python too); Go sets `Cache-Control` as the Python page routes do (`no-store`), and the `m.wrap` default `no-store, private` covers redirects.

**Anchors that must exist verbatim** (step 0): the three function lines in `App/app/routes/guest_guide.py`.

**Verified by the brief writer (in a throwaway worktree of this repo, sidecars copied exactly as step 1 does):** the six named tests PASS on PostgreSQL 16; the 52 golden links agree with Python (run on the real module); the import tests cover empty, blank, bad, same source, both links (two rows, `Location` ending `#import`), busy, source limit, a failed source retried, the run budget at 3, `next=leon`, a stranger (`404`), import off, and the UTC month; the Leon tests cover off, not offered, no tick (plain and wizard), on (columns and one audit row), the page, old terms, a stranger and off (audited); the Leon page body equals the Jinja render of `leon_settings.html` for state `waiting` (whitespace between tags normalised); the `off`/`terms` branches (unreachable through the route) are rendered by `TestGuideLeonTemplateOffAndTermsRender`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/ai/guide_import.go` | create | one route (queue an import), normalise_url, request_imports |
| `go/internal/web/ai/guide_import_test.go` | create | golden and route tests |
| `go/internal/web/ai/testdata/guide_import_urls.json` | create | generated from the Python normalise_url (do not edit) |
| `go/internal/web/ai/guide_leon.go` | create | two routes: Leon page, Leon switch |
| `go/internal/web/ai/guide/templates/guide_leon.tmpl` | create | Go twin of leon_settings.html |
| `go/internal/web/ai/guide_leon_test.go` | create | route tests |
| `App/scripts/guide_import_urls_golden.py` | create | writes/checks testdata/guide_import_urls.json |
| `App/tests/test_go_guide_import_urls.py` | create | runs the script with --check |
| `docs/tasks/1446-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1446-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints `task/1446-go-guide-editor-import-leon`.
   - `grep -cF "async def guide_import(request: Request, apartment_id: int):" App/app/routes/guest_guide.py | tail -1` prints `1`.
   - `grep -cF "def leon_page(request: Request, apartment_id: int):" App/app/routes/guest_guide.py | tail -1` prints `1`.
   - `grep -cF "async def leon_save(request: Request, apartment_id: int):" App/app/routes/guest_guide.py | tail -1` prints `1`.
   - `ls go/internal/web/ai/guide_common.go go/internal/web/ai/guide_data.go go/internal/web/ai/guide_index.go go/cmd/ubyhost-web/register_web_ai_guide.go 2>&1 | tail -5` lists all four (briefs 1440 and 1445 are on this branch), and `ls go/internal/web/ai/guide_leon.go go/internal/web/ai/guide_import.go 2>&1 | tail -3` says "No such file" twice.
   - `find docs/tasks/1446-files -name '*.txt' | wc -l | tail -1` prints `8`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1446-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   701ac7bbbd4d37a0c39c1d1ab3f8a8b3772fb26a91aa06fe0a79634955254384  go/internal/web/ai/guide_import.go
   2f67e8bbc43c0e6d150c9abc5b954964f8d4f347917c1518bc3dae60aa79040e  go/internal/web/ai/guide_import_test.go
   fe1a6f303c73a9f1e0ff22a953dd3055372c6b888b621823b0987045cb17e6d9  go/internal/web/ai/testdata/guide_import_urls.json
   0f6c711f21b64a2323db2e9aac53036a03dba6ca0e8b82128f29029aed814a92  go/internal/web/ai/guide_leon.go
   e278cecf3ce690f5a77895f299b1e60122cd82f46013e6e3a18158d50f4bde86  go/internal/web/ai/guide/templates/guide_leon.tmpl
   ac8433f9ea35844f56d36bc4574ce6e500ad28fc30e0fbe01d7b49819be7d815  go/internal/web/ai/guide_leon_test.go
   8e97ab00c9e2457d9f27841869c9bbf9458a8263893ad306abf7180a6833bdb8  App/scripts/guide_import_urls_golden.py
   156374486ca00c885160a22ba5688bf7ddad24fcd2c7a83c3893ea3991cf8dd6  App/tests/test_go_guide_import_urls.py
   EOF
   ```

   Every line must end with `: OK`. Then commit "1446 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/ai cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/ai/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all (gofmt lists nothing, build and vet are silent). Anything printed: STOP (§8). Commit "1446 step 2".

3. PostgreSQL: as brief 1440 step 3 (the server on port 55432 may still run: `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1440/data status' | tail -1` says `server is running`; if stopped, run only the `pg_ctl ... start` part of that step). Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres` below. No server: write "CI only" in the report and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres go test ./internal/web/ai/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
   ```

   Expected: two lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai	<seconds>s` and `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	<seconds>s`. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres go test ./internal/web/ai/ -count=1 -v -run '^TestGuideNormaliseURLMatchesPython$|^TestGuideImportRoute$|^TestGuideRunsThisMonthIsUTC$|^TestGuideLeonUTC$|^TestGuideLeonRoutes$|^TestGuideLeonTemplateOffAndTermsRender$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of 6 tests (times differ) and a final `ok` line; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestGuideNormaliseURLMatchesPython (0.NNs)
   --- PASS: TestGuideImportRoute (0.NNs)
   --- PASS: TestGuideRunsThisMonthIsUTC (0.NNs)
   --- PASS: TestGuideLeonUTC (0.NNs)
   --- PASS: TestGuideLeonRoutes (0.NNs)
   --- PASS: TestGuideLeonTemplateOffAndTermsRender (0.NNs)

5. Generated file and Python test (from `App/`; needs the application environment: `ls .venv/bin/python` exists). Else write "CI only" in the report and skip this step:

   ```bash
   cd App && .venv/bin/python scripts/guide_import_urls_golden.py --check 2>&1 | tail -5; .venv/bin/python -m pytest tests/test_go_guide_import_urls.py -q --tb=short -x 2>&1 | tail -30
   ```

   Expected: the script prints nothing (no `stale:` line); pytest ends with `1 passed`. A `stale:` line: STOP (Python moved; never edit the JSON to match). Commit "1446 step 5".

6. Write the report (§9), set `Status: review` and commit "1446 step 6". Open one PR titled "1446: Go guest guide editor, part 7: queue a listing import and the Leon switch page" with the PR text of §2 in its description.

## 5. Do not touch

As brief 1440 §5, plus every file of briefs 1440 to 1445. `go/internal/guideimport` is only imported (`ConfigFromEnv`). The wizard routes under `/apartments/{id}/leon/setup` belong to the other thread.

## 6. Commands

Exactly the commands of §4 (steps 2 and 4, and the Python commands of step 5). No test-map row exists yet for `go/internal/web/ai`; the coordinator adds one from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | tail -30` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 8 files.
- [ ] Step 2 printed nothing (gofmt, build and vet clean).
- [ ] Step 4 printed `ok` for both packages, and each of the 6 named tests printed `--- PASS` (none `SKIP`, none `FAIL`) on PostgreSQL.
- [ ] Step 5 printed no `stale:` line and `1 passed` (or the report says "CI only" with the reason).
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

Write `docs/tasks/1446-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git diff --stat main...HEAD | tail -20`; `origin/main...HEAD` if there is no local `main`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `guide_import.go` (everything that decides whether a row is queued: `guideNormaliseURL`, the order and keys in `requestImports`, the budget check; the inserted URL is the rebuilt one, never the pasted text) and `guide_leon.go` (`leonSave`: the ownership check precedes every write, the terms tick is required for `on`, `setLeon` writes the version constant and the signed-in account). The templates are markup only.

## Owner steps

Nothing is switched on by merging. When briefs 1440 to 1446 are merged and you want these pages on Go:

1. **UX gate first (the orchestrator does this, not you):** on the staging server only, with a test property, open these pages at 390, 768 and 1280 px and send the screenshots: the guide overview, one card (a built-in one and a custom draft with photos), the QR page, a Quick answers step, the done page and the Leon page. Production is not touched until the gate has passed (brief 1412 is the pattern).
2. Put the new paths into `UBYHOST_GO_PATHS` (the line in `.env` on the Lightsail server; keep the existing value and add these, space-separated, inside the double quotes):
   `/apartments/*/guide /apartments/*/guide/cards /apartments/*/guide/import /apartments/*/guide/qr /apartments/*/guide/qr.png /apartments/*/guide/qr/rotate /apartments/*/guide/quick /apartments/*/guide/quick/* /apartments/*/leon /apartments/*/guide/*/photos/* /apartments/*/guide/*/photos/*/delete`
3. Do **not** add `/apartments/*/guide/*`, `/apartments/*/guide/*/discard`, `/apartments/*/guide/*/skip` or `/apartments/*/guide/*/delete` yet. Caddy's `path` matches any single segment and ignores the method: `/apartments/*/guide/*` would also send `GET /apartments/<id>/guide/questions` (a Python page, `guest_questions.py`) to Go, which answers `404`. Add the four card paths together when the guest questions pages are on Go too.
4. Do not add `/apartments/*/guide/*/photos` (without the trailing `/*`): adding a photo stays on Python (brief 1447).
5. `/apartments/*/leon` is the exact path; the wizard pages `/apartments/*/leon/setup...` stay on Python or move with their own brief.
6. Run `docker compose up -d` as for any `.env` change; check with the QR page and one card save on staging. Rollback is removing the paths again and `docker compose up -d`.
