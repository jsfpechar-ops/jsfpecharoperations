# 1447: Go guest guide editor, part 8: add a card photo (POST .../photos)

Status: todo
Tier: A (a file upload from a browser, decoded and written to disk)
Depends on: 1441 and 1442 (card routes and photo routes; both done), 1640 (writable data volume), 1641 (`imgproc.Clean`; its x/image dependency) | Base commit: current branch (One big PR mode) | Branch: current branch
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 55k tokens

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1447 step k`. Never create a branch, never push, never open a PR.

## 1. Objective

Port `guide_photo_add` (`App/app/routes/guest_guide.py` 402-421) and `guide_photos.add` (`App/app/guide_photos.py` 68-95) to Go, so the whole guide editor can move to Go. The owner chose option A on 2026-11-14: a writable data volume (brief 1640) and `golang.org/x/image` (brief 1641). The picture handling is `imgproc.Clean`; this brief is the route: checks, file write, row.

## 2. Context

Rules (AGENTS.md): 2 privacy: no new personal-data field and no new retention line (guide photos are host-written, shown to guests, not encrypted, files named by 32 random hex characters; `guide_photos.py` docstring); the pipeline removes EXIF and GPS. No new outbound request. 3 test pictures are generated in the test. 4 the dependency is approved and added by brief 1641 (this brief changes no `go.mod`). 5 plain PostgreSQL through `pgxpool`, `$n` placeholders. 11 Go first.

**PR text (hard rule 2):** a host uploads a JPEG, PNG or WebP of at most 10 MiB to a guide card; Go decodes it, removes all metadata, shrinks it to 1600 px and stores a JPEG under `$UBYHOST_DATA_DIR/guide_photos`. No new outbound request, no new personal data.

**Python, in order** (`guide_photo_add` then `add`): CSRF; login; the property is the host's (404); the card belongs to it (404); the form field `photo` is read (the last one wins) and must be a file, else `flash.error.guide_photo_type`; read at most 10 MiB + 1; the content type (before `;`, trimmed, lower case) must be one of `image/jpeg`, `image/jpg`, `image/png`, `image/webp` and the file at least 64 bytes, else `guide_photo_type`; over 10 MiB is `guide_photo_size`; six photos on the card is `guide_photo_limit`; a picture that cannot be decoded, is not JPEG/PNG/WebP, or has more than 40,000,000 pixels is `guide_photo_type`. Then the file is written as `<32 hex>.jpg` through `<32 hex>.tmp` and a rename, and the row `guide_photo (item_id, file_name, sort_order = max + 1, created_at)` is inserted. The answer is a 303 back to the card page with `msg=flash.guest_guide.photo_added`, or `err=<key>`.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1447-files/<repo path>.txt`.

| sha256 | file | action | lines |
|---|---|---|---|
| `c793b8258db04ac4fc4818c9eb27dfc707698c1fde5285ff741a592460514ec3` | `go/internal/web/ai/guide_photos_add.go` | create | 153 |
| `3a00e67097409030e2af28bf571f97acaf9e8d487e4867df1d55b6f73b889317` | `go/internal/web/ai/guide_photos_add_test.go` | create | 140 |

**How the code is built (for the reviewer).** `photoAdd` starts with `s.enter(w, r)` (CSRF, int path parameters, login; for a POST `enter` already parses the multipart form up to 32 MiB, so the CSRF field and the file are both there) and then `s.home`, `s.getItem`. `guideUpload` takes the last `photo` file part and reads at most 10 MiB + 1 bytes. `addPhoto` runs the checks in Python's order, calls `imgproc.Clean`, writes and renames the file, and inserts the row; when the insert fails the file is removed again. **Routing:** Go's `net/http` refuses the pattern `POST /apartments/{id}/guide/{item}/photos` next to the existing `POST /apartments/{id}/guide/quick/{step}` (both match `/guide/quick/photos`), so the route is not a new pattern: step 2 adds a `photos` case to `cardAction` (`POST /apartments/{id}/guide/{item}/{action}`), which dispatches `discard`, `skip` and `delete` already. The route table, the route list in `cmd/ubyhost-web` and the metrics labels do not change.

**Parity notes:**

| Route | Python | Go |
|---|---|---|
| `POST /apartments/{id}/guide/{item}/photos` | `guide_photo_add` 402-421; `guide_photos.add` 68-95 | `photoAdd`, `guideUpload`, `addPhoto` |

