# 1362 report

Start commit: d84138ea3b1e3901ebd0b6ca3d15b769c547b396

## 1. Files changed (`git diff --stat d84138e`)

- `go/internal/web/customers/query.go` (new, 422 lines, sha256 7b95391a...879e69 ok)
- `go/internal/web/customers/query_test.go` (new, 322 lines, sha256 38c9fc86...25a2 ok)
- `docs/tasks/1362-go-customer-admin-queries.md` (Status line only: todo to review)
- `docs/tasks/1362-report.md` (this file)

Commits: `8e48c37 1362 step 2`, `a9f0e7e 1362 step 3`, then step 4.

## 2. Commands

- Step 1: skipped, Postgres already accepting connections on 127.0.0.1:55436.
- `gofmt -l ./internal/web ./cmd` empty; `go vet ./...` no output.
- `go test ./internal/web/customers/ ./cmd/ubyhost-web/ -count=1`:
  ```
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/customers	0.711s
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.008s
  ```
- `go test ./internal/web/customers/ -count=1 -v | grep -c SKIP`: `0`
- Verbose results: `--- PASS: TestFiltersCursorKCMatchPython`, `--- PASS: TestQueriesMatchPython`.
- `python3 scripts/context_lint.py`: see section 6 (re-run after this report).

## 3. Section 7 acceptance

- [x] 2 files exist with the sha256 values in section 4.
- [x] `TestFiltersCursorKCMatchPython` and `TestQueriesMatchPython` pass; SKIP count 0.
- [ ] Context lint OK (re-run after this report, see section 6).
- [x] `git diff --stat d84138e` lists only the section 3 paths.

## 4. Deviations

- Blocks were extracted from the brief with `sed` (lines between the `~~~~` fences), not typed; sha256 matched on the first try.
- A test file was briefly moved to `/tmp` during the step 2 build check and moved back at once (sha256 re-checked). No repo effect.

## 5. Questions

None.

## 6. Owner steps left

None. Next: brief 1363 on the same branch.
