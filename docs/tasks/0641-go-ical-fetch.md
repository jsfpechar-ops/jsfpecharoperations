# 0641: Go iCal: safe feed download (SSRF guard, pinning, validators) like Python
Status: ready
Depends on: none | Base commit: origin/main | Branch: task/0641-go-ical-fetch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
Second slice of porting the `ical` job to Go, independent of 0640. Go gets the calendar download of `App/app/feed_fetch.py` `fetch_calendar` (196) with the URL guard of `App/app/feed_url.py` `resolve_calendar_target` (116) and `resolve_redirect_url` (186). Nothing calls it yet; nothing changes in production. A host's feed URL is user input, so the guard is a security boundary: Go must refuse everything Python refuses.
## 2. Context
- Python source of truth: `App/app/feed_url.py` (whole file, 194 lines) and `App/app/feed_fetch.py` lines 25-62 and 161-287. Their tests: `App/tests/test_feed_url_ssrf.py`, `App/tests/test_feed_dns_pinning.py`, `App/tests/test_ical_skip_unchanged.py` (read only the cases, for the Go table tests).
- Config: `UBYHOST_ICAL_ALLOW_PRIVATE` (`App/app/config.py` 622, read the accepted truthy words there) counts only when `UBYHOST_DEPLOYMENT` (lowercased, default `local`) is not `production`.
- **No new Go dependency.** `net/http`, `net`, `net/netip`, `net/url` only.
- **Traps:**
  - Pinning: resolve DNS once, validate every address, then connect only to those addresses (custom `DialContext` that ignores the hostname and dials the pinned IP:port in turn; TLS still verifies the original hostname via SNI). Never let `http.Client` follow redirects (`CheckRedirect` returns `http.ErrUseLastResponse`); follow up to 3 by hand, re-resolving and re-validating each hop, refusing https→http.
  - Blocked: loopback, private, link-local, multicast, unspecified, `169.254.169.254`, `100.64.0.0/10`, `192.0.0.0/24`, `198.18.0.0/15`, and Python `is_reserved` (`240.0.0.0/4`, IPv6 reserved ranges: copy what `ipaddress` reports, check one IPv6 case per range in the tests). Unwrap IPv4-mapped IPv6 (`::ffff:127.0.0.1`) before checking. Hostnames `localhost`, `metadata.google.internal`, `metadata.google`, `*.local`, `127.*`, and non-canonical numeric hosts (`0177.0.0.1`, `2130706433`, `0x7f.1`) are refused before DNS. Host compare is lowercased with a trailing dot removed. Embedded credentials, non-http(s) scheme, missing host, bad port are refused.
  - Error messages: same English text as Python (the sync log stores it); carry the `flash.error.*` key on a typed error like `FeedUrlError.key`. Download errors use the `CalendarFetchError` wording, including `Calendar returned HTTP N.`, `Calendar is too large.`, `Calendar download took too long.`, `Calendar redirected too many times.`.
  - Limits: 45 s request timeout, 60 s total body deadline, 5 MiB cap checked both on `Content-Length` (digits only) and while reading. Headers `User-Agent` exactly as Python, `Accept: text/calendar`, `If-None-Match`/`If-Modified-Since` from cleaned validators; 304 counts as not modified only when a validator was sent.
  - `clean_validator`: trim, at most 256 chars, printable ASCII 0x20-0x7E only, else none.
  - Body decoding: no charset in Content-Type means UTF-8; invalid bytes become U+FFFD; strip one leading BOM. A declared non-UTF-8 charset: support `iso-8859-1`/`latin-1` and `windows-1250` only if the standard library can (it can't for 1250 without x/text); otherwise decode as UTF-8 and note it in the report. Do not add x/text as a direct dependency.
## 3. Files
New: `go/internal/ical/feedurl.go`, `go/internal/ical/feedurl_test.go`, `go/internal/ical/fetch.go`, `go/internal/ical/fetch_test.go`. Write `docs/tasks/0641-report.md`. Nothing else (0640 adds `parse.go` in the same package in parallel: do not create or edit it; start the package with your own top comment in `feedurl.go`).
## 4. Steps
1. `feedurl.go`: `type FeedURLError struct{ Msg, Key string }`, `type Target struct{ URL, Host string; Port int; Scheme string; IPs []netip.Addr }`, `func ResolveTarget(ctx, rawURL string, r Resolver, allowPrivate bool) (Target, error)`, `func ResolveRedirect(ctx, current, location string, r Resolver, allowPrivate bool) (Target, error)`, `type Resolver interface{ LookupNetIP(ctx, network, host string) ([]netip.Addr, error) }` (`net.DefaultResolver` fits), `func AllowPrivate(getenv func(string) string) bool`.
2. `fetch.go`: `type Fetched struct{ Text, ETag, LastModified string; NotModified bool }`, `func Fetch(ctx, rawURL, etag, lastModified string, opt FetchOptions) (Fetched, error)` where `FetchOptions` holds the Resolver, allowPrivate and an optional dialer override for tests. `func CleanValidator(string) string`.
3. Tests (no network): table tests ported from the three Python test files for the guard; `httptest` servers with a fake Resolver mapping a public-looking name to the test server, and allowPrivate true only where the test needs the loopback server, covering: 200 with validators, 304 with and without sent validators, redirect to a blocked host refused, https→http refused, 4 redirects refused, oversize by header and by stream, non-200, BOM stripped, invalid UTF-8 replaced, DNS returning one blocked and one public address refused.
4. Commit: `0641: Go iCal feed download with SSRF guard and DNS pinning, matching Python`.
## 5. Do not touch
`App/` (all), `go/internal/` outside `ical/`, `go/internal/ical/parse*.go`, `go/cmd/`, `go.mod`/`go.sum`, compose, CI, templates/CSS/JS.
## 6. Commands
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/ical/ -count=1 2>&1 | tail -30`.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
`git diff --stat origin/main` lists only section 3 files and this brief. gofmt, vet and tests pass, 0 skipped, no test opens a real network connection.
## 8. Stop and ask
Stop if matching Python needs a new dependency, or the Python guard lets through an address you think is unsafe (report it; do not silently differ).
## 9. Report
`docs/tasks/0641-report.md`: command tails, diff stat, any difference from Python you could not avoid.
