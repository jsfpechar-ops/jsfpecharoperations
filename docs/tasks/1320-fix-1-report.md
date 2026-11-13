# 1320-fix-1 report

Status: review. Branch task/1320-go-exports, nothing pushed.

## Commits
- `1320-fix-1 step 1`: sidecar copy, nine sha256 values match §2.
- `1320-fix-1 step 4`: sidecars removed, report added, brief Status set to review.

## Step 1 hashes (match §2)
e334bba8 exports_golden.py, f3d84479 1320-go-exports.md, 35731b63 exports.go, c6e70861 exports_test.go, d00c479b guest_json.go, 7e99e33f housebook.go, 39e72aa5 stays.go, d637b5df submissions.go, 968cb833 exports_golden.json.

## Step 3 results
- Golden `--check`: exit 0, no stale or wrote lines.
- gofmt clean, go vet clean.
- `go test ./cmd/ubyhost-web/ ./internal/web/... -count=1 -v`: TestGoldenParity, TestNoOwnerIsAServerError, TestFreshnessUsesTheFractionalClock all PASS; both packages ok.
- `pytest tests/test_go_exports.py tests/test_go_host_i18n.py -rs`: 5 passed, 0 skipped.
- `scripts/context_lint.py`: OK, pre-existing WARN lines only.

## §7 acceptance
- [x] Nine sha256 values match.
- [x] Golden clean; three named Go tests PASS on PostgreSQL; pytest green.
- [x] Diff limited to §3 paths, this brief and the removed sidecars.
- [x] Commits "1320-fix-1 step 1" and "1320-fix-1 step 4"; nothing pushed.

## Deviations
None.

## Questions
None.

## Owner steps left
None.
