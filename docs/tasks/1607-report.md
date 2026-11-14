# 1607 report

## 1. Files changed

```
05e82416e 1607 step 1
```

```
05e82416e

 go/cmd/ubyhost-web/register_web_exports_test.go  |   5 +-
 go/internal/web/exports/i18n.json                |   9 +-
 go/internal/web/exports/i18n_keys.txt            |   1 +
 go/internal/web/exports/routes.go                |   2 +
 go/internal/web/exports/routes_inventory_test.go |   3 +-
 go/internal/web/exports/workspace.go             | 465 +++++++++++++++++++++++
 go/internal/web/exports/workspace_test.go        |  70 ++++
 7 files changed, 549 insertions(+), 6 deletions(-)
```

```
8f6f3b2d8 1607 step 6
```

```
8f6f3b2d8

 docs/tasks/1607-go-exports-workspace-export.md |  2 +-
 docs/tasks/1607-report.md                      | 75 ++++++++++++++++++++++++++
 2 files changed, 76 insertions(+), 1 deletion(-)
```

## 2. Commands (last 5 lines each)

**Step 0** — `1606 step` commits present; pre-replace `routes.go` / `housebook.go` hashes OK; no `workspace.go`; 7 sidecars.

**Step 1** — 7/7 `sha256sum -c` lines `: OK`.

**Step 2** (`gofmt` / `go build` / `go vet`) — no output after module cache warm-up.

**Step 3** — host had no `postgres` user or PG16 binaries; `sudo apt-get install postgresql-16`; `server started` on port 55707 (`/var/tmp/pg1607`).

**Step 4 Go:**
```
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/exports	3.146s
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.100s
```
Named: 5× `--- PASS`, 2× `ok`, no SKIP/FAIL.

**Step 4 Python:**
```
...                                                                      [100%]
3 passed in 3.59s
```

**Step 5** — `server stopped`; `/var/tmp/pg1607` removed.

**context_lint** — `context lint: OK`

## 3. Acceptance (§7)

- [x] Step 1: 7/7 `: OK`
- [x] Step 2: silent (no gofmt drift)
- [x] Step 4: 2+2 `ok`, 5 named `--- PASS`, 0 SKIP; Python `3 passed`
- [x] `1607 step` commits touch only §3 paths
- [x] No `UBYHOST_GO_PATHS`, Caddy, compose, or `App/app/` changes; pushed only `wt-1607` (not `main`/`go-wave3`)
- [x] UI N/A (zip download)

## 4. Deviations

- PostgreSQL 16 not preinstalled; installed via `sudo apt-get install postgresql-16` and used `sudo` for `/var/tmp/pg1607` (per isolation: skip no test).
- Known Python/Go gaps E1–E10 unchanged (brief §2).

## 5. Questions

None.

## 6. Owner steps

When the 1605–1609 thread merges: add `/settings/workspace-export` to `UBYHOST_GO_PATHS` (full list in brief 1609). Zip temp files use the Go container `/tmp`.