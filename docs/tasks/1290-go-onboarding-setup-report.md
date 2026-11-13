# 1290 go onboarding setup report

Status: review

## Files changed (vs a83df54)
- go/internal/web/onboarding/setup.go, routes.go, setup_test.go, routes_test.go, testdata/setup_golden.json (new)
- go/cmd/ubyhost-web/register_web_onboarding.go (new)
- App/scripts/onboarding_setup_golden.py, App/tests/test_go_onboarding_setup.py (new)
- docs/tasks/1290-files/files.txt (read only, already committed), docs/tasks/1290-go-onboarding-setup.md (Status line only)

## Commands (last lines)
- Step 1 sha256 check: 7 x `OK`.
- Step 2 golden write: `wrote .../testdata/setup_golden.json`; sha256 check `OK`.
- §6.1 gofmt and vet: `gofmt-clean`, no vet output.
- §6.2 `go test ./internal/web/onboarding/ ./cmd/ubyhost-web/`: two `ok` lines (TestOnboardingRoutes skipped: no UBYHOST_TEST_DATABASE_URL set in this session).
- §6.3 pytest tests/test_go_onboarding_setup.py: `2 passed`.
- §6.4 context_lint: `context lint: OK` (plus a WARN that status.md is older than App/ commits; orchestrator to update at review).

## §7 acceptance
- [x] diff names are only §3 paths and the brief.
- [x] 7 x OK; golden OK.
- [x] §6 commands 1 to 4 as expected.
- [x] `grep -c UBYHOST_GO_PATHS register_web_onboarding.go` = 1.

## Deviations
- Report path is `1290-go-onboarding-setup-report.md` because `docs/tasks/1290-report.md` on main is the merged deadlines brief (1290-remove-python-deadlines-job).
- Route tests on PostgreSQL were skipped locally (no UBYHOST_TEST_DATABASE_URL); CI must run them.

## Questions
None.

## Owner steps left
None. Brief is ready for PR review (Tier A: Fable diff review before ready).
