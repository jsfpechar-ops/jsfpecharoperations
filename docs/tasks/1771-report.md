# 1771 report: Go `door_codes` job

Status: review

## Commits

- `1771 step 1` — copy verified (`sha256sum -c` 73/73 OK); add `App/scripts/go_door_codes_golden.py`, `App/tests/test_go_go_door_codes_job_golden.py` (rest of §3 already on `main` from #1139).
- Step 2: `go_door_codes_golden.py --check` OK; no commit.

## Files (§3, this PR vs `main`)

| Path | Note |
|---|---|
| `App/scripts/go_door_codes_golden.py` | mailnotify golden wrapper |
| `App/tests/test_go_go_door_codes_job_golden.py` | freshness test |
| `docs/tasks/1771-report.md` | this file |

Full `doorcodes` package, wiring, and job registration already on `main`.

## Commands (tail)

```
find docs/tasks/1771-files … | wc -l → 73
sha256sum -c docs/tasks/1771-files/MANIFEST.sha256 → 73 OK
go_door_codes_golden.py --check → door_codes goldens OK 4 files
gofmt -l . → (empty)
go vet ./internal/doorcodes/... ./cmd/... → silent
go test ./internal/doorcodes/... ./cmd/ubyhost-web/... -count=1 → all ok, 0 skipped
pytest tests/test_go_go_door_codes_job_golden.py -q → 1 passed
context_lint.py → OK
```

## §7 acceptance

- [x] State machines exercised in `go/internal/doorcodes/*_test.go` (issue, revoke, cancel, reconcile, cleaning, wire).
- [x] Job registered: `registerJob("door_codes", 5, doorCodesHandler)` (anchor on `main`).
- [x] Golden mailnotify JSON current; pytest freshness green.
- [x] `git log --grep='^1771 step'` → step 1 only (step 2 N/A).
- [ ] Host screenshots: N/A (no host pages in this brief).

## Deviations

1. **#1139 on `main`:** sidecar copy matched live tree; PR adds only golden script + pytest (missing from `main`).
2. Removed stray untracked smart-locks paths (not in §3 or manifest) so `gofmt -l .` is empty.

## Questions

None.

## Owner steps

TTLock plan §12 live lock acceptance; add `door_codes` to `UBYHOST_GO_JOB_KINDS` when rolling out.