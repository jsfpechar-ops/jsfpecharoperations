# 2032 report

Status: review

## Files changed

`00023`; schema golden; `steps.go`, `retention.py`, `retention_golden.py`, `fixture.sql`, `golden.json`; `steps_entry_codes_test.go`; `apartmententrycode/`; `entry_code_guard_test.go`; `test_retention_entry_code.py`; `RETENTION.md`.

## Commands (last 5 lines)

`pytest tests/test_retention_entry_code.py tests/test_retention*.py tests/test_privacy_first.py`: `53 passed in 10.33s`  
`go test ./internal/retention/ ./internal/schema/ ./internal/web/exports/ ./internal/apartmententrycode/`: all `ok`  
`retention_golden.py`: `wrote go/internal/retention/testdata/golden.json`  
`pg_schema_golden.py`: (no output; no diff)  
`context_lint.py`: FAIL `test-map.md` token cap (pre-existing)

## §7

- [x] 00023 + copy
- [x] Schema current
- [x] Retention golden
- [x] Guard + RETENTION line

## Deviations

Shared worktree branch switches; 1668 commits under 2032 tip; removed duplicate fixture INSERT; no push/PR.

## Owner steps

`scripts/merge-pr-on-green.sh`.