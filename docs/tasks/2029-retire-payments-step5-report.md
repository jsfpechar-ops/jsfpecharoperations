# 2029 step 5 report

Status: review

## PR
https://github.com/jsfpechar-ops/jsfpecharoperations/pull/1268 (draft; base `cursor/retire-payments-step1-47ba`)

## Files changed
- `go/internal/web/booking/templates/terms_en.html`, `terms_cs.html` — short unavailable note
- `App/app/templates/_booking_terms_en.html`, `_booking_terms_cs.html` — mirror
- `docs/privacy/ROPA.md` — Stripe/booking-site row marked dormant
- `docs/privacy/RETENTION.md` — `payment_request`, `site_booking` rows marked dormant

## Commands (last 5 lines)
```
context lint: OK
```

## §7 (step 5 scope)
- [x] `/terms/booking` templates show unavailable note (EN/CS, Go + Python)
- [x] ROPA/RETENTION dormant marking, retention lines kept
- [x] No migration, no secrets

## Deviations
ROPA/RETENTION had no prior Stripe/booking-site table rows on this branch; added rows with dormant note (brief asked to mark existing promises). No `terms_vi` / `_booking_terms_vi.html`: `/terms/booking` is en/cs only (`go/internal/web/booking/pages_test.go` — `?lang=vi` falls back to cs). CI shard 3: updated `test_booking_terms.py` (PR-caused; policy-name asserts replaced with unavailable note).

## Questions
None.

## Owner
Merge after steps 1–4; lawyer may bump terms version separately.