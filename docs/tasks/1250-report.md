# 1250 report: guide import job in Go

Status: review

## Result
- New `go/internal/anthropic` (thin net/http client for Anthropic and Mistral, budget caps, `ai_usage` ledger) and `go/internal/guideimport` (Apify fetch, trim, page prefill, card merge, job), registered as kind `guide_import` (60 min) in `register_job_guide_import.go`. Off until `guide_import` is in `UBYHOST_GO_JOB_KINDS`.
- No new dependency: go.mod and go.sum unchanged.
- Parity: `App/scripts/guide_import_golden.py` writes the two `testdata/golden.json` files; Go tests reproduce them. Re-running the script leaves git status clean (Python 3.13).

## Verification
- 19/19 sha256 OK against the brief; gofmt, go vet, go build clean.
- `UBYHOST_TEST_DATABASE_URL=... go test -count=1 ./internal/guideimport/... ./internal/anthropic/... ./cmd/ubyhost-web/...`: 3 ok, Postgres tests ran (queue fetch and page fill, failure/budget/stale, merge, model-failure attempts, ledger).

## Known gaps
- The 80% AI budget mail is not sent from Go (needs `go/internal/mail`); Go logs a warning once per feature and month.
- The Go runner raises `job_failed` after 5 failed attempts; Python on the first.
- Python never downloads listing photos on import (it reads photo URLs from the trimmed data, which has none); Go keeps that behaviour.

## Deviations
- Code blocks were removed from the brief after execution to fit the context-lint cap; the sha256 list still pins every file.
- fix-1 (brief 1250-fix-1): cancelled fetch fails the row, retry-after on the model retry, dropped log as JSON, 4 new Postgres tests; see the fix-1 report.
