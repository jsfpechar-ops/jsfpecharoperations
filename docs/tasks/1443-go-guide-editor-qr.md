# 1443: Go guest guide editor, part 4: the QR page, the print PNG and "new link"

Status: review
Depends on: 1440 | Base commit: 68c0e0985 | Branch: task/1443-go-guide-editor-qr
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the three QR routes of `App/app/routes/guest_guide.py` to `go/internal/web/ai`: the QR page (`GET /apartments/{id}/guide/qr`), the print-size PNG (`GET .../qr.png`) and "make a new link" (`POST .../qr/rotate`), with the page template. The PNG comes from `github.com/skip2/go-qrcode`, already in `go.mod` and used by `go/internal/payments`.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (guide pages only); 2 privacy: no new personal-data field, no new retention line, no outbound request; 3 fixtures are made up (`@example.test`, test-only secrets); 4 no new dependency (stdlib, pgx and packages already in `go.mod`); 5 plain PostgreSQL through `pgxpool`, the Python SQL with `$n` placeholders; 6 light mode, the forms work without JavaScript (they post plain forms); 7 and 10 see §7.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The QR code is drawn in the web service; the "open guide" button is a plain link the host clicks. The token (`apartment.guide_token`) is the existing one; rotating it replaces it as Python does.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1443-files/<repo path>.txt`.

| sha256 | file | action | lines |
|---|---|---|---|
| `408efec74ac23166773d07f67bdcb8b16e8938fdf8915df07b8ce7dc134c5166` | `go/internal/web/ai/guide_qr.go` | create | 126 |
| `0b595a0fe9b523f2ef0414fc72d1732f3a55654afa3c5586777483b634b8d90e` | `go/internal/web/ai/guide/templates/guide_qr.tmpl` | create | 23 |
| `775000bd763b4a0db8835e3f78417ee801966086d47a24848f261a2d277aea67` | `go/internal/web/ai/guide_qr_test.go` | create | 89 |

**How the code is built (for the reviewer; the executor reads no Go file, it only copies and runs).** The routes register through the table in `guide_common.go` (`guideAdd` in an `init()`), and `go/cmd/ubyhost-web/register_web_ai_guide.go` (brief 1440) hands them to `registerRoutes`; no other file of `go/cmd` changes. Every handler starts with `s.enter(w, r)`, which runs in FastAPI's order: for a POST `hostweb.CSRF` (header or `_csrf` field, multipart too), then the int path parameters (`422` when one is not an int), then `hostweb.Login` (`auth.require_login`), then `s.home(w, q)` (`_home`: the property of the signed-in workspace, not archived, else `404`). Redirects are `q.back` (`admin_helpers.back`, Starlette quoting), flashes are `q.flash(key, params)` from the guide catalog `guide/i18n.json`. Pages are `layout.Render` through `s.render` (host layout shell, `Cache-Control: no-store`). Every package-level name of these files starts with `guide`, so it cannot meet a name in the files of the other thread that works in `go/internal/web/ai` (`havel*.go`, `leon_setup*.go`); those files are not yours and not read.

**Parity notes:**

| Route | Python | Go |
|---|---|---|
| `GET /apartments/{id}/guide/qr` | `guide_qr` 202-212; `_guest_url` 198-200; `payments.qr_data_uri` (`App/app/payments.py` 153-163, box 6, border 4, level M) | `qrPage`, `guestURL` |
| `GET /apartments/{id}/guide/qr.png` | `guide_qr_png` 215-225; `guide_token.qr_png` 65-72 (box 20, border 4, level M) | `qrPNG`, `guideQRPNG` |
| `POST /apartments/{id}/guide/qr/rotate` | `guide_qr_rotate` 228-235; `guide_token.rotate` 44-49 | `qrRotate` (`rotateToken`, brief 1440) |

- Opening the page creates the token on first use (`guide_token.ensure`), like Python.
- `qr.png` is sent `Content-Type: image/png`, `Cache-Control: no-store`, `Content-Disposition: attachment; filename="guest-guide-qr.png"`.
- **PNG bytes differ from Python's.** Both draw a level-M code with a four-module border and the same module size; the encoders (python-qrcode with Pillow, go-qrcode) may choose a different mask, so the bytes are not identical and are not compared. The test decodes the PNG and checks every module against `qrcode.New(url).Bitmap()`. A scan test with a phone is an owner check before the switch.
- The page puts the PNG in the `src` of the `<img>` as a `data:` URL (`template.URL`); Go escapes `+` as `&#43;` there, which a browser reads as `+`.

**Known differences from Python, shared by every Go web area (not fixed here):** a missing or foreign record answers `404 {"detail":"Not Found"}` (and a non-integer id `422`), where Python shows the branded error page to a browser; `HEAD` and a wrong method answer `405` JSON (Python too); Go sets `Cache-Control` as the Python page routes do (`no-store`), and the `m.wrap` default `no-store, private` covers redirects.

