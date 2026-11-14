# 1572: Go cleaning host pages, part 3: property settings (instructions) and the cleaner share links

Status: todo
Depends on: 1570, 1571 | Base commit: current tip of the working branch | Branch: task/1572-go-cleaning-settings-shares
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1572 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1572 step'` and `git show --stat <commit>`, never a fixed base commit.

## 1. Objective

Add the property cleaning settings (`GET` and `POST /cleaning/properties/{id}`: the instructions text and the read-only door-code panel) and the cleaner share links (`GET` and `POST /cleaning/shares`, `cleaning.new_share`) to `go/internal/web/cleaning`. Dormant until the owner routes the paths.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (cleaning pages only); 2 privacy: no new personal-data field, no new retention line, no outbound request; 3 fixtures are made up (`@example.test`, test-only keys); 4 no new dependency (stdlib, pgx and packages already in `go.mod`); 5 plain PostgreSQL through `pgxpool`, the Python SQL with `$n` placeholders, no schema change; 6 light mode, the forms work without JavaScript; 11 Go first (this brief is the Go port; no file under `App/app/` changes).

**PR text (hard rule 2):** no new outbound request and no new personal-data field. A share link carries a 256-bit random token; only its SHA-256 is stored (as Python), the link is shown once, and it expires after 30 days.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1572-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `e27038ed683a11e81c3be577cbfb005282bf8bce5f7ccb94970a234ccac23227` | `go/cmd/ubyhost-web/register_web_cleaning_host_settings_test.go` | create | 24 |
| `1046a4f716815efe8d949286f8ce7986e9e30ca3e53ea03b649e10571827b88b` | `go/internal/web/cleaning/host_settings.go` | create | 162 |
| `009d9fd0ee0abcab96181c953060b48aace10a2782eaa6b1fc6d485d1408c2cc` | `go/internal/web/cleaning/host_settings_test.go` | create | 232 |
| `783968952548047468c3d2f06d998c0db83676beb3cc0a2fdbbe1868c0f2081b` | `go/internal/web/cleaning/host_shares.go` | create | 189 |
| `96f2858b2059292ab35123d8049e7b9850025e400ed8b6cdadafd3d5c242a7c7` | `go/internal/web/cleaning/hosttemplates/cleaning_settings.tmpl` | create | 29 |
| `601ef073d5e38c9f20d0fb25f15354bb8ecfed0c446d55d556922e692adda393` | `go/internal/web/cleaning/hosttemplates/cleaning_shares.tmpl` | create | 13 |

**How the code is built.** `host_settings.go` holds `renderSettings`, which brief 1573 reuses for its error answers, and `ensureProperty` (the `execer` interface accepts a pool and a transaction). `host_shares.go` holds the share page and `newShare`. The settings page shows door-code state through the existing read-only `code()` of `model.go`; no lock call is made.

**Parity notes (Python `App/app/routes/cleaning.py` unless named):**

| Route | Python | Go |
|---|---|---|
| `GET /cleaning/properties/{id}` | `property_settings` 274-279, `_settings` 250-262, template `cleaning_settings.html` | `(*hostServer).propertySettings`, `renderSettings` |
| `POST /cleaning/properties/{id}` | `save_property` 282-294, `cleaning.save_settings` (App/app/cleaning.py 166-175) | `(*hostServer).saveProperty`, `saveInstructions`, `ensureProperty` |
| `GET /cleaning/shares` | `share_settings` 332-335, `_shares` 318-329, template `cleaning_shares.html` | `(*hostServer).shareSettings`, `renderShares` |
| `POST /cleaning/shares` | `create_share` 338-351, `cleaning.new_share` (App/app/cleaning.py 293-308) | `(*hostServer).createShare`, `newShare` |

