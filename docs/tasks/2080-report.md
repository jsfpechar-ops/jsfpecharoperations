# 2080 report: Go health data volume

Status: review

## Changed paths

- `go/cmd/ubyhost-web/main.go`: health now probes the effective `UBYHOST_DATA_DIR` (default `data`) by creating, closing, and removing a unique empty file. Either a failed probe or database check returns 503; the response does not include the local path.
- `go/cmd/ubyhost-web/main_test.go`: added writable, invalid-directory, database failure, combined failure, response flags/status, and probe cleanup coverage using synthetic fixtures.

## Commands and results

- `gofmt -w cmd/ubyhost-web/main.go cmd/ubyhost-web/main_test.go` — passed.
- `go test ./cmd/ubyhost-web/ -run 'HealthzDataDirectory|Health|Wrap' -count=1 -v` — passed: 3 tests matched, 4 health combinations passed, 0 skipped.

  ```text
  --- PASS: TestWrapSetsHardenHeaders (0.00s)
  === RUN   TestWrapRouteHeaderWins
  --- PASS: TestWrapRouteHeaderWins (0.00s)
  PASS
  ok   github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web  1.423s
  ```

- `git diff --check` — passed.

## Acceptance

- [x] Writable directory and database return 200 with both flags true; failure of either returns 503 and its flag false.
- [x] The probe leaves no test file behind.

## Deviations and owner steps

No deviations. Review the writable and failure evidence before approval. No live volume, deployment, push, PR, or merge used.
