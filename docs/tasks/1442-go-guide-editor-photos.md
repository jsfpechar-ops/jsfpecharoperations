# 1442: Go guest guide editor, part 3: show and delete a card photo

Status: review
Depends on: 1440 | Base commit: 68c0e0985 | Branch: task/1442-go-guide-editor-photos
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the two photo routes of `App/app/routes/guest_guide.py` that Go can serve to `go/internal/web/ai`: show one stored guide photo (`GET /apartments/{id}/guide/{item}/photos/{photo}`) and delete one (`POST .../photos/{photo}/delete`). Adding a photo (`POST .../{item}/photos`) stays on Python: brief 1447 (blocked) says why.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (guide pages only); 2 privacy: no new personal-data field, no new retention line, no outbound request; 3 fixtures are made up (`@example.test`, test-only secrets); 4 no new dependency (stdlib, pgx and packages already in `go.mod`); 5 plain PostgreSQL through `pgxpool`, the Python SQL with `$n` placeholders; 6 light mode, the forms work without JavaScript (they post plain forms); 7 and 10 see §7.

**PR text (hard rule 2):** no new outbound request and no new personal-data field (guide photos are host-written, shown to guests, not encrypted: `App/app/guide_photos.py` docstring). The routes read files from `$UBYHOST_DATA_DIR/guide_photos` and delete rows.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1442-files/<repo path>.txt`.

| sha256 | file | action | lines |
|---|---|---|---|
| `65acf209521f639de291dd3091d74f101b76106828f7f1def96006b93f70502c` | `go/internal/web/ai/guide_photos.go` | create | 77 |
| `4d17ac69a7e00bbe37a93ff90e64f11ad13e270549aa2202a696e70d34c08f7a` | `go/internal/web/ai/guide_photos_test.go` | create | 82 |

**How the code is built (for the reviewer; the executor reads no Go file, it only copies and runs).** The routes register through the table in `guide_common.go` (`guideAdd` in an `init()`), and `go/cmd/ubyhost-web/register_web_ai_guide.go` (brief 1440) hands them to `registerRoutes`; no other file of `go/cmd` changes. Every handler starts with `s.enter(w, r)`, which runs in FastAPI's order: for a POST `hostweb.CSRF` (header or `_csrf` field, multipart too), then the int path parameters (`422` when one is not an int), then `hostweb.Login` (`auth.require_login`), then `s.home(w, q)` (`_home`: the property of the signed-in workspace, not archived, else `404`). Redirects are `q.back` (`admin_helpers.back`, Starlette quoting), flashes are `q.flash(key, params)` from the guide catalog `guide/i18n.json`. Pages are `layout.Render` through `s.render` (host layout shell, `Cache-Control: no-store`). Every package-level name of these files starts with `guide`, so it cannot meet a name in the files of the other thread that works in `go/internal/web/ai` (`havel*.go`, `leon_setup*.go`); those files are not yours and not read.

**Parity notes:**

| Route | Python | Go |
|---|---|---|
| `GET /apartments/{id}/guide/{item}/photos/{photo}` | `guide_photo_file` 424-434; `guide_photos.get` 55-62, `path_for` 64-65 | `photoFile` |
| `POST /apartments/{id}/guide/{item}/photos/{photo}/delete` | `guide_photo_delete` 437-445; `guide_photos.delete` 98-104 | `photoDelete`, `deletePhoto` (brief 1440) |

- The photo must belong to the card in the URL and the card to the host's property (`guide_photos.get` joins `guide_item.apartment_id`); a missing row or file is `404`. The file name from the database is reduced to its base name, so it cannot leave the folder.
- The file is served as `image/jpeg` with `Cache-Control: private, max-age=3600` (`FileResponse` headers). `http.ServeContent` adds `Last-Modified` and range support; Python's `FileResponse` also sends an `ETag`, Go does not (a conditional request still works through `Last-Modified`).
- **Read-only volume.** `deploy/lightsail/docker-compose.yml` mounts `ubyhost-data:/data:ro` in the Go service. Deleting the row works; removing the file is a best effort that fails silently, and the Python scheduler's `guide_photos.purge_orphans` (App/app/scheduler.py 284) deletes files no row names once they are an hour old. A deleted photo is therefore unreachable at once (no row) and its file is gone within about an hour of the next sweep. The owner decides separately whether the Go container gets a writable `/data` when the upload moves too.

**Known differences from Python, shared by every Go web area (not fixed here):** a missing or foreign record answers `404 {"detail":"Not Found"}` (and a non-integer id `422`), where Python shows the branded error page to a browser; `HEAD` and a wrong method answer `405` JSON (Python too); Go sets `Cache-Control` as the Python page routes do (`no-store`), and the `m.wrap` default `no-store, private` covers redirects.

**Anchors that must exist verbatim** (step 0): the two function lines in `App/app/routes/guest_guide.py`.

**Verified by the brief writer (in a throwaway worktree of this repo, sidecars copied exactly as step 1 does):** the test PASSes on PostgreSQL 16 and covers: a photo of the owner (bytes, `Content-Type`, `Cache-Control`), a row without a file, an unknown id, a signed-out request, another account, a photo on another card of the same property, a file name `../../etc/passwd`, delete by another account (the row stays), delete by the owner (row and file gone, another file untouched), a second delete (`404`). Mutation: dropping the apartment join of `photo()` made the Go test fail.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/ai/guide_photos.go` | create | two routes: photo file, photo delete |
| `go/internal/web/ai/guide_photos_test.go` | create | route tests |
| `docs/tasks/1442-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1442-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints `task/1442-go-guide-editor-photos`.
   - `grep -cF "def guide_photo_file(request: Request, apartment_id: int, item_id: int, photo_id: int):" App/app/routes/guest_guide.py | tail -1` prints `1`.
   - `grep -cF "def guide_photo_delete(request: Request, apartment_id: int, item_id: int, photo_id: int):" App/app/routes/guest_guide.py | tail -1` prints `1`.
   - `ls go/internal/web/ai/guide_common.go go/internal/web/ai/guide_data.go go/cmd/ubyhost-web/register_web_ai_guide.go 2>&1 | tail -5` lists all three (brief 1440 is on this branch), and the files of §3 for this brief do not exist yet (`ls` says "No such file").
   - `find docs/tasks/1442-files -name '*.txt' | wc -l | tail -1` prints `2`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1442-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   65acf209521f639de291dd3091d74f101b76106828f7f1def96006b93f70502c  go/internal/web/ai/guide_photos.go
   4d17ac69a7e00bbe37a93ff90e64f11ad13e270549aa2202a696e70d34c08f7a  go/internal/web/ai/guide_photos_test.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1442 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/ai cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/ai/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all (gofmt lists nothing, build and vet are silent). Anything printed: STOP (§8). Commit "1442 step 2".

3. PostgreSQL: as brief 1440 step 3 (the server on port 55440 may still run: `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1440/data status' | tail -1` says `server is running`; if stopped, run only the `pg_ctl ... start` part of that step). Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres` below. No server: write "CI only" in the report and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres go test ./internal/web/ai/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
   ```

   Expected: two lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai	<seconds>s` and `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	<seconds>s`. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres go test ./internal/web/ai/ -count=1 -v -run '^TestGuidePhotoFileAndDelete$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of 1 tests (times differ) and a final `ok` line; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestGuidePhotoFileAndDelete (0.NNs)

5. Write the report (§9), set `Status: review` and commit "1442 step 5". Open one PR titled "1442: Go guest guide editor, part 3: show and delete a card photo" with the PR text of §2 in its description.

## 5. Do not touch

As brief 1440 §5, plus every file of briefs 1440, 1441 and 1443 to 1446.

## 6. Commands

Exactly the commands of §4 (steps 2 and 4). No test-map row exists yet for `go/internal/web/ai`; the coordinator adds one from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | tail -30` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 2 files.
- [ ] Step 2 printed nothing (gofmt, build and vet clean).
- [ ] Step 4 printed `ok` for both packages, and each of the 1 named tests printed `--- PASS` (none `SKIP`, none `FAIL`) on PostgreSQL.
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

Write `docs/tasks/1442-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git diff --stat main...HEAD | tail -20`; `origin/main...HEAD` if there is no local `main`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `guide_photos.go` in full: it opens files from disk. Check the ownership chain (`s.home`, then `s.photo(apt, item, photo)` with the apartment join), `filepath.Base` on the stored name, that only regular files are served, and that `photoDelete` never errors when the file cannot be removed.

## Owner steps

None: nothing is switched on.
