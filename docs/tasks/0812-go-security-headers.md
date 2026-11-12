# 0812: Go web responses carry the same security headers as Python

Status: done (code on main and live in production, server on #928, 2026-11-12; closed in bulk by the orchestrator)
Depends on: none | Base commit: origin/main | Branch: task/0812-go-headers
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Before Caddy sends any page to the Go service (cutover step 4), every Go response must carry the headers Python's `_harden` and the HTTP middleware add (`App/app/main.py` lines 181-218 and 293-300). Today Go sends none of them, so moving `/api/command-palette`, `/dashboard/calendar` and `/payments/qr/*.png` would drop `nosniff`, `X-Frame-Options`, the CSP and `Cache-Control: no-store, private`.

## 2. Context

Python sets these as defaults (a value the route set itself wins):

| Header | Value |
|---|---|
| X-Content-Type-Options | `nosniff` |
| X-Frame-Options | `DENY` |
| Referrer-Policy | `strict-origin-when-cross-origin` |
| Permissions-Policy | `camera=(self), microphone=()` |
| Content-Security-Policy | `default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; connect-src 'self' https://challenges.cloudflare.com` |
| Cache-Control | `no-store, private` |

All Go routes are wrapped by `(*metrics).wrap` in `go/cmd/ubyhost-web/main.go` (line 59). Setting the headers on `w.Header()` there, before `h(rec, r)` runs, gives "route value wins" for free, because handlers call `Header().Set` (the calendar handler sets `Cache-Control: no-store`, which then replaces the default, exactly as in Python).

## 3. Files

| Path | Action |
|---|---|
| `go/cmd/ubyhost-web/main.go` | edit: a `hardenHeaders` table + 3 lines in `wrap` |
| `go/cmd/ubyhost-web/main_test.go` | edit: two tests |
| `docs/tasks/0812-report.md` | create |

No other file may change.

## 4. Steps

1. In `main.go` add, above `wrap`:
   ```go
   // hardenHeaders are Python's _harden defaults plus the middleware's
   // Cache-Control (App/app/main.py 181-218, 293-300). A route's own value wins.
   var hardenHeaders = [][2]string{
   	{"X-Content-Type-Options", "nosniff"},
   	{"X-Frame-Options", "DENY"},
   	{"Referrer-Policy", "strict-origin-when-cross-origin"},
   	{"Permissions-Policy", "camera=(self), microphone=()"},
   	{"Content-Security-Policy", "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; connect-src 'self' https://challenges.cloudflare.com"},
   	{"Cache-Control", "no-store, private"},
   }
   ```
2. In `wrap`, as the first lines of the inner func:
   ```go
   for _, h := range hardenHeaders {
   	w.Header().Set(h[0], h[1])
   }
   ```
   (Rename the loop variable if it shadows the `h` parameter: use `hv`.)
3. Tests in `main_test.go` (no database): build `m := &metrics{counts: map[key]int64{}}`, wrap a handler that writes `200 ok`, call it with `httptest.NewRecorder()`: assert all six headers equal the table. Second test: a handler that sets `Cache-Control: no-store` before writing: assert the response has `no-store` and still has `nosniff`.
4. Write a test that pins the CSP string to Python: open `../../../App/app/main.py`, and assert that it contains `"default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "` (so a Python CSP change makes this Go test fail and someone updates both).

## 5. Do not touch

Any handler package, Caddyfiles, compose, Python. No new dependency.

## 6. Commands

From `go/`: `go vet ./cmd/... 2>&1 | tail -5` and `go test ./cmd/ubyhost-web/ 2>&1 | tail -15` (no database needed). `gofmt -l cmd/ | tail -5` prints nothing.

## 7. Acceptance

- [ ] Both new tests and the existing main_test.go tests pass.
- [ ] `git diff --stat origin/main` lists only section 3 files.

## 8. Stop and ask

`wrap` is not at line 59 or not used by every route; a test fails twice; 25 tool calls.

## 9. Report

`docs/tasks/0812-report.md`: files, commands with their last lines, deviations.
