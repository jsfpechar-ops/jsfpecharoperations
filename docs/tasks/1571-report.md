# Report 1571: Go cleaning event save (create and update)

Status: review. Branch: worktree-agent-a9af2061665d4a123 (started from local `go-wave3`, commits `1571 step k`, no push, no PR).

## Files changed (`git show --stat`)

- `go/cmd/ubyhost-web/register_web_cleaning_host_events_test.go` (new, 22 lines)
- `go/internal/web/cleaning/host_events.go` (new, 339 lines)
- `go/internal/web/cleaning/host_events_test.go` (new, 326 lines)
- `docs/tasks/1571-go-cleaning-event-save.md` (Status line only: todo to review)
- `docs/tasks/1571-report.md` (new)

Sidecars under `docs/tasks/1571-files/` were not changed. sha256 of the three copies matches §2 of the brief.

## Commands (last 5 lines each)

- `gofmt -l` / `go build ./...` / `go vet ./internal/web/cleaning/... ./cmd/...`: no output.
- `go test ./internal/web/cleaning/... ./cmd/ubyhost-web/... -count=1` (PostgreSQL 16 on port 5638):
  `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/cleaning 7.299s`
  `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web 0.087s`
- Six named tests with `-v`: all `--- PASS` (TestHostCreateEvent, TestHostCreateEventJSON, TestHostCreateEventErrors, TestHostUpdateEvent, TestHostUpdateEventErrors, TestCleaningHostEventRoutesRegistered).
- Both packages with `-v`: PASS 44, SKIP 0, FAIL 0. TestCleaningMatchesPython present and green.
- `python3 scripts/context_lint.py | grep -v '^WARN'`: `context lint: OK`.

## Acceptance (§7)

- [x] sha256 of the three files matches.
- [x] Format, build and vet silent.
- [x] Both packages ok; six named tests PASS on PostgreSQL; 0 SKIP.
- [x] Step commits `1571 step 1` and `1571 step 5` on the branch; only §3 paths and the status line changed.
- [x] No `UBYHOST_GO_PATHS`, Caddy, compose, env or Python change; nothing pushed.
- [ ] UI: not applicable here (dormant pages, no path routed). UX gate runs on staging before the owner routes the paths.

## Deviations

- Step 0 reset target was `go-wave3` (per the task message); dependency check printed 1.
- PostgreSQL started on port 5638 with data in `/var/tmp/pg1571` (per the task message), not the brief's 55570 / pg55570. Stopped and removed after the tests.
- The sidecar copy was done with three explicit `cp` commands instead of the brief's loop, because a shell guard refused the compound git-containing command. Same files, same hashes.

## Questions

None.

## Owner steps left

- Nothing to switch on. Open the PR from this branch when the orchestrator collects the commits. Path routing waits for brief 1573.