Details that are easy to get wrong and are tested: the instructions are stripped and limited to 10000 characters (`notes` error, 422, the typed text comes back unstripped); the row of `cleaning_property` is created on the first save; the settings page shows the stored code (a TTLock code with the keypad `#`), a pending or failed code, a failed revocation and the effective check-out and check-in hours (`—` when empty); a share needs at least one property and every id must be one of the host's active properties, otherwise `property` (422) and no row; a non-numeric id is also `property`; staging without login answers `login_required` before the ids are read; the link is `UBYHOST_PUBLIC_BASE_URL` + `/cleaning/shared/<token>` (never the Host header), the token is `secrets.token_urlsafe(32)` (43 characters), `token_hash` is its SHA-256, `expires_at` is now + 30 days with Python's `isoformat()` shape, `created_at` the usual stamp; duplicate ids make one `cleaning_share_property` row each; the list shows the host's live shares, newest first.

**Known differences from Python, shared by every Go web area (not fixed here):** a missing or foreign record answers `404 {"detail":"Not Found"}` (and a non-integer id `422`), where Python shows the branded error page to a browser; `HEAD` is served by the `GET` pattern; a repeated query key reads the last value in the code written here (as Starlette does) but the older `buildPayload` reads the first. Python's `int()` also accepts `1_0` and a leading `+`; Go's parser accepts the sign only.

**Paths that become fully served by Go:** `/cleaning/shares` (GET and POST), `/cleaning/properties/*` (GET and POST, one segment; the `code/*` paths below it are brief 1573). **Goes live on deploy if** these paths are already routed to Go (assumed not). Do not route `/cleaning/properties/*` before brief 1573 is merged only if the prefix form `/cleaning/properties/*/*` is used; the single-segment path is complete now.

**Anchors that must exist verbatim** (step 0): the Python function lines and the Go function lines listed there.

**Verified by the brief writer:** (filled in after the check run)

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_cleaning_host_settings_test.go` | create | route registration test |
| `go/internal/web/cleaning/host_settings.go` | create | property settings page and save, `ensureProperty` |
| `go/internal/web/cleaning/host_settings_test.go` | create | route tests |
| `go/internal/web/cleaning/host_shares.go` | create | share page, `newShare` |
| `go/internal/web/cleaning/hosttemplates/cleaning_settings.tmpl` | create | Go twin of cleaning_settings.html |
| `go/internal/web/cleaning/hosttemplates/cleaning_shares.tmpl` | create | Go twin of cleaning_shares.html |
| `docs/tasks/1572-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1572-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `git log --oneline --grep='^1570 step' | wc -l | tail -1` prints a number of 1 or more (brief 1570 is on this branch).
   - `git log --oneline --grep='^1571 step' | wc -l | tail -1` prints a number of 1 or more (brief 1571 is on this branch).
   - `grep -cF "def property_settings(request: Request, property_id: int):" App/app/routes/cleaning.py | tail -1` prints `1`.
   - `grep -cF "async def save_property(request: Request, property_id: int):" App/app/routes/cleaning.py | tail -1` prints `1`.
   - `grep -cF "def share_settings(request: Request):" App/app/routes/cleaning.py | tail -1` prints `1`.
   - `grep -cF "async def create_share(request: Request):" App/app/routes/cleaning.py | tail -1` prints `1`.
   - `grep -cF "def new_share(owner_id: int | None, property_ids: list[int]) -> tuple[int, str]:" App/app/cleaning.py | tail -1` prints `1`.
   - `grep -cF "func parseHostForm(" go/internal/web/cleaning/host_events.go | tail -1` prints `1`.
   - `grep -cF "func formDict(" go/internal/web/cleaning/host_events.go | tail -1` prints `1`.
   - `grep -cF "func (s *hostServer) page(" go/internal/web/cleaning/host.go | tail -1` prints `1`.
   - `ls go/internal/web/cleaning/host_settings.go 2>&1 | tail -1` says "No such file" (nothing of this brief exists yet).
   - `find docs/tasks/1572-files -name '*.txt' | wc -l | tail -1` prints `6`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1572-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -9
   e27038ed683a11e81c3be577cbfb005282bf8bce5f7ccb94970a234ccac23227  go/cmd/ubyhost-web/register_web_cleaning_host_settings_test.go
   1046a4f716815efe8d949286f8ce7986e9e30ca3e53ea03b649e10571827b88b  go/internal/web/cleaning/host_settings.go
   009d9fd0ee0abcab96181c953060b48aace10a2782eaa6b1fc6d485d1408c2cc  go/internal/web/cleaning/host_settings_test.go
   783968952548047468c3d2f06d998c0db83676beb3cc0a2fdbbe1868c0f2081b  go/internal/web/cleaning/host_shares.go
   96f2858b2059292ab35123d8049e7b9850025e400ed8b6cdadafd3d5c242a7c7  go/internal/web/cleaning/hosttemplates/cleaning_settings.tmpl
   601ef073d5e38c9f20d0fb25f15354bb8ecfed0c446d55d556922e692adda393  go/internal/web/cleaning/hosttemplates/cleaning_shares.tmpl
   EOF
   ```

   Every line must end with `: OK`. Then commit "1572 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/cleaning cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/cleaning/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all (gofmt lists nothing, build and vet are silent). Anything printed: STOP (§8). Nothing changed, so no commit.

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if an earlier brief of this series left it running (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55570/data status' | tail -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55570 && chown postgres /var/tmp/pg55570 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55570/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55570/data -o "-p 55570 -k /var/tmp/pg55570" -l /var/tmp/pg55570/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55570/postgres` in the next steps. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands that need no database, and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55570/postgres go test ./internal/web/cleaning/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: two lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/cleaning	<seconds>s` and `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	<seconds>s`. The golden test of brief 1310 (`TestCleaningMatchesPython`) is part of the first package and must stay green. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55570/postgres go test ./internal/web/cleaning/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestHostPropertySettingsPage$|^TestHostSaveProperty$|^TestHostShares$|^TestCleaningHostSettingsRoutesRegistered$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of 4 tests (times differ) and two final `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestHostPropertySettingsPage (0.NNs)
   --- PASS: TestHostSaveProperty (0.NNs)
   --- PASS: TestHostShares (0.NNs)
   --- PASS: TestCleaningHostSettingsRoutesRegistered (0.NNs)

