# 0683 report (executor: Haiku 5.5)
Status: blocked

## Files changed (vs origin/main)
- App/scripts/webpush_golden.py (new): loads app/webpush.py by path, writes the golden file with fixed keys, salt and time.
- go/internal/webpush/webpush.go (new): RFC 8291 aes128gcm Encrypt, RFC 8292 VapidHeader (ES256, raw r||s), Send (http.Client, redirects not followed, network error = ErrTransport). Stdlib only.
- go/internal/webpush/webpush_test.go (new): golden body byte equality, golden JWT header/claims equality plus signature verify, receiver-side round trip, oversize refusal, bad point refusal, httptest headers, redirect not followed, transport error.
- go/internal/webpush/testdata/golden.json (new).
Commit: 3aa8adc "0683 step 1-2: go webpush package, python golden, tests". Not pushed.

## Commands (tails)
- `python3 scripts/webpush_golden.py`: wrote golden.json, body 164 bytes.
- `go vet ./internal/webpush/` clean; `gofmt -l` empty.
- `go test ./internal/webpush/ -count=1 -v`: 7 PASS, 0 skip (`ok github.com/.../go/internal/webpush 0.013s`).
- `python3 scripts/context_lint.py`: context lint OK.
- `python3 scripts/go_host_i18n.py --check`: FAILED to run, App/.venv missing (No module named 'fastapi'). Not resolved.
- `go build ./...` ran but downloaded modules for other packages; result not confirmed.

## Left (steps 3 to 6 not started)
Left: steps 3 to 6. Step 3 (pushsend + DB tests), step 4 (pushweb /account/push/test), step 5 (job kind push in main.go), step 6 (final commit message and report).

## Deviations
- No RFC 8291 Appendix A vector test: I could not verify the vector values offline. The Python golden file is the byte-for-byte check instead.
- VAPID signature is random (ECDSA), so the golden test compares the JWT header and claims and verifies the signature; it does not compare the signature bytes.
- The brief asks for an open PR; I did not push or open one because the orchestrator said never push.
- Go JSON claims are built as literal strings with escaping like Python's json.dumps(ensure_ascii=False default, no HTML escape); non-ASCII subject differences are untested.

## Questions
- Toolchain: go.mod requires go 1.25; local go is 1.24.7 (module downloads worked through the proxy).
- App/.venv must be created (`python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt`) for the i18n check and the golden script run by the owner.

## Owner steps left
None until the executor work continues. Pushing and PR are the owner's call.

## 0687 (pushsend, Go): section
Commit 51f9930 "0687 step 1: go pushsend port". 15 DB tests written, run in CI (ci.yml sets UBYHOST_TEST_DATABASE_URL); they skip locally.
Differences from Python:
- An endpoint outside PUSH_HOST_SUFFIXES is treated as gone (not sent).
- SUPPORT_EMAIL is a Go constant (support@ubyhost.com), not read from config.
- Sends time out after 10 s.
- Redirects are not followed.

## 0688 (test route and push job, Go): section
Commit d647d65 "0688 step 1: Go push test route and push job kind".
- `POST /account/push/test` is `pushweb.TestHandler(sender, getenv, now)`: CSRF, signed-in account only (401), 5 tries per hour (429) on rate_limit_event scope `push_test`, then `pushsend.SendTest`. Outcome other than "sent" gives 502 with the Python error JSON; success gives `{"ok":true,"message":...}`.
- Job kind `push`: `Drain(ctx, 50)` every 1 minute (goIntervals are minutes). `Drain` returns nothing while UBYHOST_WEB_PUSH is off.
- i18n: pushweb gains push.error.rate_limited, push.error.test_failed, push.test_sent (regenerated with App/.venv of the main checkout).

Commands (tails):
- `gofmt -l .`: empty. `go vet ./...`: clean. `go build ./...`: clean.
- `go test ./internal/webpush/ ./internal/pushsend/ ./internal/pushweb/ ./cmd/... -count=1`: all `ok`. DB tests SKIP (no UBYHOST_TEST_DATABASE_URL locally): pushweb TestPushTestRoute, TestPushTestRouteFailures, TestPushDeviceRoutes; pushsend 12 DB tests. CI must run them.
- `go_host_i18n.py --check`: pass. `context_lint.py`: OK.

Deviations:
- The brief says the 11th test in an hour gets 429. Python TEST_MAX_PER_HOUR is 5, so the 6th gets 429. Tests follow Python.
- Brief step 4 mentioned a `public_key` in subscribe: subscribe returns only `{"ok":true}`, so there was nothing to check.
- The job interval is 1 minute, not 60 s (goIntervals are minutes).
- The route does not check enabled(), as push.py push_test does not; only the job is off when disabled.
- TestHandler takes *pushsend.Sender (not Pool) so tests can inject the client and the endpoint check.
- Local Postgres password cannot be reset here, so the DB tests were compile-checked (go vet) only.

Questions:
- Caddy/deploy: `/account/push/test` must route to Go (the Python route is still served for it until then). Not changed here.

Owner steps left: none for this branch. Not pushed.
