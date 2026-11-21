# 1721 report

Status: review

## Commits

- `1721 step 1` — sidecars, remove `RegisterStayClaim` stub from `wave_routes.go`
- `1721 step 2` — golden script run; dedupe `stay_claim.go` vs 1720 guest helpers

## Commands (last lines)

```
go test ./internal/web/guest/... -count=1 → ok
go test ./cmd/ubyhost-web/... -count=1 → ok (cmd)
pytest tests/test_go_stay_claim_golden.py → 1 passed
gofmt -l → empty
go vet ./internal/web/guest/... → silent
context_lint.py → OK
```

`go test ./internal/web/...` fails on `settings_test` without `UBYHOST_TEST_DATABASE_URL` (pre-existing env gap; guest/cmd rows green).

## §7

- [x] Routes registered; registration test passes
- [x] Golden shape test passes
- [ ] `TestConfirmClaimRace` — needs `UBYHOST_TEST_DATABASE_URL` (skip, not silent pass)
- [ ] Host browser/390px — deferred to 1720 UX gate per brief note

## Deviations

- After #1205 + 1720 on `main`, verbatim sidecar `stay_claim.go` redeclared `writeUnavailable`, `loadApartment`, `guestPinRequired`, `rateBlocked`, `rateRecord`. Renamed helpers to `scWriteUnavailable` / `scLoadApartment`, dropped duplicate rate/pin helpers, fixed `rateBlocked` window to seconds (`int(time.Hour/time.Second)`).

## wave_routes.go

`RegisterParty`, `RegisterFormSave`, `RegisterGuideView`, `RegisterLeonQuestions` stubs remain; `RegisterStayClaim` removed.

## Questions

None.