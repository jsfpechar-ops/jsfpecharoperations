# 1587 report

## 1. Files changed

```
 go/cmd/ubyhost-web/register_web_stayfees_guestpay.go  |  23 ++
 go/cmd/ubyhost-web/register_web_stayfees_guestpay_test.go |  16 ++
 go/internal/web/stayfees/guestpay_preview.go           | 233 ++++++++++++++++++
 go/internal/web/stayfees/guestpay_preview_test.go       | 269 +++++++++++++++++++++
 docs/tasks/1587-report.md                               | (this file)
 docs/tasks/1587-go-stay-fee-guest-pay-preview.md        | Status → review
 4 code files + report + brief status; 541 insertions in Go.
```

## 2. Commands (last 5 lines)

**sha256sum -c (step 1):** all four lines `: OK`.

**gofmt / build / vet (step 2):** (silent; only module download noise).

**PostgreSQL init (step 3):**
```
waiting for server to start.... done
server started
```

**go test packages (step 4):**
```
ok  	.../internal/web/stayfees	8.055s
ok  	.../cmd/ubyhost-web	0.111s
```

**named tests -v:**
```
--- PASS: TestGuestPayPreview (0.33s)
--- PASS: TestGuestPayParseRate (0.00s)
ok  	.../internal/web/stayfees	0.341s
--- PASS: TestStayFeesGuestPayRouteRegistered (0.00s)
ok  	.../cmd/ubyhost-web	0.045s
```

**context_lint:** `context lint: OK`

## 3. Acceptance (§7)

- [x] sha256sum `: OK` for all 4 files
- [x] gofmt/build/vet silent
- [x] both packages `ok`; 3 named tests `--- PASS`; SKIP count 0
- [x] commits touch only §3 paths (+ report, brief status)
- [x] no UBYHOST_GO_PATHS / Caddy / compose / Python / main push
- [x] UI N/A

## 4. Deviations

Installed `postgresql-16` via apt (no PG on VM). Throwaway cluster on port 55587 under `/var/tmp/pg55587`. Branch `wt-1587` per coordinator (not brief one-big-PR mode). Pushed `wt-1587` only; no PR.

## 5. Questions

None.

## 6. Owner steps left

None until routing: add `POST /stay-fees/*/guest-pay-preview` to `UBYHOST_GO_PATHS` with other stay-fee paths after guest-pay switch decision.