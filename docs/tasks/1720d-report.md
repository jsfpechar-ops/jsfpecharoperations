# 1720d report

Status: **blocked**

## Done

- Branch `cursor/1720d-guest-privacy-ruian-dff7` created from `origin/cursor/1720a-guest-shell-dff7` with `origin/cursor/1720b-guest-pin-dff7` merged (PIN + shell foundation only).
- Verified Python source for `privacy_notice`, `ruian_suggest` (`guest.py` ~1360–1453).

## Blocker

Executor cannot start Tier A work:

1. **`docs/tasks/1720d-files/`** — not on any branch or in the repo (no `MANIFEST.sha256`, no `.txt` sidecars). `grep` / GitHub code search for `1720d-files` is empty.
2. **`docs/tasks/1720d-go-guest-privacy-ruian.md`** — missing (only split table in project store `internal/go-porting/1720-split-briefs.md`).
3. **Full shell golden** per split brief needs **`1720c`** (`GET /l/{token}` pick_stay); no `cursor/1720c-*` branch exists on `origin`.

Per `docs/context/executor.md` §8: STOP without anchors/sidecars.

## Commands (baseline after merge)

```
cd go && go test ./internal/web/guest/... ./cmd/ubyhost-web/... -run TestGuestShellRoutesRegistered -count=1 2>&1 | tail -5
# ok
cd App && .venv/bin/python -m pytest tests/test_go_go_guest_shell_pin_golden.py -q --tb=short -x 2>&1 | tail -5
# 1 passed
```

## Left (after exact-diff pass)

1. Opus/Sonnet exact-diff: `1720d-go-guest-privacy-ruian.md` + `1720d-files/` (privacy, ruian, golden script/test, shell route wiring, i18n/templates).
2. If golden covers pick_stay: **1720c** sidecars first or include pick in 1720d scope explicitly.
3. Executor copies sidecars, implements, runs `go_go_guest_shell_gate_golden.py` + `test_go_go_guest_shell_gate_golden.py`.
4. Merge order: land **1720a** (#1172) and **1720b** before 1720d PR.

## Deviations

None (no implementation attempted without sidecars).

## Questions

1. Should 1720d exact-diff include **pick_stay** (1720c) inside the full gate golden, or ship privacy/ruian golden only until 1720c lands?
2. Confirm brief writer runs exact-diff on current 1720b head before re-queueing this executor.

## Owner steps

None.