# 1608 report

## 1. Files changed

`git log --oneline --grep='^1608 step' | tail -10`:

```
a8b6ed1a8 1608 step 1
```

`git show --stat --format=%h a8b6ed1a8`:

- `go/cmd/ubyhost-web/register_web_exports_test.go`, `go/internal/hostweb/layout/funcs.go`, `layout.go`
- `go/internal/web/exports/archived.go`, `archived_test.go`, `templates/archived.tmpl`
- `routes.go`, `i18n_keys.txt`, `i18n.json`, `routes_inventory_test.go`
- `docs/tasks/1608-report.md` (step 6)

## 2. Commands (last 5 lines)

**Step 0:** 1607 commits present; layout/funcs/routes hashes OK; no `archived.go`; 10 sidecars.

**Step 1:** all 10 `sha256sum -c` lines `: OK`.

**Step 2:** no output (gofmt/build/vet clean).

**Step 3:** `waiting for server to start.... done` / `server started` (after `sudo apt-get install postgresql-16`; throwaway instance on port 55708).

**Step 4 Go (packages):** four `ok` lines (`exports`, `cmd/ubyhost-web`, `hostweb`, `hostweb/layout`).

**Step 4 Go (named):** six `--- PASS` (inventory, registered, archived golden, alerts once, layout golden, alert presentation); three `ok`; 0 SKIP/FAIL.

**Step 4 Python:** `3 passed in 3.94s`; no skipped.

**Step 5:** `server stopped`.

**context_lint:** `context lint: OK`.

## 3. Acceptance (§7)

- [x] Step 1: 10/10 hashes OK.
- [x] Step 2: silent.
- [x] Step 4: 4 package `ok`, 6 named PASS, Python 3 passed.
- [x] Commits `1608 step 1` (+ step 6); §3 paths only.
- [x] No `UBYHOST_GO_PATHS`/Caddy/Python app changes; not pushed to `main`.
- [x] UI: rule 7 / UX gate not run on dormant Go route (golden pins `<main>`); owner enables path then UX gate on staging.

## 4. Deviations

Executor VM had no PostgreSQL 16 user/binaries until `sudo apt-get install postgresql-16`; tests then used brief’s throwaway `/var/tmp/pg1608` on port 55708.

## 5. Questions

None.

## 6. Owner steps

When merged/deployed: add `/settings/archived` to `UBYHOST_GO_PATHS`; run UX gate on staging (390/768/1280). Known Python/Go diffs E1–E10 remain as in brief §2.