# 2036 report: Go guide workflow staging acceptance

**Status: blocked** (host and guest sessions missing; §8)

**Staging build (owner-confirmed, not verified in-app):** `ffd8c17bc8193e6379fc7d6efda8f0dddd7bd51c`  
**Brief base commit:** `bd961426570f07a214f9840bf165a0bca397b450`  
**When:** 2026-11-23 UTC

## Commands

```text
go test ./internal/web/ai -run 'TestGuideImportRoute' -count=1 -v
--- SKIP: TestGuideImportRoute (0.00s)
    guide_import_test.go:47: UBYHOST_TEST_DATABASE_URL is not set
PASS
ok  	.../go/internal/web/ai	0.015s
```

Code anchors present: POST import route in `guide_import.go`; `id="leon-setup-import"` in `leon_setup.tmpl`.

## Staging checks (unauthenticated)

| Check | Result | Evidence |
|---|---|---|
| Signup enabled | **PASS** | `GET /signup?lang=en` → 200 (was 404 on prior audit) |
| Login email-only | **PASS** | Email field + “Send me a login link”; no `type="password"` |
| GET `/apartments/1/guide/import` | **INFO** | HTTP **422** (POST-only; not an import completion test) |
| GET `/apartments/1/guide` | **BLOCKED** | 303 → `/login?next=…` (no host session) |
| GET `/apartments/1/leon/setup` | **BLOCKED** | 303 → login (route exists; eligibility unverified) |
| Manual card CRUD | **BLOCKED** | Needs logged-in host on eligible property |
| POST import via Leon form | **BLOCKED** | Needs host session + `guide_import` fixture |
| Guest guide EN/CS | **BLOCKED** | Needs approved guest link/PIN (2033) |

Screenshots: `docs/tasks/media/2036/` (login/signup 390&1280, import GET 422, login redirects for guide/leon).

## §7 acceptance

- [ ] Manual card persisted — **BLOCKED**
- [ ] Import via real form → drafts, unpublished — **BLOCKED**
- [ ] Leon preview (eligible / ineligible) — **BLOCKED**
- [ ] Authorized guest content — **BLOCKED**

## Deviations

- `TestGuideImportRoute` skipped locally (no disposable DB URL).
- No magic-link inbox or staging password; could not complete steps 1–3.

## Follow-up (if host session available)

- **Import:** `(*guideServer).importPost` — expect POST 303 + queued row; GET 422 is expected.
- **Leon:** `leonEntry` — expect 200 with `leon-setup-import` when `leon` + provider eligible; 404/redirect otherwise.

## Owner steps

1. Send a one-time login link for the synthetic property host (or enable `UBYHOST_STAGING_LOGIN_PASSWORD` and share non-secret test login).
2. Confirm `UBYHOST_AI_FEATURES` lists `leon,guide_import` for that property and that a mocked provider fixture is approved.
3. Share a redacted guest stay URL + PIN for published-card verification (after 2033 if claim-gated).
4. On `/settings/help` or technical settings, confirm deployed git SHA matches `ffd8c17…`.

## Questions

None beyond the blocked preconditions above.