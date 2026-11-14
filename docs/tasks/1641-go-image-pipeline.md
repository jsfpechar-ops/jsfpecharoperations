# 1641: Go image pipeline: golang.org/x/image and `go/internal/imgproc` (uploaded photo to a clean JPEG)

Status: review
Tier: A (a new dependency, and the code that decodes files strangers upload)
Depends on: none (nothing routes to it yet; brief 1447 uses it) | Base commit: current branch (One big PR mode) | Branch: current branch
Executor: Haiku 5.5 | Fits one session: 20 tool calls, 40k tokens

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1641 step k`. Never create a branch, never push, never open a PR.

## 1. Objective

Add the Go twin of `passport_photos.reencode_image` followed by `guide_photos._shrink` as package `go/internal/imgproc` (`imgproc.Clean(bytes) ([]byte, error)`), and the one new dependency it needs, `golang.org/x/image` (WebP decoder, scaler). Nothing serves a route with it yet; brief 1447 does.

## 2. Context

Rules (AGENTS.md): 2 privacy: the package touches no file and no network; the output holds pixels only (no EXIF, no GPS, no ICC profile). 3 test pictures are made up or generated in the test. **4 new dependency: the owner decided it on 2026-11-14; the line is in `docs/context/decisions.md` (`[dep/infra] golang.org/x/image v0.45.0 ...`).** 11 Go first.

**Dependency pin.** `golang.org/x/image v0.45.0` is the newest release that keeps `go 1.25.0` and the `toolchain go1.25.14` of `go/go.mod` and does not raise `golang.org/x/text` (v0.41.0) or `golang.org/x/sync` (v0.22.0). v0.46.0 and later require Go 1.26, which the Dockerfile (`golang:1.25-alpine`) does not have: do not take them. Exact additions the executor must see in the diff:

- `go/go.mod`: one line in the first `require` block, before `golang.org/x/text v0.41.0`: `golang.org/x/image v0.45.0`
- `go/go.sum`: two lines, before the `golang.org/x/sync` lines:

```
golang.org/x/image v0.45.0 h1:FMb1nTbH5H9vF55SriQHgFw5GnNL9Jg6L25BwXKzhB0=
golang.org/x/image v0.45.0/go.mod h1:n62x/7RqlwXDvGsSU4u6IUTUf6KghUZ9Bt7cG/T9Fx4=
```

**What Python does** (`App/app/passport_photos.py` 116-161 and `App/app/guide_photos.py` 31-39): accept JPEG, MPO, PNG, WEBP only (GIF, BMP, PDF are refused), refuse more than 40,000,000 pixels before decoding, take the first frame, apply EXIF orientation to the pixels, put transparency on white, write a JPEG from pixels only (quality 90), then shrink so the longest side is at most 1600 px (never enlarge) and write a JPEG of quality 82.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1641-files/<repo path>.txt`.

| sha256 | file | action | lines |
|---|---|---|---|
| `f5dca9801f318e65c2fae6630468a08f7865fe5201de78125c0ffeafbc7d4a1e` | `go/internal/imgproc/imgproc.go` | create | 221 |
| `28fe43cd3a41f5fa679f3bde949160b6ddc03832749e4b1d42bdd371314a25c1` | `go/internal/imgproc/imgproc_test.go` | create | 285 |

**How it works (for the reviewer).** `Clean` sniffs the magic bytes (JPEG, PNG, WebP), reads the size with `image.DecodeConfig` and refuses over 40,000,000 pixels (`ErrTooManyPixels`) before any pixel is decoded, takes one decoding slot (a channel of size 1, so two uploads never decode at once), decodes, composites on white into an `image.RGBA`, shrinks with `xdraw.CatmullRom` (only when a side is over 1600; the result side is `round(short*1600/long)`, like `Image.thumbnail`), applies the EXIF orientation of the JPEG's APP1 segment (eight cases, written as a pixel copy), and encodes quality 82. Shrinking before turning is the same picture (a 90 degree turn keeps the longest side) and needs less memory. Any decode problem, a GIF, a truncated file or an animated WebP is `ErrNotImage`; the caller maps both errors to `flash.error.guide_photo_type`.

