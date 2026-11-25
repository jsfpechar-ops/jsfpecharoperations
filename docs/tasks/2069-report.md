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
- Synthetic checks cover missing claim refusal with no guest write, wrong apartment, locked access, outsider demo, unknown stay, past reachback and the inclusive reachback boundary. The remaining requested cases and 390 px screenshot remain unverified.

## Deviations and owner steps

- Acceptance remains incomplete pending the remaining requested access cases and screenshot review. No live services, real guest data, deployment, push, or PR used.
