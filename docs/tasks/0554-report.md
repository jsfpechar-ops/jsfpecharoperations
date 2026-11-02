# 0554 report: Go G5d-3d SubmitBatch

Status: review

## Files changed
- New: `go/internal/ubyport/submit.go` (SubmitBatch, Sender, BatchPair, BatchDeps, BatchResult, branch helpers).
- New: `go/internal/ubyport/submit_test.go` (7 database tests, reusing claimTestPool, notifyApartment, notifyStay, notifyDevice, storeTestCrypto, storeRead, storeDecrypt, effectsCount, effectsText).
- `docs/tasks/0554-go-g5d3d-submit-batch.md` (Status line only).
- This report.
- `client.go` not changed: `Error.RequestXML` already exists and `Submit` already sets it on the in-doubt paths.

## Commands
- `gofmt -l .` empty; `go vet ./...` clean.
- `go test ./internal/ubyport/ -count=1` with UBYHOST_TEST_DATABASE_URL set:
  `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport 25.046s`
- Verbose run: 54 PASS, 0 SKIP.
- SubmitBatch tests (all PASS): accepted, rejected (alert params bytes, one email_outbox, one push_outbox), outcome unknown (encrypted envelope, guest pointers, critical alert, mail), auth error (two alerts), transport error (guests unchanged), accepted without receipt (receipt_missing with params), all-demo (noop, no sender call, no rows).
- `python3 scripts/context_lint.py`: see the commit step below.

## Deviations and decisions
- Reading range: the brief said 1541-1817; the audit call sits at 1835-1841, which I also read.
- Non-ubyport errors from the Sender are returned as-is with the submission row left `running`, as Python's uncaught exception would leave it.
- `BatchResult.Stamp` carries the pseudo stamp; `State` and `Error` are filled as Python's dict.
- Stuck names: `PlanOutcome` returns exhausted guest ids, so names are resolved through the BatchPair map (same first-seen grouping).
- Logs carry ids only (no reason text, addresses or envelopes).

## Owner steps left
None. Nothing calls this code yet; 0555 wires it.
