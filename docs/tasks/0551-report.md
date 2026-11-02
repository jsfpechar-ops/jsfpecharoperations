# 0551 report: Go G5d-3a data keys, alerts and audit

## Files changed
- `go/internal/secure/datakeys.go` (new): `LoadDataKeys`, `MultiFernet.EncryptString`, legacy flag, secret loader (read only, never creates a file).
- `go/internal/secure/datakeys_test.go` (new): 8 tests, no database.
- `go/internal/ubyport/effects.go` (new): `AlertParams`, `RaiseAlert`, `ResolveAlert`, `Audit`, `ApartmentInDoubt`, `ClearStuckIfRecovered`.
- `go/internal/ubyport/effects_test.go` (new): 10 database tests (skip without `UBYHOST_TEST_DATABASE_URL`).
- `docs/tasks/0551-go-g5d3a-keys-alerts-audit.md`: status set to `review`.
- `docs/tasks/0551-report.md` (this file).

## Commands
- `cd go && test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/secure/ ./internal/ubyport/ -count=1`
  - gofmt and vet clean. The `go test` tail: `ok github.com/.../internal/secure 0.014s` and `ok github.com/.../internal/ubyport 0.333s`. The 10 database tests skip locally; CI's `go` job is their gate.
- `-run DataKeys -v`: all 8 `TestDataKeys*` pass.
- `python3 scripts/context_lint.py | tail -3`: `context lint: OK`.

## Brief section 7
- `git diff --stat origin/main` lists only section 3 files and the brief (plus this report).
- gofmt, vet and non-database tests pass locally.
- Database tests: not run locally. Pending CI with 0 skipped.

## Deviations and decisions beyond section 2
- `EncryptString` did not exist on `MultiFernet`, so it was added in `datakeys.go` (not `fernet.go`) to keep the existing file untouched.
- `pyJSONParams` does not reuse `writePyString` from `store.go`: that helper escapes non-ASCII (ensure_ascii=True), while the alert params need `ensure_ascii=False`. A local writer keeps non-ASCII as is.
- Secret length uses rune count (Python `len` counts characters), not byte length.
- `RaiseAlert` follows the Python flow: SELECT open alert by key, then UPDATE; else INSERT, and on SQLSTATE 23505 an UPDATE of the open row.
- Empty `params` map and nil both store NULL.
- The test for params bytes also covers the refresh path.
- Python's `secret_key()` default dir `data` is used as the brief states; it is resolved relative to the working directory, as the brief gives it.

## Questions
- None blocking. Please confirm the default secret dir (`data`, relative to cwd) matches what Python resolves at runtime, since the brief gives only the name.

## Owner steps left
- None. Nothing is pushed. The branch needs CI's `go` job to pass before the PR is merged.
