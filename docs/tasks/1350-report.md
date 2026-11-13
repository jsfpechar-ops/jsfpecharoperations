# 1350 report

Status: review

## 1. Files changed (git diff --stat a83df54..HEAD)

9 files, 4482 insertions, 2 deletions: the five §3 code files, the two generated fixtures, and the brief and patch from commit 4220489. `git diff a83df54 -- go/internal/payments/webhook_forward_test.go go/internal/payments/webhook_test.go` is empty.

## 2. Commands (last lines of output)

- `sha256sum` of patch and five code files: all match.
- `sha256sum` of golden.json and booking_i18n.json: all match.
- `gofmt -l ./internal/payments`, `go build ./...`, `go vet ./internal/payments`: no output.
- `go test -count=1 ./internal/payments/...`: `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments` (PASS, DB set).
- `go test -v -run 'Booking|Forward'`: PASS for TestBookingWebhookMatchesPython, TestBookingSwitchOffForwards, TestBookingSwitchOnHandlesInGo, TestBookingDatesAndToken, TestForwardBookingEventTypes, TestForwardPassesPythonStatus, TestForwardPythonDown, TestForwardNotForwarded, TestForwardRejectedAndOff; `ok`.
- `go test -v ./internal/payments/...` SKIP count: 0.
- pytest (4 files): `69 passed in 1.46s`.

## 3. Acceptance (§7)

- [x] Patch and seven file sha256 values match.
- [x] `go test ./internal/payments/...` ok with a database; Booking and Forward PASS, none skipped.
- [x] pytest: 69 passed.
- [x] `git diff --stat a83df54` lists only §3 files.
- [x] webhook_forward_test.go and webhook_test.go unchanged.

## 4. Deviations

- Postgres: used the already-running instance from `/var/tmp/pg1350` on port 55450 (`UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55450/postgres`). The brief's port 55451 is served by another data dir (`/var/tmp/pg1351`), so it was not used. No new instance was started.
- No push and no PR, as instructed by the orchestrator.

## 5. Questions

None.

## 6. Owner steps left

None for this PR (switch stays off). Later steps are in the brief's Owner steps section.
