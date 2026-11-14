# 1581 report: Go stay-fees list page

## 1. Files changed

```
 go/cmd/ubyhost-web/register_web_stayfees_pages.go      |  25 +
 go/cmd/ubyhost-web/register_web_stayfees_pages_test.go   |  23 +
 go/internal/web/stayfees/page_host.go                    | 374 +++
 go/internal/web/stayfees/page_i18n.json                | 719 +++++
 go/internal/web/stayfees/page_i18n_keys.txt            | 152 +
 go/internal/web/stayfees/page_list.go                    | 276 ++
 go/internal/web/stayfees/page_list_test.go              | 360 +++
 go/internal/web/stayfees/pagetemplates/_filter.tmpl    |  73 +
 go/internal/web/stayfees/pagetemplates/stay_fees.tmpl  | 231 ++
 docs/tasks/1581-report.md                                | (this file)
 docs/tasks/1581-go-stay-fees-list-page.md                | Status → review
 9 files changed, 2233 insertions(+) in step 1
```

## 2. Commands (last 5 lines each)

**Step 0:** branch `wt-1581`; all anchor greps `1`; `page_host.go` missing; 9 sidecar `.txt` files.

**Step 1 sha256sum -c:**
```
go/internal/web/stayfees/pagetemplates/_filter.tmpl: OK
go/internal/web/stayfees/pagetemplates/stay_fees.tmpl: OK
```

**Step 2** (`cd go && gofmt -l …; go build ./...; go vet …`): silent (module download only on first build).

**Step 3 PG:** `server started` on port 55581 (`/var/tmp/pg55581`).

**Step 4 tests:**
```
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stayfees	1.432s
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.083s
```
Named tests: `TestPageListPage`, `TestPageListReturnKeepsFilters`, `TestPageRowStatus`, `TestPageHelpers`, `TestStayFeesListPageRegistered` — all `--- PASS`. SKIP count: **0**.

**context_lint:**
```
context lint: OK
```

## 3. Acceptance (§7)

- [x] sha256sum `: OK` for all 9 files
- [x] gofmt/build/vet silent
- [x] both packages `ok`; 5 named tests PASS; SKIP count 0
- [x] step commits `1581 step 1` (+ step 5); paths only §3
- [x] no UBYHOST_GO_PATHS / Caddy / compose / App changes; not pushed to `main`
- [x] UI N/A (dormant route)

## 4. Deviations

Base `go-wave3` at `24d7155b2` (includes merged wt-1580 / `36d126db5`). Worker branch `wt-1581` (not brief’s `task/1581-…`). PostgreSQL 16 was not preinstalled; `apt-get install postgresql-16` then throwaway instance on 55581 — not a repo dependency change.

## 5. Questions

None.

## 6. Owner steps

None until full `/stay-fees` Go stack and UX gate; then add `/stay-fees` to `UBYHOST_GO_PATHS`.