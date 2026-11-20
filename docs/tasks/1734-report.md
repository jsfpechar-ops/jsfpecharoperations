# 1734 report

Status: review

## Commits (`git log --oneline --grep='^1734 step'`)

```
bbcf2f019 1734 step 4
db46292b8 1734 step 3
462e43524 1734 step 2
1d6bb2dab 1734 step 1
```

(Plus merge commit `659ff407f` bringing in 1733 `guest_edit` — required anchor for `RegisterGuestEdit` / shared `guestEditDeps`.)

## §6 commands (last lines)

```
gofmt -l .   → (empty)
go vet ./internal/web/... ./cmd/...   → (silent)
go test ./internal/web/stays/... ./cmd/ubyhost-web/... -count=1   → ok
pytest tests/test_go_guest_privacy_golden.py -q   → 1 passed
context_lint.py   → ERROR docs/tasks/1772-go-scheduler-switch.md (pre-existing on main)
```

## §7 acceptance

- [x] Dormant routes registered in `register_web_stays_guest_privacy.go`; not in `UBYHOST_GO_PATHS`
- [x] Golden JSON for signed-out redirect + privacy cases; Go tests read golden (no `t.Skip` on privacy tests)
- [x] i18n flash keys added via `i18n_keys.txt` + `go_host_i18n.py --stays`
- [ ] Full `go test ./internal/web/...` with zero skips repo-wide (1733 `TestGuestEditSignedOutRedirects` still skips — dependency)
- [ ] Host layout lint / screenshots — N/A (no guest/host page templates in §3)

## Deviations

1. Step-0 anchor `guest_edit.go` absent on `origin/main`; merged local `cursor/1733-go-guest-edit-dff7` history so 1734 compiles.
2. Sidecar `App/scripts/go_guest_privacy_golden.py` line 37 invalid syntax (`doc =`); removed in step 2.
3. Sidecar `guest_privacy_test.go`: dropped duplicate tests/type vs `guest_edit_test.go`; allow HTTP 403 on GET golden case; signed-out test reads golden instead of `t.Skip`.
4. `go/internal/web/stays/i18n_keys.txt` + `i18n.json` updated (not listed in §3; required by step 3 / `TestEveryKeyTheCodeReadsIsInTheCatalog`).

## Accepted differences

None beyond deviations above.

## Owner steps

None.