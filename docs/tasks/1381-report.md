# 1381 report

Status: review

## 1. Files changed

`git diff --stat HEAD~1` (after step 5) is in the handback. All changes are §3 paths: 15 modified, 12 created (27 total, matching MANIFEST.sha256). No file outside §3 changed.

## 2. Commands (last lines of output)

- Step 1 `sha256sum -c MANIFEST.sha256` in the bundle: all 27 lines `OK`.
- Step 2 copy in and `git status`: only §3 paths; `sha256sum -c` against the manifest: 27 `OK`. Commit `1381 step 2`.
- Step 3 `go_host_i18n.py --check`: rc=0, no output. `go_layout_golden.py --check`: rc=0, no output.
- §6.1 `gofmt -l`, `go vet`, `go test -count=1 -race`:
  ```
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb	1.019s
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout	2.971s
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar	1.156s
  ```
- Step 4 `go build ./cmd/ubyhost-web`: rc=0, no output. Binary removed.
- §6.2 DB test (Postgres at 127.0.0.1:54381, reachable):
  ```
  --- PASS: TestShellQuery (0.15s)
  PASS
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout	0.153s
  ```
- §6.3 pytest (`tests/test_go_layout_golden.py tests/test_go_host_i18n.py`):
  ```
  ...                                                                      [100%]
  3 passed in 2.08s
  ```
- §6.4 `python3 scripts/context_lint.py`: three WARN lines (pre-existing test-name overlap and "commits touched App/ after status.md update"), then
  ```
  next free: task 1382 | migration 0046
  context lint: OK
  ```

## 3. §7 acceptance

- [x] sha256sum all 27 OK; `git diff --stat fe42cc4` lists only §3 files.
- [x] Both generators `--check` exit 0.
- [x] §6 commands 1, 3, 4 as expected; `go build ./cmd/ubyhost-web` clean.

## 4. Deviations

- Brief §4 step 3 pipes through `tail`, so `rc=$?` reports tail's status. Re-ran both checks with the python exit code captured directly: rc=0 for both.
- Brief §9 and executor.md say "set Status: review". The status was written in this report header only. `docs/tasks/1381-go-layout-shell-data.md` is not in §3, so it was not edited.
- No PR opened: the executor brief says do not push, and the commit is local on `task/1381-go-layout-alerts`. The orchestrator pushes and opens the PR.
- Brief §4 step 2 `cp -r App` copied only the bundle's two App/scripts files; no other App file changed.

## 5. Questions

None.

## 6. Owner steps left

Push and open the draft PR (stacked on #985), then review and merge with `scripts/merge-pr-on-green.sh` after #985 is merged and CI is green.
