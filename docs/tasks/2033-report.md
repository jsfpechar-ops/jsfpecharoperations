# 2033 report — Go claim-start staging proof

Status: blocked

## Staging build tested

`ffd8c17bc8193e6379fc7d6efda8f0dddd7bd51c` (`GET /healthz` 200, `database_ok` true). Signup and login **200** (signup was 404 on older audit). `GET /apartments` → **303** `/login?next=/apartments` (NO_LOGIN off). Public guest probes only: invalid token `GET /l/…/1` → **404**; bare `POST …/party` → **403** (CSRF).

## Dependency cleared

Brief **2022** merged; device gate **Option 3** (port Python) in `docs/tasks/2022-report.md`. Gate logic present on this SHA in `stay_claim.go`; party mail-on path still **does not** call `start_claim` (same comment at line 420 in `party.go` at `ffd8c17`).

## Commands

```text
go test ./internal/web/guest -run '^TestGuestFormCSRFRoundTrip$' -count=1 -v
→ SKIP: UBYHOST_TEST_DATABASE_URL not set (PASS package)
curl /healthz, /signup, /login, /apartments, guest paths → statuses above
```

## Acceptance (§7)

- [ ] Mail-enabled party → claim message (blocked: no `start_claim` wire-up + no host/mail-sink fixture here)
- [ ] EN/CS party → confirm → registration (owner-only: magic-link host session, disposable stay, console mail readback)
- [ ] Mail-disabled branch (needs host fixture + profile switch)
- [x] Device-gate decision recorded (2022 report)

## Owner-only

1. Sign in on staging (magic link to audit inbox); create or reuse disposable stay; copy guest link + PIN (never paste in repo).
2. Confirm `UBYHOST_MAIL_BACKEND=console` and share **redacted** claim-link path shape from Settings after party submit (expected after exact-diff).
3. Assign Tier A brief for `party.go` → `StartClaim` / mail enqueue + DB tests; deploy to staging; re-run step 3 of brief 2033.

## Deviations

No application edits (brief §3). Headless Chromium screenshot attempt timed out; used HTTP checks only.