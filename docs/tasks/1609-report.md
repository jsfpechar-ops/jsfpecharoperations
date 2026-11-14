# 1609 report

## 1. Files changed

```
e1f18e9a3 1609 step 1
```

`git show --stat --format=%h e1f18e9a3`: 9 files (purge.go, purge_test.go, owner.go, retention.go, routes.go, i18n*, routes_inventory_test.go, register_web_exports_test.go).

## 2. Commands (last lines)

**Step 0:** 1608 steps present; retention/routes hashes OK; purge.go and owner.go absent; 9 sidecars.

**Step 1 sha256sum -c:** nine `: OK` lines.

**Step 2:** `gofmt -l` empty; `go build ./...` and `go vet` exited 0 (first build printed module download lines only).

**Step 3:** Installed `postgresql-16` (no binaries initially); then `server started` on port 55709.

**Step 4 Go:**
```
ok  	.../internal/web/exports	4.288s
ok  	.../cmd/ubyhost-web	0.112s
ok  	.../internal/retention	1.411s
ok  	.../internal/photosweep	0.602s
```
Nine named tests: all `--- PASS`, no SKIP/FAIL.

**Step 4 Python:** `5 passed in 7.33s`

**Step 5:** `server stopped`

**context_lint:** `context lint: OK`

## 3. Acceptance (§7)

- [x] Step 1: 9× `: OK`
- [x] Step 2: no fmt/vet findings (cold `go build` downloads only)
- [x] Step 4: 4+4 `ok`, 9× PASS, 5 Python passed
- [x] Commits: `1609 step 1` (step 6 adds report)
- [x] No UBYHOST_GO_PATHS / deploy / App app changes; not pushed yet

## 4. Deviations

- Step 3: host had no PostgreSQL 16; installed `postgresql-16` via apt to run step 4 (user assignment: skip no test). Used `sudo` for `/var/tmp/pg1609` and `postgres` user.

## 5. Questions

None.

## 6. Owner steps left

Per brief §9 Owner steps: do not add `/settings/purge-expired` to `UBYHOST_GO_PATHS` until `/data` is writable on `ubyhost-go` and retention dry-run counts match (E6, E10).

Known diffs E1–E10 unchanged (brief list).