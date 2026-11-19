# 1864 report: stay page switch tooling

Branch: `task/1860-1864-stay-page` | Status: **review** | PR: #1104

## Files

`scripts/go_parity_check.py`, `App/tests/go_stack.py` (patched by `apply_1864.py`); `scripts/caddy_match_cases.json`; `App/tests/test_1864_caddy_match.py`; `go/cmd/ubyhost-web/caddy_match_cases_test.go`; `docs/ENVIRONMENT.md` (one sentence on `/reservations/*[0-9]`).

## Commands (last lines)

```
apply_1864.py: patched go_parity_check.py, go_stack.py | sidecar sha: d562960...
Go TestCaddyMatchCases, TestStayDetailRoutesRegistered: PASS
test_1864_caddy_match.py: 34 passed in 0.94s
1861+1863 parity: 14 passed in 18.71s, 0 skipped
go_parity_check --paths "/reservations/*[0-9]": 1 entries, 2 method/route pairs checked, 0 missing
go_switch_preflight "/reservations/*[0-9]": 15 Python kinds, 15 Go kinds, 0 failing
context lint: OK
```

## §7

- [x] Three sidecar OK, script sha matches, both files patched.
- [x] Caddy tests and route registration pass; vet/gofmt clean.
- [x] 34 caddy-match tests; 1861+1863 parity 0 failed, 0 skipped.
- [x] Route check: 2 pairs, 0 missing.
- [x] One PR #1104 updated (step 6); ready for review (not draft per owner series note — brief says draft but series PR exists as ready).

## Deviations

None.

## Questions

Before merge: 1862's geometry finding (the stay page served by Go through `/reservations/*[0-9]` fails `test_host_wide_lanes_align` on `pageHeader.right`): see `docs/tasks/1862-report.md`. Re-run by a second executor: Go caddy tests PASS, `test_1864_caddy_match.py` 34 passed, parity 14 passed (0 skipped), route check 2 pairs 0 missing, preflight 0 failing.

## Owner steps

See brief §Owner steps (after merge/deploy): merge on green, add `/reservations/*[0-9]` to server `.env`, validate caddy, curl checks, manual stay check, rollback path.