# 1598 report

## 1. Step commits

`git log --oneline --grep='^1598 step'` after step 6: one commit (`1598 step 6`).

## 2. Commands (last 5 lines) and SKIP count

**Step 0**

```
wt-1598
go/internal/web/onboarding/demo_reset.go
go/internal/web/onboarding/onboarding_page.go
go/internal/web/onboarding/routes.go
go/internal/web/onboarding/setup.go
1
2
App/tests/test_go_demo_reset_golden.py
App/tests/test_go_onboarding_page_golden.py
App/tests/test_go_onboarding_setup.py
```

**Step 1** (gofmt empty; build/vet exit 0; first run pulled modules):

```
go: downloading github.com/jackc/pgpassfile v1.0.0
go: downloading github.com/pkg/errors v0.8.1
go: downloading golang.org/x/sync v0.22.0
```

**Step 2:** No PostgreSQL 16 at `/usr/lib/postgresql/16/bin/initdb`; no `postgres` user. **CI only** — stopped before step 3 per brief.

**Step 3:** Not run on this VM (no test DB). Ad-hoc attempt failed (`admin connect failed`). **SKIP count:** not measured (required `0` on CI with PG).

**Step 4:**

```
....                                                                     [100%]
4 passed in 4.24s
```

(Brief text says `5 passed`; this branch has four test functions in the three files.)

**Step 5:**

```
next free: task 1632 | goose migration 00018 (App/app/migrations/ is frozen)
context lint: OK
```

## 3. §7 acceptance

- [x] Step 0: branch and files present; `POST /onboarding/dismiss` count 1.
- [ ] Step 0: `POST /demo/reset` grep count is **2** (comment + `Handle`), not **1**.
- [x] Step 1: gofmt clean; build and vet OK (module download on cold cache only).
- [ ] Step 3: not run — **CI only**.
- [ ] Step 4: **4 passed**, not 5 (brief count outdated).
- [x] Step 5: context lint OK.
- [ ] Remaining §7 items: need step 3 on CI with PG.

## 4. Deviations

- Step 0 `grep -cF "POST /demo/reset"` → 2 (string also in file comment).
- No local PostgreSQL 16; step 3 skipped per §4 step 2.
- Step 4: 4/4 passed vs brief’s “5 passed”.

## 5. Owner steps left

Unchanged from brief § Owner steps: add the four POST paths to `UBYHOST_GO_PATHS`, validate Caddy, compose up, smoke dismiss/resume and audit rows; rollback by removing paths.

**CI follow-up:** Re-run steps 3–4 on a host with PostgreSQL 16 (port 55598 or `UBYHOST_TEST_DATABASE_URL`); confirm step 3 SKIP count `0` and go tests all `ok`.