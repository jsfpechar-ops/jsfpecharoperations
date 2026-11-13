# 1231c report: Go mail delivery part 3 (tests)

Status: review

## 1. Diff stat (commits 1231c step 1-2 and step 4)

```
go/internal/mail/outbox_golden_test.go  | new
go/internal/mail/outbox_drain_test.go   | new
docs/tasks/1231c-go-mail-delivery-tests.md | Status line
docs/tasks/1231c-report.md              | new
```

## 2. Commands

Step 0: branch `task/1230-track-a`; `func SendNow` 1; cases.json hash matches `84faacbe...99b0`; new test files absent 2; `git status --short` empty.

Step 1 sha256 (both match):
```
b28cded804dce01ce21dbdb37711f76bb2bd0608e761a0a559e7a5b7934c9468  go/internal/mail/outbox_golden_test.go
850985f61646cc11fce0f4fa6ab328dc049ceb3211933ef0f3f94fc73eb089c5  go/internal/mail/outbox_drain_test.go
```

Step 2: `gofmt -l` empty (`GOFMT_OK`); `go vet ./...` clean.

Step 3 (deviation, see §4): Go mail tests run against the given database:
```
UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5440/postgres go test ./internal/mail/ -count=1 -v
--- PASS: TestCancelledWithGuestsMatchesPython
--- PASS: TestCancelledWithGuestsRefusesUnknownVariant
--- PASS: TestBuildDoubleBooking
--- PASS: TestDrainConsole
--- PASS: TestDrainTerminalFailureRaisesAlert
--- PASS: TestDrainResetsStaleSending
--- PASS: TestDrainSESRequest
--- PASS: TestDrainSESErrorsDoNotLeakAddresses
--- PASS: TestPurge
--- PASS: TestSendNow
--- PASS: TestNoDetailsRendererPutsRowBack
--- PASS: TestGoldenDelivery
--- PASS: TestGoldenAddressHelpers
--- PASS: TestSigV4MatchesBotocore
--- PASS: TestConfigFromEnv
--- PASS: TestDetailsMarkers
--- PASS: TestRawMessageNonASCIIAddressName
--- PASS: TestSubmissionProblemMatchesPython
--- PASS: TestOtherLanguagesAreRefused
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail	3.230s
```
No SKIP lines.

Context lint: see §3.

## 3. Acceptance

- [x] The two test file hashes match.
- [x] gofmt empty, `go vet ./...` clean, all mail tests pass with 0 skipped.
- [x] Context lint passes (run after this report was written).

## 4. Deviations

- Step 3 said to start a new PostgreSQL 16 on port 55431. Not done: the orchestrator gave the Postgres at 127.0.0.1:5440 for this run, and that is what the tests used.
- Helper written to the scratchpad, not `/tmp`. Same hashes.

## 5. Questions

None.

## 6. Owner steps left

None. CI runs the Go tests.
