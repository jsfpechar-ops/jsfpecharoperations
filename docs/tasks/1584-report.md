# 1584 report

## 1. Files changed

```
 go/cmd/ubyhost-web/register_web_stayfees_adjust.go |  25 ++
 .../register_web_stayfees_adjust_test.go           |  16 +
 go/internal/web/stayfees/adjust.go                 | 232 +++++++++++
 go/internal/web/stayfees/adjust_i18n.json          |  17 +
 go/internal/web/stayfees/adjust_test.go            | 458 +++++++++++++++++++++
 docs/tasks/1584-report.md                            |  (this file)
 docs/tasks/1584-go-stay-fee-adjustment-add.md        |  Status: review
```

## 2. Commands (last 5 lines each)

**Step 1 sha256sum -c:** five lines ending `: OK`.

**Step 2** (`gofmt`, `go build ./...`, `go vet`): no output.

**Step 3** throwaway PG: `waiting for server to start.... done` / `server started`.

**Step 4 package tests:**
```
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stayfees	4.694s
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.105s
```

**Step 4 named tests (-v):** seven `--- PASS` (AdjustmentAdd* ×6, TestStayFeesAdjustRouteRegistered); two `ok` lines; no SKIP/FAIL.

**SKIP count:** `0`

**context_lint.py:** `context lint: OK`

## 3. Acceptance (§7)

- [x] sha256sum step 1: all 5 `: OK`
- [x] gofmt/build/vet: silent
- [x] both packages `ok`; 7 named tests `--- PASS`; SKIP 0
- [x] `1584 step 1` commit; paths match §3 sidecars only (report in step 5)
- [x] No UBYHOST_GO_PATHS / Caddy / compose / App changes; not pushed to `main`
- [x] UI N/A (redirect only)

## 4. Deviations

- VM had no PostgreSQL 16 initially; installed `postgresql-16`, then throwaway cluster on port `55583` under `/var/tmp/pg55583` (not CI-only).
- Branch `wt-1584` per coordinator (brief one-big-PR text); no PR opened per assignment.

## 5. Questions

None.

## 6. Owner steps left

None until routing `POST /stay-fees/*/adjustment` to Go (with brief 1582 form).