- The picture differences (one JPEG encode at quality 82, Catmull-Rom instead of Pillow bicubic, orientation read from JPEGs only, animated WebP refused) are listed in brief 1641 §2 and accepted there.
- An empty file chooser (filename empty) is not a file part in Go (`mime/multipart` treats it as a value) and an empty `UploadFile` in Starlette: both end in `flash.error.guide_photo_type`.
- The count check and the insert are not one transaction, as in Python: two uploads at the same moment could store a seventh photo. Accepted (same as Python).
- Python writes the file with the process umask (0644 here); Go writes mode 0644. The folder is created with 0755.
- A body over 20 MB is refused by Caddy (`request_body max_size 20MB`) before Go sees it; between 10 MiB and 20 MB Go answers `guide_photo_size`, like Python.

**Verified by the brief writer** in a throwaway copy of `go/` with these files, the edits of step 2 and the 1641 files, PostgreSQL 16 on a disposable port: `gofmt -l` empty, `go build ./...` and `go vet` clean, `go mod tidy -diff` empty, `go test ./internal/web/ai/ ./internal/imgproc/ -count=1` both `ok` with the database tests run (not skipped). `TestGuidePhotoAdd` covers: a 2000x1000 JPEG becomes 1600x800 with one row, sort order 1, a 36-character `.jpg` name and no temporary file left; a content type `IMAGE/JPEG; charset=x` is accepted and the second photo has sort order 2; refusals (no file field, `image/gif`, 63 bytes, text sent as `image/png`, 10 MiB + the JPEG) all redirect with `err=` and add no row; the seventh photo is refused; another account and a missing card are 404; a signed-out request goes to `/login`; six rows at the end.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/ai/guide_photos_add.go` | create | the route handler and `addPhoto` |
| `go/internal/web/ai/guide_photos_add_test.go` | create | `TestGuidePhotoAdd` |
| `go/internal/web/ai/guide_cards.go` | edit | `photos` case in `cardAction` (step 2) |
| `go/internal/web/ai/guide_photos.go` | edit | header comment only (step 2) |
| `go/internal/web/ai/guide_data.go` | edit | comment of `deletePhoto` only (step 2) |
| `docs/tasks/1447-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1447-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `grep -cF "async def guide_photo_add(request: Request, apartment_id: int, item_id: int):" App/app/routes/guest_guide.py | tail -1` prints `1`.
   - `ls go/internal/imgproc/imgproc.go go/internal/web/ai/guide_photos.go go/internal/web/ai/guide_cards.go 2>&1 | tail -3` lists all three (briefs 1641 and 1442 are on this branch); `ls go/internal/web/ai/guide_photos_add.go 2>&1 | tail -1` says "No such file".
   - `grep -c 'x/image v0.45.0' go/go.mod | tail -1` prints `1`.
   - `grep -cF "      - ubyhost-data:/data:ro" deploy/lightsail/docker-compose.yml | tail -1` prints `0` (brief 1640 is on this branch).
   - `grep -cF '		s.cardDelete(w, r)' go/internal/web/ai/guide_cards.go | tail -1` prints `1`.
   - `find docs/tasks/1447-files -name '*.txt' | wc -l | tail -1` prints `2`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1447-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -4
   c793b8258db04ac4fc4818c9eb27dfc707698c1fde5285ff741a592460514ec3  go/internal/web/ai/guide_photos_add.go
   3a00e67097409030e2af28bf571f97acaf9e8d487e4867df1d55b6f73b889317  go/internal/web/ai/guide_photos_add_test.go
   EOF
   ```

   Both lines must end with `: OK`. Commit "1447 step 1".

2. Three small edits (use the editor tool; each old text must be found exactly once, else STOP). The three-space indent of the code blocks below is markdown only; the Go lines inside start with tabs, as in the file:

   a. `go/internal/web/ai/guide_cards.go`, replace

   ```
   	case "delete":
   		s.cardDelete(w, r)
   	default:
   		guideNotFound(w)
   ```

   by

   ```
   	case "delete":
   		s.cardDelete(w, r)
   	case "photos":
   		s.photoAdd(w, r)
   	default:
   		guideNotFound(w)
   ```

   and replace the comment line `// skip and delete. Any other action is the router's 404, before CSRF.` by `// skip and delete, and photos (brief 1447: add a photo). Any other action is the router's 404, before CSRF.`

   b. `go/internal/web/ai/guide_photos.go`, replace the three comment lines

   ```
   // 1442): show one stored photo and delete one. Adding a photo
   // (POST .../photos) stays on Python; see brief 1447.
   ```

   by

   ```
   // 1442): show one stored photo and delete one. Adding a photo
   // (POST .../photos) is guide_photos_add.go (brief 1447).
   ```

   c. `go/internal/web/ai/guide_data.go`, replace

   ```
   // deletePhoto is guide_photos.delete: the row goes, then the file. The Go
   // container mounts the data volume read-only, so a file it cannot remove is
   // left for guide_photos.purge_orphans (the scheduler's sweep of files no row
   // names, once they are an hour old). It reports false when the photo is not on
   // this card of this property.
   ```

   by

   ```
   // deletePhoto is guide_photos.delete: the row goes, then the file. The data
   // volume is writable since brief 1640; a file that still cannot be removed is
   // left for guide_photos.purge_orphans (the scheduler's sweep of files no row
   // names, once they are an hour old). It reports false when the photo is not on
   // this card of this property.
   ```

   Check: `git diff --stat | tail -5` shows the three files, and `grep -c 'photoAdd' go/internal/web/ai/guide_cards.go | tail -1` prints `1`. Commit "1447 step 2".