**Known differences from Python (documented, accepted by this brief):**

| Point | Python | Go |
|---|---|---|
| Encoding | JPEG q90, decoded again, shrunk, JPEG q82 | one JPEG q82 (the bytes differ, the picture does not) |
| Resampling | Pillow bicubic | Catmull-Rom; pixel values differ by a few levels |
| EXIF orientation | read from JPEG, PNG (`eXIf`) and WebP | read from JPEG only; a PNG or WebP with an orientation tag stays as stored |
| Animated WebP | first frame is kept | refused (`x/image/webp` cannot decode animation); phones do not produce animated WebP photos |
| Memory | Pillow streams in C | a 40 megapixel photo needs about 500 MB peak and 2.5 s (measured: 7000x5700 JPEG); one decode at a time; see Owner steps |

**Verified by the brief writer** in a throwaway copy of `go/` with exactly these files and the two go.mod/go.sum changes: `gofmt -l` empty, `go build ./...` and `go vet` clean, `go mod tidy -diff` empty, `go test ./internal/imgproc/ -count=1` ok (9 tests). A mutation (orientation 6 mapped to the counter-clockwise turn) made the orientation test fail. Fixtures in the test are generated in code (JPEG, PNG, GIF) or are small base64 WebP files made with Pillow 12 (lossy, lossless, lossless with alpha, animated).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/imgproc/imgproc.go` | create | `Clean` and helpers |
| `go/internal/imgproc/imgproc_test.go` | create | 9 tests |
| `go/go.mod` | edit | one `require` line (step 2) |
| `go/go.sum` | edit | two lines (step 2) |
| `docs/context/architecture.md` | edit | one row (step 5) |
| `docs/tasks/1641-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1641-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `grep -c 'golang.org/x/image' go/go.mod go/go.sum | tail -3` prints `go/go.mod:0` and `go/go.sum:0`.
   - `grep -nE '^(go|toolchain) ' go/go.mod | tail -3` prints `3:go 1.25.0` and `5:toolchain go1.25.14`.
   - `ls go/internal/imgproc 2>&1 | tail -2` says "No such file".
   - `grep -c 'x/image v0.45.0' docs/context/decisions.md | tail -1` prints `1`.
   - `find docs/tasks/1641-files -name '*.txt' | wc -l | tail -1` prints `2`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1641-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -4
   f5dca9801f318e65c2fae6630468a08f7865fe5201de78125c0ffeafbc7d4a1e  go/internal/imgproc/imgproc.go
   28fe43cd3a41f5fa679f3bde949160b6ddc03832749e4b1d42bdd371314a25c1  go/internal/imgproc/imgproc_test.go
   EOF
   ```

   Both lines must end with `: OK`. Commit "1641 step 1".

2. The dependency (from `go/`; needs the Go module proxy):

   ```bash
   cd go && go get golang.org/x/image@v0.45.0 2>&1 | tail -5; go mod tidy 2>&1 | tail -5; git diff --stat go.mod go.sum | tail -4; git diff go.mod go.sum | grep -E '^[+-][^+-]' | tail -10
   ```

   Expected: exactly three changed lines, `+	golang.org/x/image v0.45.0` (go.mod, no `// indirect`) and the two `+golang.org/x/image v0.45.0 ...` lines of §2 (go.sum, with these exact hashes). `go.mod` must still say `go 1.25.0` and `toolchain go1.25.14`, and `x/text` / `x/sync` must keep their versions. Any other changed line, another version, a `go 1.26` line: `git checkout go/go.mod go/go.sum` and STOP (§8). If the proxy is unreachable (`dial tcp`, `403`), do not guess: apply the three lines by hand exactly as in §2 and say so in the report; step 3 then proves them. Commit "1641 step 2".

