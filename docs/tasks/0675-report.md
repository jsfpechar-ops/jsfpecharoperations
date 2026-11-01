# 0675 report: Go card rail payment link send

Status: review

## Files changed
- Created `go/internal/payments/paylink.go`: `SendPaymentLink` on `StripeOnboarder`, `reasonCS`, `paylinkName`.
- Created `go/internal/payments/paylink_test.go`: 5 DB tests with their own httptest Stripe fake.
- Edited `go/internal/payments/onboarder.go`: `call` takes an optional trailing `stripeAccount ...string` that sets the `Stripe-Account` header. Existing callers unchanged.
- Edited `docs/tasks/0675-go-payment-link-send.md`: Status set to `review`.
- Created this report.

## Commands (last lines)
- gofmt, vet, build, and `-run SendPaymentLink`: `--- PASS: TestSendPaymentLinkStripeErrorHidesKey`, `PASS`, `ok .../internal/payments 1.734s`.
- Full payments package with `UBYHOST_TEST_DATABASE_URL`: `--- PASS: TestWebhookRateLimit`, `PASS`, `ok .../internal/payments 4.653s`. SKIP count 0.
- `python3 scripts/context_lint.py`: run after this report was written (see commit).

## Section 7
- [x] All payments tests pass with the database URL, 0 skipped (16 tests).
- [x] gofmt clean, `go vet` and `go build` clean.
- [x] Diff touches only section 3 files plus this report and the Status line.

## Deviations
- Brief test case "mode off gives ErrStripeOff" cannot occur in Python's order: the account lookup for mode `off` finds no row, so the result is `"", nil` with no call. Tests now cover: test mode with no key gives ErrStripeOff, and mode off gives `"", nil` with 0 requests and 0 usage rows.
- Unknown reason falls back to the key `payments.reason.<reason>`, as the brief says. The DB CHECK constraint already rejects unknown reasons.
- The brief's "open one PR" step is not done, because the instruction was to commit and not push.

## Questions
None.

## Owner steps left
1. Push `claude/project-thread-ach4z4` and open the PR for 0675.
2. Merge with `scripts/merge-pr-on-green.sh` once CI is green.