3. Format, build, vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/ai cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/ai/... ./cmd/... 2>&1 | tail -30; go mod tidy -diff 2>&1 | grep -v downloading | tail -5
   ```

   Expected: no output at all. Anything printed: STOP (§8). Commit "1447 step 3" only if a file changed.

4. PostgreSQL: as brief 1442 step 3 (`UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres`; brief 1440 step 3 starts the throwaway server). No server: write "CI only" in the report and STOP before step 5.

5. Tests (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres go test ./internal/web/ai/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
   ```

   Expected: `ok` for both packages. Then show the named tests ran:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres go test ./internal/web/ai/ -count=1 -v -run '^(TestGuidePhotoAdd|TestGuidePhotoFileAndDelete|TestGuideRoutesUniqueAndPoolFree)$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -10
   ```

   Expected: three `--- PASS` lines and a final `ok`; no `--- SKIP`, no `--- FAIL`.

6. Write the report (§9), set `Status: review`, commit "1447 step 6". Run last, from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` (no finding about the files of this brief).

## 5. Do not touch

`go/go.mod`, `go/go.sum`, `go/internal/imgproc/`, `go/cmd/ubyhost-web/` (no route is added, no path is switched), `deploy/`, `App/` (Python keeps serving the route until the owner switches the path), `docs/context/*`, every other guide file. Never set `UBYHOST_GO_PATHS`.

## 6. Commands

Exactly those of §4 (steps 3 and 5). Test-map: no row exists for `go/internal/web/ai`; the coordinator adds one from the report. Never the full suite, never `go test ./...`.

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for both files.
- [ ] Step 3 printed nothing.
- [ ] Step 5 printed `ok` for both packages and three `--- PASS` (none `SKIP`, none `FAIL`) on PostgreSQL.
- [ ] `git diff --stat main...HEAD | tail -20` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no compose, Caddy, env, `go.mod` or Python file changed in this brief; nothing was pushed to `main`.
- [ ] UI: not applicable in this PR (rules 7 and 10): no template or CSS changes and no path routes to the handler yet. The UX gate runs on staging before the owner switches the path (Owner steps).

## 8. Stop and ask

Stop, and write the report, if an anchor, hash or file count of step 0, 1 or 2 is not as stated; a test fails twice (do not edit the sidecar files: report); you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside §3 needs a change; or you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1447-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with the last 5 lines of its output, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`guide_photos_add.go`: the checks come in Python's order; the size limit is read as limit + 1 byte; the file is written only after `imgproc.Clean` succeeded; a failed insert removes the file; the name is random hex and never taken from the request. `guide_cards.go`: only the `photos` case is new.

## Owner steps

The photo upload runs on Python until you switch it. Do these in order, on the staging server first:

1. Deploy brief 1640 (writable volume) and set `UBYHOST_GO_MEM=768m` in `.env` (brief 1641, Owner steps); run `docker compose --profile go up -d ubyhost-go`.
2. UX gate (the orchestrator does this on staging, not you): with a test property, add a portrait phone photo (JPEG with rotation), a PNG with a transparent background and a WebP to a guide card; open the card page at 390, 768 and 1280 px and check the photos stand upright and the page looks as before.
3. Add this path to `UBYHOST_GO_PATHS` in `.env` (keep the existing value, space-separated, inside the double quotes): `/apartments/*/guide/*/photos`. This is the exact path without a trailing `/*`; the paths `/apartments/*/guide/*/photos/*` and `.../delete` are already there (brief 1446). Run `docker compose up -d`.
4. Check on staging: add a photo, see it on the card, delete it. Rollback is removing the path again and `docker compose up -d`; photos stored by Go are ordinary files that Python reads the same.
