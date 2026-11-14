# 1595 report: Go onboarding checklist page

## 1. Files changed

`git show --stat` for `1595 step 1` (only step commit):

- `go/internal/palette/linkkey.go` (+15)
- `go/internal/web/onboarding/onboarding_page.go` (+324)
- `go/internal/web/onboarding/onboarding_page_test.go` (+356)
- `go/internal/web/onboarding/onboardingpage/onboarding.tmpl` (+100)
- `go/internal/web/onboarding/onboardingpage/i18n_keys.txt` (+11)
- `go/internal/web/onboarding/onboardingpage/i18n.json` (+209)
- `go/internal/web/onboarding/testdata/onboarding_page_golden.json` (+2051)
- `go/cmd/ubyhost-web/register_web_onboarding_page.go` (+24)
- `go/cmd/ubyhost-web/register_web_onboarding_page_test.go` (+23)
- `App/scripts/go_onboarding_page_golden.py` (+238)
- `App/tests/test_go_onboarding_page_golden.py` (+27)

## 2. Commands (last lines)

**Step 1 sha256:** 11× `: OK`

**Step 2** (`gofmt`, `go build ./...`, `go vet`): no output (deps downloaded on first build only).

**Step 3:**
```
i18n rc=0
.....                                                                    [100%]
5 passed in 3.25s
```

**Step 4 PG:** `server started` on `/var/tmp/pg55595`, port 55595.

**Step 5 bulk:**
```
ok  	.../go/internal/web/onboarding	0.972s
ok  	.../go/internal/palette	2.172s
ok  	.../go/cmd/ubyhost-web	0.083s
```

**Step 5 named (-v):** `--- PASS` for all six (`VisibleLines`, `MatchesPython`, `CreatesSlug`, `TemplateKeys`, `OnboardingRoutes`, `RouteRegistered`); two `ok` lines; no FAIL/SKIP.

**SKIP count (full run -v):** `0`

**context_lint:** `context lint: OK`

## 3. Acceptance (§7)

- [x] sha256 all OK (11 files)
- [x] format/build/vet silent
- [x] Step 3: `i18n rc=0`, `5 passed`
- [x] Step 5: three `ok`, six named `--- PASS`, SKIP `0`
- [x] Step commits only §3 paths (+ report/brief status in step 6)
- [x] No `UBYHOST_GO_PATHS`, Caddy, compose, env, or `App/app/` changes
- [ ] UI/UX gate pending (dormant route; §7 item 7)

## 4. Deviations

- Working branch `wt-1595` per worker isolation (brief template name differs).
- Host had no PostgreSQL 16: installed `postgresql-16` via apt, then ran step 4 init/start as brief specifies.

## 5. Questions

None.

## 6. Owner steps left

None until UX gate on Go `/onboarding` and path switch (see brief Owner steps).