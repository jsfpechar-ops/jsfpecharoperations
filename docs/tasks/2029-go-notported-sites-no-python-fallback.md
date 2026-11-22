# 2029: Remove the dead Python fallback from the Go notPorted sites (AUD-04)

Status: todo
Depends on: 2002 (hostweb.NotFoundPage, PR #1256, on main) | Base commit: b5127d006 | Branch: task/2029-go-notported-sites
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`notPorted` in `go/internal/web/properties/lists.go` answers 501 plus `X-Ubyhost-Not-Ported: 1` so Caddy re-sends the request to Python. The all-Go Caddyfiles no longer do that (verified on main: `reverse_proxy` goes only to `ubyhost-go`; the only `Not-Ported` string left in `go/` and `deploy/` outside tests is in `lists.go`). So every site is a live 501 text page. Worst case: `GET /apartments/abc` shows "not served by Go yet: a path id that is not a number"; Python answers the branded 404 (`App/app/main.py` `validation_error_handler`).

## 2. Context: verification of the claim (current main, b5127d006)

Still holds. `git grep -n notPorted -- go` finds 16 call sites in `go/internal/web/properties/` (not 18; the "about 18" counted two helper paths, see group C). No other Go package has a Not-Ported header.

| Group | Site (file:line) | Trigger | Plan |
|---|---|---|---|
| A | `apartment_detail.go:230` | path id not a number | NotFoundPage (matches Python) |
| A | `apartment_detail.go:243`, `apartment_new.go:321` | `copy_from`/numeric query non-ASCII or oversized | NotFoundPage |
| A | `lists.go:219` | `?edit=` non-ASCII number | NotFoundPage |
| A | `apartment_create.go:399`, `apartment_update.go:338`, `apartment_small_posts.go:324` | form int non-ASCII or past 64 bits | NotFoundPage |
| B | `apartment_create.go:393`, `apartment_update.go:332` via `apartmentUpdateNotPorted` (`stay_fee_guest_form`, other setup_step values, wizard return_to; the non-ASCII digit and bad `stay_fee_rate_from` cases go to NotFoundPage as group A) | unported form branches | interim redirect + flash; ports 2030, 2031 |
| B | `apartment_update.go:122` | refused council account with guest-pay operator account | interim redirect + flash; port 2030 |
| C | `apartment_small_posts.go:114` (automation timing save), `:262` and `:264` (iCal feed validation re-render, wizard calendar step and bookings view), `:547` and `:550` (police-letter read re-render) | HTML re-render with errors | interim redirect + flash; ports later |
| C | `entities.go:44` (`fillFromRegister` default, brief 1523 replaces it from an `init()`) | ARES lookup | no change (1523 landed) |

### Owner decisions (made)

- **D1 (group B):** port `stay_fee_guest_form` and the wizard steps. Each is too big for this session, so they are separate briefs: **2030** (guest-pay block) and **2031** (wizard `setup_step` values and wizard return_to). Until they land, 2029 turns the group B 501 into the interim redirect of D2 so nobody sees the 501 text.
- **D2 (group C):** interim redirect back to `returnTo` (or the page the form came from) with an error flash; ports later, one brief per re-render (2032, 2033 to be written after 2029 merges).
- **D3 (ARES):** brief 1523 landed (`entity_editor.go` `init()` sets `fillFromRegister = fillFromRegisterAnswer`). The 501 stub in `entities.go:44` is unreachable. No change; optional cleanup is out of scope.
- Oversized and non-ASCII numbers: keep the 404 narrowing (group A).

Interim flash: add key `flash.error.not_saved_here` to `go/internal/web/properties/apartmentsmallposts/i18n.json` in en, cs and vi (en: "This change could not be saved from here. Reload the page and try again."; cs: "Tuto změnu se odsud nepodařilo uložit. Načtěte stránku znovu a zkuste to znovu."; vi: "Không thể lưu thay đổi này từ đây. Hãy tải lại trang và thử lại."). Read it with `smallPostsFlash(q, "flash.error.not_saved_here", nil)` and send with `q.back(w, r, path, hostweb.Flash{}, flash)`. Mirror the shape of an existing key in that file; if the file has a key list test, extend it.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/apartment_detail.go` | edit | lines 230, 243: `hostweb.NotFoundPage(w, r)` |
| `go/internal/web/properties/apartment_new.go` | edit | line 321 |
| `go/internal/web/properties/lists.go` | edit | line 219; keep `notPorted` (no caller left after this brief, so delete it and `notported_test.go`'s use if nothing else needs it; otherwise keep), fix its comment to say Caddy no longer falls back |
| `go/internal/web/properties/apartment_create.go` | edit | line 399 only |
| `go/internal/web/properties/apartment_update.go` | edit | line 338 only |
| `go/internal/web/properties/apartment_small_posts.go` | edit | line 324 only |
| `go/internal/web/properties/notported_test.go`, `apartment_detail_test.go`, `lists_test.go` | edit | tests below |
| `docs/context/test-map.md` | edit | add the row in §6 |
| `docs/context/known-issues.md` | edit | append: groups B and C save nothing and show the interim flash until 2030, 2031 and the re-render ports land (list file:line) |

No other file may change.

## 4. Steps

1. `grep -nF 'notPorted(w, "a path id that is not a number")' go/internal/web/properties/apartment_detail.go`. Replace with `hostweb.NotFoundPage(w, r)` (package is already imported there). Repeat for each group A line in §2 (use `grep -nF` on the quoted reason text; `r` is in scope at each site, check once).
2. Add one test per group A site in the existing `_test.go` files, in their style: request with `abc` id, non-ASCII digit, oversized number; assert status 404, no `X-Ubyhost-Not-Ported` header, body contains "Page not found" for `Accept: text/html`.
3. Group B and C sites: replace each `notPorted(w, ...)` with the interim redirect + flash described above (`returnTo` is already computed at small_posts:256; elsewhere use `formReturnTo(r, <page>, false)` with the page the form came from, e.g. `/apartments/{id}`). Nothing is written before the redirect (these branches already returned before any write; confirm per site). Add a test per site: status 303, `Location` set, flash key present, no `X-Ubyhost-Not-Ported`, no DB write.
4. Update the `notPorted` comment (lines 46 to 47 of `lists.go`) to: it answers a branch Go does not render yet with a plain 501; Caddy has no Python fallback, so every call is user-visible.
5. Add the test-map row: `| Go host pages (properties) | in `go/`: `go test ./internal/web/properties/... ./internal/hostweb/... 2>&1 \| tail -30` |`.
6. Run §6. Commit `2029 step k` after each step.

## 5. Do not touch

`entities.go`; templates, CSS, Caddyfiles, `App/`; no new dependency. Hard rules 3 and 8 of AGENTS.md apply.

## 6. Commands

From `go/`: `go test ./internal/web/properties/... ./internal/hostweb/... 2>&1 | tail -30` (DB tests skip without `UBYHOST_TEST_DATABASE_URL`; say so in the report). From repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`, and `git grep -n 'notPorted(' -- go | wc -l` (expect 1 left: the unreachable stub in `entities.go`; confirm in the report).

## 7. Acceptance

- [ ] `GET /apartments/abc` with `Accept: text/html` returns 404 with the branded page, not 501.
- [ ] No group A site sets `X-Ubyhost-Not-Ported`.
- [ ] Group B and C sites redirect with the interim flash, write nothing, and are listed in known-issues.
- [ ] Test-map row added; tests green; lint green.
- [ ] No template or CSS change, so no screenshots.

## 8. Stop and ask

An excerpt is not found, `r` is not in scope at a site, a test fails twice, a file outside §4 needs a change, 25 tool calls reached. Never push, merge, or touch `main`.

## 9. Report

`docs/tasks/2029-report.md`, 600 tokens at most, per executor.md.

## Risk list (for the reviewer)

`apartment_create.go` and `apartment_update.go`: confirm a 404 for oversized form ints matches Python's outcome closely enough (Python int() accepts non-ASCII digits; 404 here is a deliberate narrowing, not parity). If the reviewer disagrees, ask the owner before merge.

## Owner steps

1. Open the draft PR, wait for CI green, mark it ready.
2. Merge with `scripts/merge-pr-on-green.sh <PR number>`.
3. After deploy, open `https://<your host>/apartments/abc` while logged in. Expect "Page not found", not "not served by Go yet".
4. Ask the orchestrator to write briefs 2032 and 2033 (the re-render ports) after this merges; 2030 and 2031 are already written.
