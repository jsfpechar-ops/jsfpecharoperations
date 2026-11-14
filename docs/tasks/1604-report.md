# 1604 report

## 1. Step commits

```
87fcd866d 1604 step 6
```

## 2. Commands (last 5 lines; SKIP = 0)

**Step 0:** branch `wt-1604`; four wizard Go files + register + four parity tests present; `TestWizardSkipWithDemoStayIs501` count 1.

**Step 1** (`gofmt` / `go build` / `go vet`): exit 0; no format or vet issues reported.

**Step 2** (PostgreSQL 55599):
```
waiting for server to start.... done
server started
```

**Step 3** (Go tests):
```
ok  	.../go/internal/web/onboarding	4.744s
ok  	.../go/cmd/ubyhost-web	0.114s
```
SKIP count: **0**

**Step 4** (pytest parity):
```
....                                                                     [100%]
4 passed in 3.54s
```

**Step 5** (context lint):
```
next free: task 1632 | goose migration 00018 (App/app/migrations/ is frozen)
context lint: OK
```

## 3. Acceptance (§7)

- [x] Step 0 checks all passed.
- [x] Step 1: no output at all (module download only on first build).
- [x] Step 3: `ok` for every package, SKIP count `0`.
- [x] Step 4: `4 passed`, 0 skipped.
- [x] Step 5: `context lint: OK`.
- [x] Commits touch only `docs/tasks/1604-go-setup-wizard-switch.md` and `docs/tasks/1604-report.md`.
- [x] No `UBYHOST_GO_PATHS`, Caddy, compose, env or `App/app/` changes; not pushed to `main`.
- [x] UI: UX gate pending (Owner steps).

## 4. Deviations

- Coordinator assignment: `git fetch`, `reset --hard origin/go-wave3`, work branch `wt-1604` (brief §one-PR mode skipped); push `wt-1604` at end, no PR.
- Installed `postgresql-16` via apt; created throwaway cluster at `/var/tmp/pg55599` (port 55599).

## 5. Owner steps left

Unchanged from brief §Owner steps: accept 501 on try-it skip with demo stay; UX gate on staging; add `/apartments/*/setup` and `/apartments/*/setup/*` to `UBYHOST_GO_PATHS`; validate Caddy and compose; production smoke; rollback by removing paths.

Brief 1603 remains blocked for demo-stay delete; hosts with demo stays must skip to finish manually until 1603 merges.