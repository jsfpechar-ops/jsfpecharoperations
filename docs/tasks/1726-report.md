# 1726 report

Executor: cloud agent on branch `cursor/1726-guest-leon-dff7`.

## Commits

- `1726 step 1`: copy seven sidecars from `docs/tasks/1726-files/`; remove `RegisterLeonQuestions` stub from `go/internal/web/guest/wave_routes.go` (real handlers in `leon_questions.go`).

## Commands

### `sha256sum -c docs/tasks/1726-files/MANIFEST.sha256`

All seven paths `: OK`.

### `cd go && gofmt -l` (Leon paths)

(empty)

### `cd go && go test ./internal/web/guest/... ./cmd/ubyhost-web/... -run 'Leon|leon' -count=1`

```
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/guest	0.020s
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.077s
```

### `cd App && pytest tests/test_go_leon_questions_golden.py`

```
1 passed in 0.26s
```

### `python3 scripts/context_lint.py`

`context lint: OK`

## Accepted differences

None noted in this run. PostgreSQL golden replay (`UBYHOST_TEST_DATABASE_URL`) not run in this environment.

## Screenshots (host pages)

Deferred: UX gate for host question pages when routes go live in `UBYHOST_GO_PATHS` (brief 1728).

## Left undone

- Full `go test ./internal/web/... ./cmd/ubyhost-web/...` (entire packages, not Leon-filtered).
- `test_layout_lint_browser.py` and 390/768/1280 screenshots per rule 10.
- Optional regen: `App/scripts/go_leon_questions_golden.py` with FastAPI replay.