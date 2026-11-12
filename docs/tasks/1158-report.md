# 1158 report

Status: review

## Files changed

Steps 0 to 5 on `claude/go-meta-capi-job`, nothing pushed:

- `go/internal/metacapi/send.go` (step 1, unchanged since)
- `go/internal/metacapi/send_test.go` (step 2, new, 381 lines, copied from the brief's code block)
- `go/cmd/ubyhost-web/main.go` (step 3: import, `"meta_capi": 10` interval, handler before `submit`)
- `docs/ENVIRONMENT.md` (step 4: `UBYHOST_GO_JOB_KINDS` row only)
- `docs/tasks/1158-go-meta-capi-job.md` and `docs/tasks/1158-cont-1.md` (step 5: `Status: review`)

Diff stat, §3 paths only (`git diff --stat` against the brief commit `5ad0091`):

    docs/ENVIRONMENT.md               |   2 +-
    go/cmd/ubyhost-web/main.go        |  10 +-
    go/internal/metacapi/send_test.go | 381 +++

## §6 results (last lines)

- `gofmt -l .`, `go vet ./...`, `go test ./internal/metacapi/ ./cmd/ubyhost-web/ -count=1`: `ok` for both packages.
- The six named tests: all `--- PASS`, then `ok`.
- `python3 scripts/context_lint.py`: only `ERROR docs/context/status.md: ~707 tokens > cap 700` (expected, pre-existing). `next free: task 1159 | migration 0046`.

## §7 ticked

- [x] Both packages `ok`.
- [x] `go.mod`, `go.sum`, `App/` unchanged.
- [x] `grep -c '"meta_capi"' main.go` = 2.
- [x] The `slog` grep for secrets/identifiers: no output.
- [x] The `RawQuery` / `?access_token` grep: no output.
- [x] context_lint: only the expected status.md error.
- [x] Diff against the brief commit lists only §3 paths.
- [x] Commits `1158 step 1` to `1158 step 5`; nothing pushed.

## Deviations

None. Done: steps 0 to 5. Note: the step 5 commit also contains the report and the two `Status:` lines.

## Questions

None.

## Follow-up

- A test-map row for the Go module is owed by another brief (test-map not touched here).
- The status.md token cap error on main belongs to another change.

## Owner steps left

After review, merge and deploy, the owner decides whether `meta_capi` is added to `UBYHOST_GO_JOB_KINDS`. Do not add it to any default. The Python job keeps running until then.