**Anchors that must exist verbatim** (step 0): the three function lines in `App/app/routes/guest_guide.py`; `grep -c "skip2/go-qrcode" go/go.mod` prints `1`.

**Verified by the brief writer (in a throwaway worktree of this repo, sidecars copied exactly as step 1 does):** the two tests PASS on PostgreSQL 16 (PNG pixel check for box sizes 6 and 20; page, download headers, rotate by the owner, rotate refused for another account, foreign and signed-out requests); the page body equals the Jinja render of `guest_guide_qr.html` except the PNG bytes of the `src` (whitespace between tags normalised). A first version put the help tip inside the title's no-wrap span like `layout.uiSection`; the comparison showed Python puts it after the span, so `guideSectionOpen` in `guide_common.go` follows Python. (`go/internal/hostweb/layout/macros_ui.go` `uiSection` has the same difference; it is read-only here and is reported to the coordinator.)

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/ai/guide_qr.go` | create | three routes: QR page, qr.png, rotate |
| `go/internal/web/ai/guide/templates/guide_qr.tmpl` | create | Go twin of guest_guide_qr.html |
| `go/internal/web/ai/guide_qr_test.go` | create | PNG and route tests |
| `docs/tasks/1443-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1443-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints `task/1443-go-guide-editor-qr`.
   - `grep -cF "def guide_qr(request: Request, apartment_id: int):" App/app/routes/guest_guide.py | tail -1` prints `1`.
   - `grep -cF "def guide_qr_png(request: Request, apartment_id: int):" App/app/routes/guest_guide.py | tail -1` prints `1`.
   - `grep -cF "def guide_qr_rotate(request: Request, apartment_id: int):" App/app/routes/guest_guide.py | tail -1` prints `1`.
   - `ls go/internal/web/ai/guide_common.go go/internal/web/ai/guide_data.go go/cmd/ubyhost-web/register_web_ai_guide.go 2>&1 | tail -5` lists all three (brief 1440 is on this branch), and the files of §3 for this brief do not exist yet (`ls` says "No such file").
   - `find docs/tasks/1443-files -name '*.txt' | wc -l | tail -1` prints `3`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1443-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -12
   408efec74ac23166773d07f67bdcb8b16e8938fdf8915df07b8ce7dc134c5166  go/internal/web/ai/guide_qr.go
   0b595a0fe9b523f2ef0414fc72d1732f3a55654afa3c5586777483b634b8d90e  go/internal/web/ai/guide/templates/guide_qr.tmpl
   775000bd763b4a0db8835e3f78417ee801966086d47a24848f261a2d277aea67  go/internal/web/ai/guide_qr_test.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1443 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/ai cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/ai/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all (gofmt lists nothing, build and vet are silent). Anything printed: STOP (§8). Commit "1443 step 2".

3. PostgreSQL: as brief 1440 step 3 (the server on port 55440 may still run: `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1440/data status' | tail -1` says `server is running`; if stopped, run only the `pg_ctl ... start` part of that step). Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres` below. No server: write "CI only" in the report and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres go test ./internal/web/ai/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
   ```

   Expected: two lines, `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai	<seconds>s` and `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	<seconds>s`. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres go test ./internal/web/ai/ -count=1 -v -run '^TestGuideQRPNGMatchesTheCode$|^TestGuideQRRoutes$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of 2 tests (times differ) and a final `ok` line; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestGuideQRPNGMatchesTheCode (0.NNs)
   --- PASS: TestGuideQRRoutes (0.NNs)

5. Write the report (§9), set `Status: review` and commit "1443 step 5". Open one PR titled "1443: Go guest guide editor, part 4: the QR page, the print PNG and "new link"" with the PR text of §2 in its description.

## 5. Do not touch

As brief 1440 §5, plus every file of briefs 1440 to 1442 and 1444 to 1446. Rule 4: `go.mod` and `go.sum` must not change (`git diff --stat -- go/go.mod go/go.sum | tail -3` prints nothing).

## 6. Commands

Exactly the commands of §4 (steps 2 and 4, and the `go.mod` check of §7). No test-map row exists yet for `go/internal/web/ai`; the coordinator adds one from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | tail -30` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 3 files.
- [ ] Step 2 printed nothing (gofmt, build and vet clean).
- [ ] Step 4 printed `ok` for both packages, and each of the 2 named tests printed `--- PASS` (none `SKIP`, none `FAIL`) on PostgreSQL.
- [ ] `git diff --stat -- go/go.mod go/go.sum | tail -3` prints nothing.
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

Write `docs/tasks/1443-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git diff --stat main...HEAD | tail -20`; `origin/main...HEAD` if there is no local `main`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `guide_qr.go`: `qrPage` and `qrPNG` call `s.home` before the token is read or created; `qrRotate` is a POST behind CSRF and `home`; the `Content-Disposition` header carries a fixed file name. The generated URL is `hostweb.PublicBase` plus `/g/` plus the token, never request data.

## Owner steps

None: nothing is switched on. Before the switch, scan the printed QR code of one real property with a phone (the PNG bytes differ from Python's).