5. Write the report (§9), set `Status: review` in this file and commit "1572 step 5". Do not open a PR (one big PR mode); the owner or the orchestrator opens it with the PR text of §2.

## 5. Do not touch

`App/` (no Python file changes; the Python routes stay the live ones), `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, every file of briefs 1570 and 1571 and the existing files of the package. Hard rules of AGENTS.md: no secret or guest datum in a file or a log (the test data is made up), nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 2 and 4). No test-map row exists yet for `go/internal/web/cleaning` host pages; the coordinator adds one from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 6 files.
- [ ] The format, build and vet step printed nothing.
- [ ] The test step printed `ok` for both packages, and each of the 4 named tests printed `--- PASS` (none `SKIP`, none `FAIL`) on PostgreSQL.
- [ ] `git log --oneline --grep='^1572 step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1572 step') | tail -40` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed to `main`.
- [ ] UI: not applicable in this PR (rules 7 and 10): the pages are dormant (no path routes to them) and the Python-side browser tests cannot reach the Go service. The UX gate of rule 10 (`test_layout_lint_browser.py`, the 390, 768 and 1280 px screenshots of each page, a line per page in the PR) runs on staging before the owner adds the paths; see Owner steps.

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

Write `docs/tasks/1572-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git diff --stat` as in §7).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of: `host_settings.go` (`saveProperty`: 404 for a foreign property before any write; `renderSettings` only reads), `host_shares.go` (`newShare`: ids checked against the owner's properties, the token is random and only its hash is stored, the two inserts are one transaction; `renderShares`: the list is scoped by owner, the link is built from the configured public URL), the two templates (every form has `_csrf`).

## Owner steps

None: nothing is switched on. The path switch for the whole area is described in the owner steps of brief 1573 and must wait for it.
