# 1707 report: Go smart-locks POST routes (dormant)

Status: review

## Commits

`git log --oneline --grep='^1707 step'`: step 1–4 (copy sidecars, golden, gofmt, route registration verified).

## Files (§3)

Eight implementation paths from `docs/tasks/1707-files/` (MANIFEST checksums OK). Routes registered via `init()` in `register_web_properties_smart_locks.go`; **not** added to `UBYHOST_GO_PATHS` (wave P2).

## Commands (last lines)

```
sha256sum -c docs/tasks/1707-files/MANIFEST.sha256
(all OK)
```

```
cd go && gofmt -l .
(empty)
```

```
cd go && go vet ./internal/web/... ./cmd/...
(silent)
```

```
cd go && go test ./internal/web/properties/... ./cmd/ubyhost-web/... -count=1
ok  	.../go/internal/web/properties	0.065s
ok  	.../go/cmd/ubyhost-web	1.693s
```

```
cd go && go test ./internal/web/... ./cmd/ubyhost-web/... -count=1
FAIL	.../go/internal/web/settings (UBYHOST_TEST_DATABASE_URL is not set); CI has Postgres.
```

```
cd App && .venv/bin/python -m pytest tests/test_go_smart_locks_golden.py -q --tb=short -x
1 passed
```

```
python3 scripts/context_lint.py
context lint: OK
```

## §7 acceptance

- [x] Dormant registration; no `UBYHOST_GO_PATHS` edit.
- [x] Golden: signed-out POST redirect cases (`go_smart_locks_golden.py` / freshness test).
- [x] `TestSmartLocksPostRoutesRegistered`, `TestSmartLocksReturnTo`, `TestSmartLocksSection` pass locally.
- [ ] Full `./internal/web/...` package run: **CI only** (no local `UBYHOST_TEST_DATABASE_URL`).
- [ ] Signed-in / TTLock gateway parity cases: **accepted difference** until golden script expanded (per brief).

## Host UX (rule 10)

No template or CSS changes; smart-lock UI unchanged. Browser screenshots N/A.

## Owner

Section 12 TTLock acceptance on staging before wave P2 path rollout.

## Deviations

- `gofmt -w` on `smart_locks_test.go` (step 3); sidecar was one line short of formatted.
- `scripts/start-merge-guard.sh` not in repo; use `scripts/merge-pr-on-green.sh <pr>` after CI green.