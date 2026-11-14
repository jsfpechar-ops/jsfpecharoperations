# 1573 report: Go cleaning door-code actions

Status: review (one big PR mode: committed on the worktree branch, not pushed, no PR)

## 1. Files changed
- create go/cmd/ubyhost-web/register_web_cleaning_host_codes_test.go (39 lines)
- create go/internal/web/cleaning/host_codes.go (408 lines)
- create go/internal/web/cleaning/host_codes_test.go (334 lines)
- sidecars docs/tasks/1573-files/** copied to the repo paths above (hashes verified)
- docs/tasks/1573-report.md (this file), brief status set to review

Commits: 1573 step 1 (fea1c9d). Steps 2 to 4 changed no file.

## 2. Commands
- sha256sum (step 1): all three files match the brief hashes.
- gofmt -l / go build ./... / go vet ./internal/web/cleaning/... ./cmd/...: no output.
- UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55731/postgres go test ./internal/web/cleaning/... ./cmd/ubyhost-web/... -count=1
  last lines:
  ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/cleaning 18.735s
  ok  github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web 0.103s
- Named tests (-v -run ...): 8 tests in cleaning PASS, TestCleaningAllRoutesRegistered PASS, both packages ok.

## 3. Acceptance
- [x] sha256 OK for all 3 files
- [x] format, build, vet silent
- [x] both packages ok on PostgreSQL 16; 9 named tests PASS
- [x] only the section 3 paths and sidecars changed
- [x] no UBYHOST_GO_PATHS, Caddy, compose, env or App/ change; nothing pushed
- UI: not applicable (dormant, rule 7/10 as stated in brief)

## 4. Deviations
- PostgreSQL started on port 55731 with data dir /var/tmp/pg-1573 (orchestrator instruction) instead of 55570.
- Worktree branch is worktree-agent-a1a24b800a03be5fa (not task/1573-...), as the one-big-PR mode requires.

## 5. Questions
None.

## 6. Owner steps left
None for this brief; the owner steps of the brief apply after 1570 to 1573 are merged and green.

## Skips
Go test SKIP count: 0 (package-wide -v run on cleaning and cmd/ubyhost-web).
