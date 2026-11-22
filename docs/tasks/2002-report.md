# Task 2002 Report: Go host web branded 404, trailing-slash redirect, staydetail logging

Status: review

## Changes Summary

Implemented three Go-only fixes in the host web:

1. **Trailing-slash redirect:** Implemented `CanonicalSlash` wrapper in `go/internal/hostweb/slash.go` to answer `GET /reservations/252/` with `307 /reservations/252`, preserving method and query string, matching Python's Starlette `redirect_slashes` behavior.

2. **Branded 404 page:** Refactored `notfound.go` to introduce `NotFoundPage` function serving branded HTML to requests with `Accept: text/html` and empty 404 body otherwise. The payments-hidden middleware continues using this via `BlockedPage` wrapper.

3. **staydetail logging:** Added `stayNotFound` helper that logs `stay detail: not found method=… id=… workspace=…` before rendering the branded 404, enabling attribution of production 404s.

## Test Results

```
go/cmd/ubyhost-web/main.go                  | 6 +-
go/internal/hostweb/notfound.go             | 11 ++-
go/internal/hostweb/notfound_test.go        | 18 +++++
go/internal/hostweb/slash.go                | 38 ++++++++++
go/internal/hostweb/slash_test.go           | 108 ++++++++++++++++++++++++++++
go/internal/web/staydetail/handlers.go      | 12 +++-
go/internal/web/staydetail/handlers_test.go | 40 +++++++++++
7 files changed, 225 insertions(+), 8 deletions(-)
```

**All tests pass:**
- `gofmt` clean
- `go vet` clean
- `go test ./internal/hostweb/... ./internal/web/staydetail/... ./cmd/ubyhost-web/...` ✓
- `python3 scripts/context_lint.py` ✓

## Acceptance Checklist

- [x] `/reservations/7/` and `/reservations/7/?x=1` answer `307` to `/reservations/7` (query kept), `POST` included; `/`, unknown paths and subtree routes unchanged.
- [x] Host-page 404 with `Accept: text/html` renders branded page; without it, body stays empty; payments-hidden middleware still uses same page.
- [x] `staydetail` logs exactly one `stay detail: not found method=… id=… workspace=…` line per not-found and nothing else new.
- [x] `gofmt`, `go vet`, three package test suites and `scripts/context_lint.py` green.
- [x] PR body will state what was NOT fixed.

## Anchor Link Handling

The trailing-slash redirect does **not** cover the `#now` anchor link from the stay email (`https://app.ubyhost.com/reservations/252#now`).

**Why not:** The anchor (`#now`) is stripped by the browser before the HTTP request is sent to the server. The request reaches the server as `GET /reservations/252/` with no `#now` fragment. After the `307` redirect, the browser makes a fresh request to `/reservations/252?` and re-applies the anchor if it was stored client-side, but HTTP does not carry anchors over redirects. The URL in the email must include the anchor after the path without slash: `https://app.ubyhost.com/reservations/252#now`, and the host must not enforce trailing slashes on that path (which it now doesn't, via `CanonicalSlash`).
