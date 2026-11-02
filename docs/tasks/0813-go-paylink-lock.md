# 0813: Go payment Send makes one Stripe link even on a double click

Status: todo
Depends on: none | Base commit: origin/main | Branch: task/0813-go-paylink-lock
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`SendPaymentLink` in `go/internal/payments/paylink.go` reads the request, calls Stripe and stores the link with no lock. Two Send clicks at once create two live Stripe payment links, so a guest could pay twice. Python fixed the same bug in PR #699 (`App/app/payment_links.py` `send`): take a per-row advisory lock in a transaction, re-read the row under the lock, reuse an active stored link, else create, store, commit. This must be fixed before Stripe moves to Go (cutover step 6).

## 2. Context

Python key: `pg_advisory_xact_lock(hashtext('payment_request'), id)`. Go already uses this pattern, for example `go/internal/ubyport/recover.go` line 29:
`tx.Exec(ctx, "SELECT pg_advisory_xact_lock(hashtext($1), $2)", "submit_apartment", int32(aptID))`. Use the same name `"payment_request"` and `int32(requestID)` so Python and Go wait on the same lock.

`s.Pool` is a `*pgxpool.Pool`. The Stripe calls (`s.call`) happen while the transaction is open, as in Python. The audit row stays after the commit (Python writes it after the `with` block).

## 3. Files

| Path | Action |
|---|---|
| `go/internal/payments/paylink.go` | edit `SendPaymentLink` |
| `go/internal/payments/paylink_test.go` | add one test |
| `docs/tasks/0813-report.md` | create |

No other file may change.

## 4. Steps

1. Keep the first part (request read, rail check, account read, state check, `s.guard`) as is. Then replace the part from `if linkID != "" {` down to the `paylinkStampSQL` Exec with:
   - `tx, err := s.Pool.Begin(ctx)`; `defer tx.Rollback(ctx)` (ignore its error).
   - `tx.Exec(ctx, "SELECT pg_advisory_xact_lock(hashtext($1), $2)", "payment_request", int32(requestID))`.
   - Re-read under the lock: `tx.QueryRow(ctx, paylinkRequestSQL, requestID).Scan(&id, &owner, &rail, &reason, &amount, &linkID)`; `pgx.ErrNoRows` returns `"", nil`.
   - If `linkID != ""`: the existing GET; if `old.Active`, return `old.URL, nil` (the deferred rollback ends the tx).
   - Build the form from the re-read values and POST, exactly as now.
   - `tx.Exec(ctx, paylinkStampSQL, created.ID, stamp, requestID)`, then `tx.Commit(ctx)`; any error returns it.
   - Then the existing `audit(...)` call on `s.Pool`, then return `created.URL`.
2. Test `TestSendPaymentLinkOverlapCreatesOneLink`, modelled on `TestSendPaymentLinkFresh` (same `testPool`, `paylinkSeed`, `newPaylinkFake`, `paylinkOnboarder`). Make the fake's POST block until released: add an optional `gate chan struct{}` and `inCreate chan struct{}` to `paylinkFake`; in the handler, for the POST, if `gate != nil` signal `inCreate` (non-blocking) and wait on `gate` BEFORE taking `f.mu`. After the first POST returns, the fake must answer GETs for `plink_1` as active: set `f.links["plink_1"] = map[string]any{"id": "plink_1", "url": "https://buy.stripe.test/plink_1", "active": true}` in the test before releasing the gate. Start call A in a goroutine, wait for `inCreate`, start call B in a goroutine, sleep 200 ms, close `gate`, wait for both. Assert: no errors, both URLs `https://buy.stripe.test/plink_1`, exactly one POST in `fake.requests()`, stored link `plink_1`, one `payment_link_created` audit row.
3. Run the existing paylink tests: they must still pass unchanged.

## 5. Do not touch

Python, other Go packages, the SQL constants' text. No new dependency.

## 6. Commands

From `go/`: `go vet ./internal/payments/ 2>&1 | tail -5`, `gofmt -l internal/payments | tail -5` (prints nothing), `go build ./... 2>&1 | tail -5`. The DB tests need `UBYHOST_TEST_DATABASE_URL`; if it is unset they skip locally and CI runs them: say so in the report. If a local Postgres is reachable, run `go test ./internal/payments/ -run SendPaymentLink 2>&1 | tail -15`.

## 7. Acceptance

- [ ] vet, gofmt, build clean; new test compiles (`go test -count=1 -run XXX ./internal/payments/` builds the test binary).
- [ ] Only section 3 files changed.

## 8. Stop and ask

The function no longer matches section 2; a test fails twice; 25 tool calls.

## 9. Report

`docs/tasks/0813-report.md`: files, commands with their last lines, deviations.
