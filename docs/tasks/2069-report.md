# 2069 report: guest save access gates

Status: blocked

## Changed paths

- `go/internal/web/guest/form_save.go`: picker visibility and reachback eligibility before save, demo and completed-stay proof checks, then the existing claim gate before form processing.
- `go/internal/web/guest/form_save_test.go`: focused refusal case verifies a missing email claim redirects before guest rows are written.

## Checks

- `UBYHOST_TEST_DATABASE_URL=<isolated PostgreSQL 16.2> GOPROXY=off go test ./internal/web/guest/ -run 'FormSaveAccess|FormSaveRoutePattern' -count=1 -v`: both tests passed; no skips.
- `git diff --check`: passed.

## Acceptance evidence

- The handler now applies the visible picker path and the reachback fallback before processing the posted form, and requires the existing claim gate after throttling.
- The synthetic missing-claim refusal leaves guest rows untouched. Other requested access cases and the 390 px screenshot remain unverified.

## Deviations and owner steps

- Acceptance remains incomplete pending the remaining requested access cases and screenshot review. No live services, real guest data, deployment, push, or PR used.
