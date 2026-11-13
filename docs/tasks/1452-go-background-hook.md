# 1452: `registerBackground`: a start hook for long-running Go background tasks

Status: todo
Depends on: none | Base: the orchestrator's branch (claude/happy-babbage-2zeeam); anchors checked in step 0 | Branch: the current one
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

**One big PR mode.** Work on the branch that is checked out. Commit `1452 step k` after each step. Do not create a branch, do not push, do not open a PR.

## 1. Objective

Add `registerBackground(name, setup)` to `go/cmd/ubyhost-web`, so a thread's background task starts once after the schema check, can return a set-up error, is never started by tests that build the mux, and is joined on shutdown before `pool.Close()`. The Go scheduler (brief 1450) is its first user. Until now a background task could only ride on `registerRoutes`, which has no context and no join.

## 2. Context

Rules (AGENTS.md): 4 no new dependency (standard library and pgx only); `main.go` is read-only for every lane (plan section 6), **except this one exact change, authorised by the orchestrator for the J7 thread on 2026-11-13**: one call plus one comment line in `run()`.

**What changes.**
- `registry.go`: `backgroundTask`, `backgroundTasks`, `registerBackground(name, setup)` (call from `init()`, a name registered twice panics), and `startBackground(ctx, pool, wg)`. It runs each setup in init order. A setup error is logged as `background task not started task=<name> error=...` and the service goes on: `ubyhost-go` serves live pages, so a bad task must not take them down. A nil run function means "switched off". Each run function gets its own goroutine on `wg` and is logged as `background task started task=<name>`.
- `main.go` `run()`: right after the `jobs.Run` goroutine, `startBackground(jobCtx, pool, &jobsDone)`. `jobCtx` is cancelled on SIGINT/SIGTERM. The existing `defer func() { cancelJobs(); jobsDone.Wait() }()` was registered after `defer pool.Close()`, and defers run last-in first-out, so background tasks are cancelled and waited for before the pool closes. `newMux` never calls `startBackground`, so the tests that build the mux start nothing.
- Who else needs it: `grep -l 'registerBackground\|main\.go' docs/tasks/14*.md docs/tasks/15*.md` at the brief writer's time found only 1450 (this thread) and 1500, which lists `main.go` as read-only and needs no hook. Nobody else needs a different hook.

**The exact change** is `docs/tasks/1452-files/1452.patch`. It is reproduced here for the reviewer; apply the file, never retype it:

````diff
diff --git a/go/cmd/ubyhost-web/main.go b/go/cmd/ubyhost-web/main.go
--- a/go/cmd/ubyhost-web/main.go
+++ b/go/cmd/ubyhost-web/main.go
@@ -173,6 +173,8 @@ func run() int {
 			jobs.Run(jobCtx, pool, goKinds, goHandlers(pool), goIntervals)
 		}()
 	}
+	// Brief 1452: tasks from registerBackground; joined with the jobs above.
+	startBackground(jobCtx, pool, &jobsDone)
 
 	m := &metrics{counts: map[key]int64{}}
 	mux := newMux(m, pool)
````

plus 54 added lines in `registry.go`: the imports `context`, `log/slog` and `sync`, then at the end the type, the slice and the two functions. Read them in the patch file.

Anchors (step 0, `grep -cF` prints 1): `go/cmd/ubyhost-web/main.go` `jobs.Run(jobCtx, pool, goKinds, goHandlers(pool), goIntervals)` and `defer func() { cancelJobs(); jobsDone.Wait() }()`; `go/cmd/ubyhost-web/registry.go` `func registerRoutes(fn func(*http.ServeMux, *metrics, *pgxpool.Pool)) {`; and `grep -c 'registerBackground' go/cmd/ubyhost-web/*.go` prints 0 for every file.

