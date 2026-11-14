# 1594 report

## 1. Files changed

```
dd9f045b4 1594 step 2
b81bfc467 1594 step 1
```

**b81bfc467** — `go/cmd/ubyhost-web/register_web_customers.go`, `go/cmd/ubyhost-web/register_web_customers_test.go`

**dd9f045b4** — `deploy/lightsail/docker-compose.yml` (+7 env keys in `ubyhost-go`)

## 2. Commands (last 5 lines)

**Step 1 sha256sum:** both lines `: OK`

**Step 2 diff:** `7 insertions(+)`, one file changed

**Step 3 gofmt/build/vet:** (no output)

**Step 5 full test:**
```
ok  	.../go/internal/web/customers	5.280s
ok  	.../go/cmd/ubyhost-web	0.088s
```

**Step 5 named tests:**
```
--- PASS: TestCustomerRoutesAllServedByGo (0.00s)
--- PASS: TestCustomerRoutesNeedLogin (0.00s)
--- PASS: TestGoServiceGetsInvoiceEnv (0.00s)
ok  	.../go/cmd/ubyhost-web	0.051s
```

**SKIP count (full verbose run):** `0`

**Step 6 PG stop:** `server stopped`

**context_lint:** `context lint: OK`

## 3. Acceptance (§7)

- [x] sha256sum `: OK` for both sidecars
- [x] Step 3 silent
- [x] Step 5 `ok`, three `--- PASS`, skip count `0`
- [x] `1594 step 1` and `1594 step 2` commits; §3 paths only
- [x] Compose step 2: seven `+` lines only; no `UBYHOST_GO_PATHS`/Caddy/App changes; not pushed (until executor push of `wt-1594`)
- [x] UI: N/A

## 4. Deviations

Host had no PostgreSQL 16; installed `postgresql-16` with apt and started throwaway cluster on `/var/tmp/pg1594`, port `55594` (sudo). Tests ran as specified.

## 5. Questions

None.

## 6. Owner steps left

Per brief § Owner steps (staging UX gate, `.env` `UBYHOST_GO_PATHS`, compose restart, hand checks). Not for the executor.