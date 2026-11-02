# 0641 report: Go iCal feed download with SSRF guard
Status: review

## Files changed
- `go/internal/ical/feedurl.go` (guard: ResolveTarget, ResolveRedirect, AllowPrivate, blocked-range tables)
- `go/internal/ical/feedurl_test.go` (table tests ported from test_feed_url_ssrf.py, IPv6 per reserved range, host guards, redirect rules)
- `go/internal/ical/fetch.go` (Fetch, CleanValidator, pinned transport, 3-hop manual redirects, caps, decoding)
- `go/internal/ical/fetch_test.go` (httptest cases: 200/304, redirects, oversize, non-200, BOM, invalid UTF-8, latin-1, DNS pinning)
- `docs/tasks/0641-report.md` (this file)

## Commands
- `test -z "$(gofmt -l .)" && go vet ./...` (from `go/`): clean, no output.
- `go test ./internal/ical/ -count=1` (from `go/`): `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ical`. With `-race`: ok. 28 tests pass, 0 skipped, no real network (loopback httptest only, with allowPrivate true in one test).
- `python3 scripts/context_lint.py | tail -3`: `context lint: FAIL`. The only error is `docs/tasks/0641-go-ical-fetch.md needs a 'Status: <blocked|done|in-progress|replaced|review|todo>' line`. The brief has `Status: ready`, which the linter does not accept. The brief is not in this commit's scope, so it was left as is.

## Deviations from Python (none silent)
1. Every IPv4-mapped IPv6 address is refused, not unwrapped and checked. Python's `::ffff:0:0/96` is in its private list, so this matches Python exactly.
2. `fec0::/10` (deprecated site-local) is allowed, as in Python (ipaddress does not flag it). This is a gap in the Python guard; it was not changed. Owner decision needed.
3. Python's IPv4 and IPv6 private and reserved lists were copied from the 3.13 stdlib (exceptions included).
4. BOM: all leading U+FEFF are stripped, as Python's `lstrip` does, not exactly one.
5. Charset: only iso-8859-1, latin-1 and latin1 are decoded as declared. windows-1250 and every other charset decode as UTF-8 (no x/text).
6. Invalid UTF-8: one U+FFFD per invalid byte. Python's `errors=replace` can give a different count for truncated sequences.
7. Timeouts: 45 s is the dial and response-header timeout, not Python's per-read socket timeout. The 60 s body deadline is also a request-context deadline counted from each hop's start (includes header wait), so it is no later than Python's.
8. The transport has `Proxy: nil` and direct dials to the pinned addresses only. Python's `_socket_connect_pinned` is also direct.
9. DNS failure text is Go's resolver wording, not Python's gaierror wording.
10. Port handling: 0 gives the invalid-port key, non-numeric or above 65535 gives malformed (as urlparse).
11. An https-to-http redirect is tested in `feedurl_test.go` through `ResolveRedirect` only, because a fetch test would need a TLS test server.
12. go.mod says `go 1.25.0` and the local toolchain is go1.24.7. It worked here (module download via GOTOOLCHAIN auto), but CI should confirm.

## Questions
- Owner: should `fec0::/10` be blocked in both Python and Go (see deviation 2)?
- Brief status line `Status: ready` fails `scripts/context_lint.py` (see Commands).

## Owner steps left
- None for this slice. Nothing calls the package yet. Push and PR are not done (brief says do not push).
