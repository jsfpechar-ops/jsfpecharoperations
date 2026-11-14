# 1586 report

## 1. Files changed

```
 go/cmd/ubyhost-web/register_web_stayfees_confirm.go   |  22 ++
 go/cmd/ubyhost-web/register_web_stayfees_confirm_test.go |  15 +
 go/internal/web/stayfees/confirm.go                  | 155 ++++++++
 go/internal/web/stayfees/confirm_i18n.json           |  10 +
 go/internal/web/stayfees/confirm_test.go             | 391 +++++++++++++++++++++
 5 files changed, 593 insertions(+)
```

## 2. Commands (last 5 lines) — SKIP count: **0**

**Step 1 sha256sum:** all five lines `: OK`.

**Step 2 (`gofmt` / `build` / `vet`):** (no output after tooling warm-up)

**Step 3 PostgreSQL:** `waiting for server to start.... done` / `server started`

**Step 4 full packages:**
```
ok  	.../go/internal/web/stayfees	7.857s
ok  	.../go/cmd/ubyhost-web	0.122s
```

**Step 4 named tests:** seven `--- PASS` lines; two `ok` lines; no `--- SKIP` or `--- FAIL`.

**context_lint:** `context lint: OK`

## 3. Acceptance (§7)

- [x] `sha256sum -c` of step 1 printed `: OK` for all 5 files.
- [x] Format, build and vet printed nothing (after module download).
- [x] Both packages `ok`; seven named tests `--- PASS`; SKIP 0.
- [x] Step commits: `1586 step 1`, `1586 step 5`; stat only §3 paths.
- [x] No `UBYHOST_GO_PATHS`, Caddy, compose, env, or Python app changes; not pushed to `main`.
- [x] UI N/A (redirect-only route).

## 4. Deviations

- Branch `wt-1586` per coordinator isolation (not brief’s one-big-PR branch note).
- PostgreSQL 16 was not preinstalled; installed `postgresql-16` and started throwaway cluster on port 55585 before step 4 (not “CI only”).

## 5. Questions

None.

## 6. Owner steps left

Route `POST /stay-fees/confirm-ready` in `UBYHOST_GO_PATHS` after brief 1580 sets `stayFeeRenderer`; no deploy switch in this brief.