# 1599 report: Go setup wizard core

Status: review

## 1. Files changed

`git show --stat` for `1599 step 1`: 17 files, +5543 lines (§3 paths only; no other files touched).

## 2. Commands (last 5 lines each)

**Step 1 sha256sum -c:** all 17 `: OK`.

**Step 2 gofmt/build/vet:** (no output).

**Step 3 pg_ctl start:** `waiting for server to start.... done` / `server started`.

**Step 4 go test packages:**
```
ok  	.../go/internal/web/onboarding	2.637s
ok  	.../go/cmd/ubyhost-web	0.098s
```

**Step 4 named tests:** 8× `--- PASS` (see brief §4); 2× `ok`; no SKIP/FAIL.

**Step 5 pytest:** `3 passed in 2.65s`

**context_lint:** `context lint: OK`

## 3. Acceptance (§7)

- [x] sha256sum step 1: 17 OK
- [x] format/build/vet silent
- [x] step 4: both packages ok; 8 named tests PASS; 0 SKIP
- [x] step 5: 3 passed
- [x] commits: `1599 step 1`, `1599 step 6`; stat shows §3 paths only
- [x] no UBYHOST_GO_PATHS / Caddy / compose / App/app changes; not pushed to main
- [x] UX gate pending (dormant routes; brief §7)

## 4. Deviations

Installed `postgresql-16` (apt; binaries were absent) and used `sudo` for `/var/tmp/pg55599` init/start. Branch `wt-1599` per coordinator isolation (brief template said task/1599).

## 5. Questions

None.

## 6. Owner steps left

None (path switch in brief 1602).