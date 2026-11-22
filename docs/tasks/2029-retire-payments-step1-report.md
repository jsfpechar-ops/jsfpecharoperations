# 2029 step 1 report

Status: review

## Files changed
- `go/internal/appconfig/payments_hidden.go` — `PaymentsRetired`, retired `/p/*` booking paths, `/pay/*`
- `go/internal/appconfig/payments_hidden_test.go` — retired table
- `go/cmd/ubyhost-web/payments_hidden_test.go` — mux/wrap 404 and open-path cases
- `App/app/config.py` — mirror `PAYMENTS_RETIRED`, `payments_host_path_blocked`

## Commands (last 5 lines)
Go: `ok .../appconfig (cached)` / `ok .../cmd/ubyhost-web 0.083s`
Python: `24 passed in 2.91s`

## §7 (step 1 scope)
- [x] RETIRED=1: listed booking/payment paths blocked in Go tests
- [x] RETIRED unset: existing hidden tests unchanged
- [x] No migration, no secrets

## Deviations
None.

## Questions
None.

## Blocks steps 1b–5
None for step 1. Step 1b still needs `Bookable` false on property template; steps 2–4 need this flag on main first (jobs, webhook, deploy).

## Owner
Merge only via `scripts/merge-pr-on-green.sh`; do not set `UBYHOST_PAYMENTS_RETIRED=1` on server until steps 1–4 merged (per brief owner steps).