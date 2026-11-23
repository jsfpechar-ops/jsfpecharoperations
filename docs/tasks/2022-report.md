# 2022 report — claim device gate

Status: review

## UbyPort rule

Filing guard is `claim_sendable` / submission state machine (`docs/UBYPORT_CORE.md` §What “works” means). The guest device gate only limits who may edit registration data before that; it does not replace `claim_sendable`.

## Four device states (`ubyhost_claim` cookie, `reservation_claim.token_version`)

| Device cookie | Python (`_require_claim_session`) | Go (`formPagesRequireClaim` / stay hub) |
|---|---|---|
| None | 303 → stay hub (claim ask) | 303 → stay hub |
| Stale version | 303 | 303 |
| Other reservation | 303 (no match) | 303 |
| Correct stay+version | Proceed | Proceed |

Mail off or host session: gate skipped (both stacks).

## Gate after this brief

**On** whenever mail is enabled (`console`/`ses`), matching Python. Not a separate feature flag. Removed unused `stayClaimDeviceGate = false` (misleading dead code).

## Owner decision (asleep → safest default)

**Option 3 — port Python exactly** (2026-11-23, executor). No new user-visible switch. Second device must re-claim after mail confirm, same as production Python.

## Files changed

`go/internal/web/guest/stay_claim.go`, `form_pages_claim_gate_test.go`, `docs/context/known-issues-recent.md` (K-PAR02).

## Commands

```text
go build ./... && gofmt -l ./internal ./cmd  → (form_pages_claim_gate_test.go only, fixed)
go test ./internal/web/guest/... ./cmd/ubyhost-web/... -count=1  → ok
```

DB-backed gate tests skip without `UBYHOST_TEST_DATABASE_URL`; CI runs them.

## Acceptance

- [x] Four cookie states tested (`TestDeviceHoldsClaimCookieRoundTrip`, `TestFormPagesRequireClaim*` with DB in CI)
- [x] Route: `TestFormPagesNewRouteRedirectsWithoutClaim`
- [x] Gate state and decision recorded
- [ ] `go_parity_check --all` and `page_parity_audit` not run here (no local PG :5433)

## Deviations

Implementation already matched Python on `main`; work was tests, dead-flag removal, documentation.