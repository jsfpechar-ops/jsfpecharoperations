# 1600 report

## Files changed

- `App/scripts/onboarding_wizard_golden_pages.py` (create)
- `App/tests/test_go_onboarding_wizard_pages.py` (create)
- `go/internal/web/onboarding/testdata/wizard_golden_pages.json` (create)
- `go/internal/web/onboarding/wizard_pages.go` (create)
- `go/internal/web/onboarding/wizard_pages_golden_test.go` (create)
- `go/internal/web/onboarding/wizard_pages_test.go` (create)
- `go/internal/web/onboarding/wizardtemplates/police.tmpl` (create)
- `go/internal/web/onboarding/wizardtemplates/property.tmpl` (create)
- `docs/tasks/1600-report.md` (create)

## Commands (last 5 lines)

**sha256sum -c (step 1):** all 8 lines `: OK`.

**gofmt/build/vet (step 2):** (empty).

**go test packages (step 4):**
```
ok  	.../go/internal/web/onboarding	2.968s
ok  	.../go/cmd/ubyhost-web	0.101s
```

**go test -v named (step 4):**
```
--- PASS: TestWizardEntryMatchesPython (0.26s)
--- PASS: TestWizardPagesMatchesPython (0.27s)
--- PASS: TestWizardDoorWindow (0.00s)
--- PASS: TestWizardOperatorSelected (0.00s)
--- PASS: TestWizardTemplatesUseKnownKeys (0.00s)
ok  	.../go/internal/web/onboarding	0.550s
```

**pytest (step 5):** `4 passed in 2.82s`

**context_lint:** (see commit; no errors in non-WARN tail)

## §7 Acceptance

- [x] `sha256sum -c` of step 1 printed `: OK` for all 8 files.
- [x] Format, build and vet printed nothing.
- [x] Step 4: two `ok` packages; 5 named tests `--- PASS`; 0 SKIP; 0 FAIL.
- [x] Step 5: `4 passed`.
- [x] Commits touch only §3 paths (step 1 + step 6).
- [x] No `UBYHOST_GO_PATHS`, Caddy, compose, env, or `App/app/` changes; not pushed to `main`.
- [x] UX gate pending (dormant paths; brief 1602).

## Deviations

- Coordinator branch `wt-1600` (not `task/1600-…`). Installed `postgresql-16` via apt and started throwaway PG on port 55599 (`/var/tmp/pg55599`) — binaries were absent at step 0.

## Questions

None.

## Owner steps

None (path switch in brief 1602).