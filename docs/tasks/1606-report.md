# 1606 report

## 1. Files changed

```
e39b331e1 1606 step 1
```

```
e39b331e1

 App/scripts/exports_routes_golden.py               |  277 +++
 App/tests/test_go_exports_routes.py                |   40 +
 go/cmd/ubyhost-web/register_web_exports_test.go    |    5 +-
 go/internal/web/exports/housebook.go               |  111 +-
 go/internal/web/exports/housebook_zip.go           |  113 +
 go/internal/web/exports/housebook_zip_test.go      |   27 +
 go/internal/web/exports/i18n.json                  |    6 +
 go/internal/web/exports/i18n_keys.txt              |    2 +
 go/internal/web/exports/routes.go                  |    2 +
 go/internal/web/exports/routes_golden_test.go      |  272 +++
 go/internal/web/exports/routes_inventory_test.go   |    3 +-
 .../exports/testdata/exports_routes_golden.json    | 2291 ++++++++++++++++++++
 12 files changed, 3103 insertions(+), 46 deletions(-)
```

## 2. Commands (last 5 lines each)

**Step 0** — 1605 commits present; pre-replace hashes OK; no `housebook_zip.go`; 12 sidecars.

**Step 1** — all 12 `sha256sum -c` lines `: OK`.

**Step 2** (`gofmt` / `go build` / `go vet`) — no output.

**Step 3** — after `apt-get install postgresql-16`, `server started` on port 55706.

**Step 4 Go:**
```
ok  	.../go/internal/web/exports	1.816s
ok  	.../go/cmd/ubyhost-web	0.096s
```
Named: 6× `--- PASS`, 2× `ok`, no SKIP/FAIL.

**Step 4 Python:**
```
......                                                                   [100%]
6 passed in 7.13s
```

**Step 5** — `server stopped`.

**context_lint** — see step 6 commit output.

## 3. Acceptance (§7)

- [x] Step 1: 12/12 `: OK`
- [x] Step 2: silent
- [x] Step 4: 2+2 `ok`, 6 `--- PASS`, 0 SKIP; Python `6 passed`
- [x] `1606 step` commits touch only §3 paths
- [x] No `UBYHOST_GO_PATHS`, Caddy, compose, or `App/app/` changes; branch `wt-1606` only (no push to `main`/`go-wave3` in brief sense)
- [x] UI N/A

## 4. Deviations

- Host had no PostgreSQL 16; installed `postgresql-16` via apt and used `sudo` for `/var/tmp/pg1606` ownership so step 3 could run (user: skip no test).
- Known Python/Go gaps E1–E10 unchanged (brief §2).

## 5. Questions

None.

## 6. Owner steps

When the 1605–1609 thread merges: add `/housebook/pdfs.zip` to `UBYHOST_GO_PATHS` (full list in brief 1609).