3. Format, build, vet (from `go/`):

   ```bash
   cd go && gofmt -l internal/imgproc 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/imgproc/ 2>&1 | tail -30; go mod tidy -diff 2>&1 | grep -v downloading | tail -10
   ```

   Expected: no output at all. Anything printed: STOP. Commit "1641 step 3" only if a file changed.

4. Tests (from `go/`; no database needed):

   ```bash
   cd go && go test ./internal/imgproc/ -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL|panic)' | tail -20
   ```

   Expected: nine `--- PASS` lines (`TestOrientationEightValues`, `TestNoMetadataSurvives`, `TestShrinkOnlyAndAspect`, `TestPNGTransparencyOnWhite`, `TestWebP`, `TestAnimatedWebPIsRefused`, `TestRefusals`, `TestTooManyPixelsBeforeDecoding`, `TestJPEGOrientationJunk`) and a final `ok`; no `--- SKIP`, no `--- FAIL`.

5. In `docs/context/architecture.md`, in the row that starts `| Go port (G1) |`, replace the exact text ``go/internal/schema/` (goose files and pending state) |`` by ``go/internal/schema/` (goose files and pending state), `go/internal/imgproc/` (uploaded photo to a clean JPEG: orientation, white background, 1600 px; uses `golang.org/x/image`) |``. Check: `grep -c 'go/internal/imgproc' docs/context/architecture.md | tail -1` prints `1`. Commit "1641 step 5".

6. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` (no finding about the files of §3). Write the report (§9), set `Status: review`, commit "1641 step 6".

## 5. Do not touch

Every other file under `go/` (no handler uses the package yet), `App/`, `deploy/`, `docs/context/decisions.md`, the sidecars. Do not run `go get -u`, `go get golang.org/x/image@latest` or `go mod tidy -go=...`.

## 6. Commands

Exactly those of §4 (steps 2, 3 and 4). No test-map row exists for `go/internal/imgproc`; the coordinator adds one from the report. Never the full suite, never `go test ./...`.

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for both files.
- [ ] `git diff main...HEAD -- go/go.mod go/go.sum | grep -cE '^\+[^+]' | tail -1` prints `3`, and `grep -cE '^-[^-]'` of the same diff prints `0`.
- [ ] `go.mod` still has `go 1.25.0` and `toolchain go1.25.14`.
- [ ] Step 3 printed nothing; step 4 printed nine `--- PASS` and `ok`.
- [ ] `git diff --stat main...HEAD | tail -20` lists only the paths of §3 and the sidecars.

## 8. Stop and ask

Stop, and write the report, if an anchor, hash or count of step 0, 1 or 2 is not as stated; the dependency step changes anything but the three lines; a test fails twice (do not edit the sidecar files: report); you reach 20 tool calls or about 40k tokens (report as `blocked`); a file outside §3 needs a change; or you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1641-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with the last 5 lines of its output, §7 ticked, deviations (say if go.mod was edited by hand), questions, owner steps left.

## Risk list (for the reviewer)

`go/go.mod` and `go/go.sum` (exactly the three lines), `go/internal/imgproc/imgproc.go`: the pixel limit is checked before `image.Decode`, only JPEG, PNG and WebP pass the magic-byte check, the decode slot is released on every path, nothing is written to disk.

## Owner steps

None for this brief (nothing is routed). Before brief 1447 is switched on: raise the Go service memory from the default 128 MB, because a 40 megapixel photo needs about 500 MB. In `.env` on the server set `UBYHOST_GO_MEM=768m` and run `docker compose --profile go up -d ubyhost-go`. Alternative if you prefer a smaller server footprint: tell the orchestrator, and a later brief lowers the Go pixel limit to 16,000,000 (a 4000x4000 photo) while Python keeps 40,000,000.
