# 2032 report

Status: blocked

## Files changed

- `go/internal/web/guest/party.go` — `partySizeHandler` uses `OpenLink`, `pinRedirect`, and `apartment.PermalinkToken` for scoped stay load.
- `go/internal/web/guest/csrf_forms_test.go` — party subtest uses current slug GET; POST loop asserts 303 for slug and permalink token.
- `docs/tasks/2032-go-guest-party-slug.md` — brief copy.

## Commands (last 5 lines)

`go test ./internal/web/guest -run '^TestGuestFormCSRFRoundTrip$' -count=1 -v` (no `UBYHOST_TEST_DATABASE_URL`):

```
--- SKIP: TestGuestFormCSRFRoundTrip (0.00s)
PASS
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/guest	0.033s
```

`go test ./internal/web/guest -run '^$'` (compile):

```
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/guest	0.025s [no tests to run]
```

Guest browser / geometry (`test_guest_browser_e2e.py`, test-map row): not run — no disposable Postgres/App stack in this VM.

Staging browser (EN/CS, copy-link, PIN, party POST): not run — needs owner deploy.

## Acceptance (§7)

- [ ] Slug + permalink 303 with valid CSRF — needs DB test URL.
- [ ] Negative paths + persistence — not exercised here.
- [ ] 390/1280 screenshots — not captured.

## Deviations

Done: steps 1–2, compile check. Left: §6 DB test with 0 skips, browser/geometry, staging screenshots.

`UBYHOST_TEST_DATABASE_URL`: unavailable (no PostgreSQL 16 / `postgres` user on VM).

## Questions

None.

## Owner steps

1. Review draft PR; run `cd go && UBYHOST_TEST_DATABASE_URL=… go test ./internal/web/guest -run '^TestGuestFormCSRFRoundTrip$' -count=1 -v`.
2. Run guest browser tests from test-map with 0 skipped.
3. Deploy branch to isolated staging; complete §7 browser checks and attach screenshots.
4. Merge via `scripts/merge-pr-on-green.sh` when green (not from this session).