# 1615 report

Status: review

## Files changed

```
git log --oneline --grep='^1615 step' | tail -5
```

(step 1, step 2, step 8 commits — stats only §3 paths)

## Commands (last 5 lines)

Step 0: all checks OK; 10 sidecars.

Step 1: 10× `: OK`.

Step 2: `store.go` sha256 `30a68e7d...1efc0`.

Step 3: (no output).

Step 5:
```
ok  	.../go/internal/web/privacy	0.895s
ok  	.../go/cmd/ubyhost-web	0.078s
```
6× `--- PASS`; **SKIP count: 0**.

Step 6: `3 passed in 2.31s`; i18n check exit 0.

Step 7: `server stopped`.

`context_lint.py`: OK.

## §7 Acceptance

- [x] Step 1: 10 OK; step 2 hash OK
- [x] Step 3 silent
- [x] Step 5: 2 ok, 6 PASS, SKIP 0
- [x] Step 6: 3 passed, i18n exit 0
- [x] Commits 1/2/8; §3 paths only
- [x] No path switch / no push (coordinator pushes `wt-1615`)
- [x] UI: no screenshot (D5)

## Deviations

Created `App/.venv` for step 6 (brief allows). PG16 from apt; throwaway DB port 55616.

## Known differences

D1–D5 per brief §2.

## Questions

None.

## Owner steps left

Brief §2 Owner steps 1–6 (UBYHOST_GO_PATHS pair, UX gate, verify, rollback, coordinator lines).