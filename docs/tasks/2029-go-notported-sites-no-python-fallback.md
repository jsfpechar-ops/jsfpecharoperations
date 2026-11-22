# 2029: Remove the dead Python fallback from the Go notPorted sites (AUD-04)

Status: todo
Depends on: 2002 (hostweb.NotFoundPage, PR #1256, on main) | Base commit: b5127d006 | Branch: task/2029-go-notported-sites
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`notPorted` in `go/internal/web/properties/lists.go` answers 501 plus `X-Ubyhost-Not-Ported: 1` so Caddy re-sends the request to Python. The all-Go Caddyfiles no longer do that (verified on main: `reverse_proxy` goes only to `ubyhost-go`; the only `Not-Ported` string left in `go/` and `deploy/` outside tests is in `lists.go`). So every site is a live 501 text page. Worst case: `GET /apartments/abc` shows "not served by Go yet: a path id that is not a number"; Python answers the branded 404 (`App/app/main.py` `validation_error_handler`).

## 2. Verification of the claim (current main, b5127d006)

Still holds. `git grep -n notPorted -- go` finds 16 call sites in `go/internal/web/properties/` (not 18; the "about 18" counted two helper paths, see group C). No other Go package has a Not-Ported header.

| Group | Site (file:line) | Trigger | Plan |
|---|---|---|---|
| A | `apartment_detail.go:230` | path id not a number | NotFoundPage (matches Python) |
| A | `apartment_detail.go:243`, `apartment_new.go:321` | `copy_from`/numeric query non-ASCII or oversized | NotFoundPage |
| A | `lists.go:219` | `?edit=` non-ASCII number | NotFoundPage |
| A | `apartment_create.go:399`, `apartment_update.go:338`, `apartment_small_posts.go:324` | form int non-ASCII or past 64 bits | NotFoundPage |
| B | `apartment_create.go:393` and `apartment_update.go:332` via `apartmentUpdateNotPorted` (`apartmentNotPortedFields` = `stay_fee_guest_form`, other setup_step values, wizard return_to, non-ASCII digits, bad `stay_fee_rate_from`) | unported form branches | DECISION D1 |
| B | `apartment_update.go:122` | refused council account with guest-pay operator account | DECISION D1 |
| C | `apartment_small_posts.go:114` (automation timing save), `:262` and `:264` (iCal feed validation re-render, wizard calendar step and bookings view), `:547` and `:550` (police-letter read re-render) | HTML re-render with errors | DECISION D2 |
| C | `entities.go:44` (`fillFromRegister` default, brief 1523 replaces it from an `init()`) | ARES lookup | leave, see D3 |

## 3. Decisions the owner must make (the brief does group A only until answered)

- **D1** (group B, unported form branches): (a) port each branch (each is a separate Python path, own brief), or (b) answer NotFoundPage now. Recommendation: (a) for `stay_fee_guest_form` and wizard `setup_step`s, because they are real user actions; NotFoundPage would silently lose a save.
- **D2** (group C, re-renders): a 404 would be wrong, the user did a valid action and made a typo. Options: (a) port the re-render, (b) interim redirect back to `returnTo` with an error flash via the existing flash helper. Recommendation: (b) now, (a) later. Needs one brief per re-render.
- **D3**: is brief 1523 (ARES fill) still planned? If not, route `fillFromRegister` to a redirect with a flash.

Executor: do group A only. Do not decide D1 to D3.

## 4. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/apartment_detail.go` | edit | lines 230, 243: `hostweb.NotFoundPage(w, r)` |
| `go/internal/web/properties/apartment_new.go` | edit | line 321 |
| `go/internal/web/properties/lists.go` | edit | line 219; keep `notPorted` (still used by groups B and C), fix its comment to say Caddy no longer falls back |
| `go/internal/web/properties/apartment_create.go` | edit | line 399 only |
| `go/internal/web/properties/apartment_update.go` | edit | line 338 only |
| `go/internal/web/properties/apartment_small_posts.go` | edit | line 324 only |
| `go/internal/web/properties/notported_test.go`, `apartment_detail_test.go`, `lists_test.go` | edit | tests below |
| `docs/context/test-map.md` | edit | add the row in §6 |
| `docs/context/known-issues.md` | edit | append: groups B, C, D3 still answer 501 text (list file:line) |

No other file may change.

## 5. Steps

1. `grep -nF 'notPorted(w, "a path id that is not a number")' go/internal/web/properties/apartment_detail.go`. Replace with `hostweb.NotFoundPage(w, r)` (package is already imported there). Repeat for each group A line in §2 (use `grep -nF` on the quoted reason text; `r` is in scope at each site, check once).
2. Add one test per group A site in the existing `_test.go` files, in their style: request with `abc` id, non-ASCII digit, oversized number; assert status 404, no `X-Ubyhost-Not-Ported` header, body contains "Page not found" for `Accept: text/html`.
3. Update the `notPorted` comment (lines 46 to 47 of `lists.go`) to: it answers a branch Go does not render yet with a plain 501; Caddy has no Python fallback, so every call is user-visible.
4. Add the test-map row: `| Go host pages (properties) | in `go/`: `go test ./internal/web/properties/... ./internal/hostweb/... 2>&1 \| tail -30` |`.
5. Run §6. Commit `2029 step k` after each step.

## 6. Commands

From `go/`: `go test ./internal/web/properties/... ./internal/hostweb/... 2>&1 | tail -30` (DB tests skip without `UBYHOST_TEST_DATABASE_URL`; say so in the report). From repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`, and `git grep -n 'notPorted(' -- go | wc -l` (expect 8 call sites left: 2 in B create/update, 1 in update.go:122, 5 in small_posts, 1 in entities; confirm the exact number in the report).

## 7. Acceptance

- [ ] `GET /apartments/abc` with `Accept: text/html` returns 404 with the branded page, not 501.
- [ ] No group A site sets `X-Ubyhost-Not-Ported`.
- [ ] Group B and C sites unchanged and listed in known-issues.
- [ ] Test-map row added; tests green; lint green.
- [ ] No template or CSS change, so no screenshots.

## 8. Stop and ask

An excerpt is not found, `r` is not in scope at a site, a test fails twice, a file outside §4 needs a change, 25 tool calls reached. Never push, merge, or touch `main`.

## 9. Report

`docs/tasks/2029-report.md`, 600 tokens at most, per executor.md.

## Risk list (for the reviewer)

`apartment_create.go` and `apartment_update.go`: confirm a 404 for oversized form ints matches Python's outcome closely enough (Python int() accepts non-ASCII digits; 404 here is a deliberate narrowing, not parity). If the reviewer disagrees, move those lines to D1.

## Owner steps

1. Answer D1, D2 and D3 in the PR conversation (one line each, a/b).
2. Open the draft PR, wait for CI green, mark it ready.
3. Merge with `scripts/merge-pr-on-green.sh <PR number>`.
4. After deploy, open `https://<your host>/apartments/abc` while logged in. Expect "Page not found", not "not served by Go yet".
5. Ask the orchestrator for follow-up briefs for the D1 and D2 ports you chose.
