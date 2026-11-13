# 1351 report

Status: review

## 1. Files changed

Commits on `task/1351-go-booking-site-logic` (not pushed):

- `52f3992` 1351 step 1: 11 target files copied from the carrier folder (sha256 OK for all 11)
- `765c4ed` 1351 step 3: `go/internal/web/booking/testdata/golden.json` generated (hash `5fb4154237c9155eca42bbd51852323b88786bcfcf7fe85cea9d813e73b64541`, as expected)
- `d1f252b` 1351 step 4: `docs/tasks/1351-files/` removed (5 `.txt` carriers and the SHA256SUMS, git rm)
- this commit: `docs/tasks/1351-report.md`

## 2. Commands

- `sha256sum -c docs/tasks/1351-files/SHA256SUMS` (after copy): 11 lines, all `OK`.
- `cd go && go build ./...`, `go vet ./internal/web/booking/ ./cmd/ubyhost-web/`, `gofmt -l internal/web cmd`: no output (clean).
- `.venv/bin/python scripts/booking_site_golden.py`: `wrote .../golden.json`; sha256 matches.
- `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55451/postgres go test -count=1 ./internal/web/booking/ ./cmd/ubyhost-web/`: `ok` for both packages. Verbose run: 18 PASS, 0 FAIL, 0 SKIP. Database tests ran (Postgres was up).
- `cd App && UBYHOST_TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_go_booking_golden.py tests/test_booking_site.py tests/test_property_page.py tests/test_stripe_connect.py -q -rs --tb=short -x`: 70 passed, 0 skipped.

## 3. Acceptance (§7)

- [x] sha256 of all 11 §3 files matches the list.
- [x] Go build, vet, gofmt clean.
- [x] Golden hash matches.
- [x] Go tests pass with the database; 0 skipped.
- [x] Python tests pass; 0 skipped.

## 4. Deviations

- Not pushed and no PR opened (the executor's instructions say do not push). The owner or orchestrator must push the branch and open the draft PR.
- `Status: review` is written here. The brief's own status line in `docs/tasks/1351-go-booking-site-logic.md` was not changed because it is not in §3.

## 5. Questions

None.

## 6. Owner steps left

1. Push the branch `task/1351-go-booking-site-logic` and open a draft PR (the orchestrator or owner does this).
2. Review and merge when CI is green. Nothing goes live: no path is routed to Go until `UBYHOST_GO_PATHS` is changed (brief §10 step 2 and 3).
