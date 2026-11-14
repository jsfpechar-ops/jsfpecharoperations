# 1596 report

## Files changed

- `go/internal/web/onboarding/demo_reset.go` (create)
- `go/internal/web/onboarding/demo_reset_test.go` (create)
- `go/internal/web/onboarding/testdata/demo_reset_golden.json` (create)
- `go/cmd/ubyhost-web/register_web_onboarding_demo.go` (create)
- `go/cmd/ubyhost-web/register_web_onboarding_demo_test.go` (create)
- `App/scripts/go_demo_reset_golden.py` (create)
- `App/tests/test_go_demo_reset_golden.py` (create)
- `docs/tasks/1596-report.md` (create)

Sidecars under `docs/tasks/1596-files/` unchanged (already in repo).

## Commands (last lines)

**Step 1 sha256:** 7× `: OK`

**Step 2 gofmt/build/vet:** (no output)

**Step 3 pytest:** `2 passed in 3.58s`

**Step 5 package tests:** `ok …/internal/web/onboarding`, `ok …/cmd/ubyhost-web`

**Step 5 named -v:** `--- PASS` ×5 (`TestDemoResetMatchesPython`, `TestDemoResetStopsBeforeDeleting`, `TestDemoResetRollsBack`, `TestOnboardingPageMatchesPython`, `TestOnboardingDemoRouteRegistered`); two `ok` lines

**SKIP count:** `0`

**context_lint:** (see run at commit time)

## §7 acceptance

- [x] sha256sum step 1: all 7 OK
- [x] format/build/vet silent
- [x] step 3: 2 passed
- [x] step 5: two ok, 5 named PASS, SKIP 0
- [x] commits only §3 paths (+ report)
- [x] no `UBYHOST_GO_PATHS`, Caddy/compose/env/app Python changes; not pushed to main
- [x] UI: none

## Deviations

- Branch `wt-1596` on `origin/go-wave3` @ `033fd25f7` (coordinator isolation; brief one-branch mode not used).
- VM had no PostgreSQL 16: installed `postgresql-16` via apt and started throwaway instance per brief 1595 step 4 (`/var/tmp/pg55595`, port 55595). Not a repo change.

## Questions

None.

## Owner steps left

Per brief §9: none until data volume writable for `ubyhost-go` and brief 1597 merged, then add `/demo/reset` (with `/demo`) to `UBYHOST_GO_PATHS`.