# 1543 report: Go booking checkout, direct payment requests

Status: review (one big PR mode, local branch go-wave3, no push, no PR)

## Files changed
- go/internal/payments/qrdatauri.go, qrdatauri_test.go (new, copied from sidecar, sha256 OK)
- go/internal/web/booking/direct.go, direct_test.go (new, copied from sidecar, sha256 OK)
- go/cmd/ubyhost-web/register_web_booking_checkout.go (step 2 patch, 2 insertions, 1 deletion)

Patch hash 2ff76e46fc319fc506361d0d84338ee413b486ead4e813120d93b749f99e004d matched. Anchor grep matched, git apply --check passed.

## Commands
- go build ./... : no output
- go vet (payments, web/booking, cmd/ubyhost-web) : no output
- gofmt -l internal cmd : no output
- go test -count=1 -v ./internal/payments/ ./internal/web/booking/ ./cmd/ubyhost-web/ with UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5622/postgres : ok, ok, ok. 151 PASS lines, 0 FAIL, 0 SKIP.

## Section 7
- [x] Step 3 hashes OK, patch hash matches
- [x] Steps 1 and 2 present in git log
- [x] Step 2 changes only register_web_booking_checkout.go
- [x] Three packages ok with database set
- [x] grep -c Direct returns 2

## Deviations
None. PostgreSQL 16 started on port 5622 under /var/tmp/pg1543, stopped and removed afterwards.

## Owner steps left
None. Nothing goes live on merge (brief 1550 gives the switch order).
