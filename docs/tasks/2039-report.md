# 2039 report: Go address lookup on staging

**Status: blocked** · Staging SHA `ffd8c17bc8193e6379fc7d6efda8f0dddd7bd51c` (matches assignment). `origin/main` after fetch: `7b44a3b01eb1ff39662ba1293da5f201dfb69557`.

## Checks

| Check | Result | Evidence |
|---|---|---|
| `/healthz` version | PASS | `ffd8c17…` |
| Auth profile (no `NO_LOGIN`) | PASS | `/login` email magic-link form EN/CS 200; `/signup` 200 (not 404) |
| `GET /apartments/ruian-suggest` route | PARTIAL | Unauthenticated: HTTP **401**, body `[]` for Vinohradská, Václavské, no-match (Go `ruian_suggest.go`) |
| Known address → suggestions | **BLOCKED** | Host session required; `/apartments/new` → `/login?next=/apartments/new` (0× `data-ruian-suggest`) |
| Select + field fill + JS-off submit | **BLOCKED** | No magic-link redemption (no test-mail sink in executor) |
| Discoverability (street label) | **BLOCKED** | Add-property form not reached |
| `go test … Test.*Ruian` | PARTIAL | 3 PASS; 6 **SKIP** (`UBYHOST_TEST_DATABASE_URL` unset here) |

## Commands (last lines)

```text
curl /healthz → {"status":"ok","version":"ffd8c17bc8193e6379fc7d6efda8f0dddd7bd51c",…}
go test ./internal/web/properties -run 'Test.*Ruian' → 6 SKIP, 3 PASS, ok
curl /apartments/ruian-suggest?q=Vinohradská → 401 []
Chromium: login/signup EN+CS @390/1280; /apartments/new → login redirect
```

Screenshots (executor machine, not in repo): `/opt/cursor/artifacts/2039/login-{en,cs}-{390,1280}.png`, `signup-{en,cs}-{390,1280}.png`, `apartments-new-390.png`.

## §7 acceptance

- [ ] Known staged address + populate fields — **not run** (needs host cookie).
- [ ] Manual entry / no-JS — **not run**.
- [x] Blocked prerequisite documented — **yes** (session + optional RÚIAN rows).

Prior audit on older SHA (`2528d7db4`, `NO_LOGIN`): Vinohradská → **200, count 0** while authenticated bypass active. On `ffd8c17` with auth profile, authenticated lookup not re-tested.

## Failing fixture (for owner rerun)

1. Sign in on staging (magic link via test sink).
2. Open `/apartments/new?lang=en`, street field with `data-ruian-suggest`.
3. Type owner-supplied address from staged `ruian_address`; record `GET /apartments/ruian-suggest?q=…` status and JSON length.
4. Repeat `zzznomatch123` → expect 200 `[]` with manual fields visible.
5. Owning handler: `go/internal/web/properties/ruian_suggest.go`; template: `apartmentnew/apartment_new.tmpl`; JS: `/static/ruian_suggest.js` (200 on staging).

## Deviations

**Done:** SHA verify, unauthenticated API probes, login/signup/page sweep, local Ruian tests, brief copy. **Left:** steps 1–4 authenticated UI, 768 px form shots, RÚIAN row confirmation.

## Questions (owner booleans only)

1. `UBYHOST_RUIAN_ENABLED` on staging (default on unless `off`)?
2. `ruian_address` row count > 0 on staging DB?
3. One public address guaranteed in that dataset?
4. Test-mail sink window for magic-link session?

## Owner steps

1. Confirm Go serves `GET /apartments/ruian-suggest` on `ffd8c17` (yes unauthenticated; 401 expected).
2. Share row count + sample query that must hit.
3. Grant test-mail access; executor reruns 2039 steps 1–4 on same SHA.

**Files changed:** `docs/tasks/2039-go-address-lookup-staging.md`, `docs/tasks/2039-report.md`.