**Verified by the brief writer** on a throwaway worktree of the branch head (fd4075b47): patch applied with `git apply`, then 1450 and 1451 on top; `gofmt -l` empty, `go build ./...`, `go vet ./cmd/...` clean, `go test -race ./cmd/ubyhost-web/` ok.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/registry.go` | edit (patch) | `registerBackground`, `startBackground` |
| `go/cmd/ubyhost-web/main.go` | edit (patch) | one comment line and the `startBackground` call in `run()` |
| `go/cmd/ubyhost-web/register_background_test.go` | create (copy) | newMux starts nothing; error, off and join; duplicate panics |
| `docs/tasks/1452-report.md` | create | the report |

`docs/tasks/1452-files/` is part of this brief; do not edit it. No other file may change.

## 4. Steps

0. Checks (from the repo root, one call): `git status --short -- go/cmd/ubyhost-web | tail -5` is empty; the anchors of section 2 as stated; then

```bash
cd docs/tasks/1452-files && sha256sum -c <<'EOF' 2>&1 | tail -3; cd ../../.. && git apply --check docs/tasks/1452-files/1452.patch 2>&1 | tail -5 && echo APPLY_OK
e7a2139583972cd19af14c356506c85111d37c0621d75cc4b5f84457977bbd4b  1452.patch
2eaa55512e09be8a56a209a31daac914225bcaba5cbc56967a2d9b2d15c112a4  go/cmd/ubyhost-web/register_background_test.go
EOF
```

   Expected: two `OK` lines and `APPLY_OK`. Anything else: STOP.

1. Apply the patch: `git apply docs/tasks/1452-files/1452.patch && git diff --stat -- go/cmd/ubyhost-web | tail -3`. Expected: `main.go | 2 ++`, `registry.go | 54 +++...`, `2 files changed, 56 insertions(+)`. Commit only those two files: `git add go/cmd/ubyhost-web/main.go go/cmd/ubyhost-web/registry.go && git commit -m "1452 step 1"`.

2. Copy the test: `cp docs/tasks/1452-files/go/cmd/ubyhost-web/register_background_test.go go/cmd/ubyhost-web/ && cd go && gofmt -l cmd/ubyhost-web 2>&1 | tail -3 && go build ./... 2>&1 | tail -5`. Expected: no output. Commit: `git add go/cmd/ubyhost-web/register_background_test.go && git commit -m "1452 step 2"`.

3. Run section 6, write the report (section 9), and commit it with `git add docs/tasks/1452-report.md docs/tasks/1452-go-background-hook.md && git commit -m "1452 report"`.

## 5. Do not touch

Everything in `go/cmd/ubyhost-web/` except the three files of section 3 (other threads own the `register_*.go` files); in `main.go` anything but the two lines of the patch; `go/internal/` (all of it); `go/go.mod`, `go/go.sum`; `App/`; `docs/context/*`; `docs/tasks/1452-files/`. Other writers commit on this branch at the same time: stage only your own files by name, never `git add -A` or `git commit -a`.

## 6. Commands

From `go/`:

- `go vet ./cmd/... 2>&1 | tail -30` prints nothing.
- `go test -count=1 -race -v -run 'Background|NewMux|RoutesRegisterOnce|DuplicateRoute|DuplicateJobKind' ./cmd/ubyhost-web/ 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -10` prints `--- PASS` for `TestNewMuxStartsNoBackgroundTask`, `TestStartBackgroundRunsJoinsAndSkips`, `TestDuplicateBackgroundTaskFails`, `TestRoutesRegisterOnce`, `TestDuplicateRouteFails`, `TestDuplicateJobKindFails`, then `ok`.
- `go test -count=1 ./cmd/ubyhost-web/ 2>&1 | tail -3` prints `ok`.

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` shows no error naming 1452. Test-map: no row covers Go; these are the tests.

## 7. Acceptance

- [ ] `git log --oneline --grep='^1452 '` lists `1452 step 1`, `1452 step 2` and `1452 report`, and `git show --stat --format=%s $(git log --format=%h --grep='^1452 step') | tail -8` names only `main.go`, `registry.go` and `register_background_test.go`.
- [ ] `git show $(git log --format=%h --grep='^1452 step 1') -- go/cmd/ubyhost-web | grep '^[+-][^+-]' | sha256sum` equals `grep '^[+-][^+-]' docs/tasks/1452-files/1452.patch | sha256sum`.
- [ ] `cmp docs/tasks/1452-files/go/cmd/ubyhost-web/register_background_test.go go/cmd/ubyhost-web/register_background_test.go` prints nothing.
- [ ] Section 6 output exactly as stated.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found, a sha256 differs, or `git apply --check` fails (another writer changed `main.go` or `registry.go`: do not merge by hand);
- a test fails twice (never change the patch or the test);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1452-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git show --stat` of the step commits).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left (none).

## Risk list (for the reviewer)

Read the full diff of:

- `go/cmd/ubyhost-web/main.go`: exactly two added lines, after the `jobs.Run` goroutine and before the mux; the join order relies on the existing defers (wait before `pool.Close()`).
- `go/cmd/ubyhost-web/registry.go`: setup errors are logged, not fatal; nil run means off; `wg.Add` before the goroutine.
- `go/cmd/ubyhost-web/register_background_test.go`: the tests swap `backgroundTasks` and restore it.

## Owner steps

None. The hook does nothing until a task registers (brief 1450), and that task is off unless `UBYHOST_SCHEDULER=go`.
