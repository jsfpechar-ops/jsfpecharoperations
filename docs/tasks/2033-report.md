# 2033 report — Go claim-start staging proof

Status: review

## Implementation (main, task 2033)

- `go/internal/web/guest/party.go`: mail-on party POST calls `stays.StartClaim` (Python `claim.start_claim`), with Turnstile, `claim_start` rate limit, claimed-session headcount path, and `guest_party` throttle. `partyMailEnabled` now follows `UBYHOST_MAIL_BACKEND` console/ses (was SMTP/SES env only).
- `go/internal/web/guest/party_claim_start_test.go`: unit test for console mail detection.

## Commands

```text
cd go && go test ./internal/web/guest/... -count=1 2>&1 | tail -30  → ok
go test ./internal/web/guest -run TestPartyMailEnabledConsoleBackend -v  → pass
cd App && .venv/bin/python -m pytest tests/test_go_party_golden.py -q  → 1 passed
```

DB-backed `TestGuestFormCSRFRoundTrip` / full claim-start chain: **not run** (`UBYHOST_TEST_DATABASE_URL` unset in agent VM).

## Acceptance (§7)

- [x] Mail-enabled party POST starts claim (code + `stays.StartClaim` mail enqueue)
- [ ] Browser EN/CS party → confirm → registration (owner/staging)
- [ ] Mail-disabled branch unchanged (code path present)
- [x] Device-gate decision (2022)

## Owner-only

1. Deploy branch to staging; run brief 2033 step 3 (disposable stay, console mail readback).
2. Confirm `claim_sent=1` redirect and provisional `reservation_claim` after party submit.

## Deviations

Staging E2E and DB integration tests not executed in cloud agent (no test database).