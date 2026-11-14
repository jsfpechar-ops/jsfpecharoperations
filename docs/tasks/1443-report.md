# 1443 report: Go guest guide editor, part 4 (QR page, print PNG, "new link")

Status: review. Branch: worktree-agent-ada5f4bd680b16a94 (PR-mode: no push, no PR; the orchestrator collects the commits).

## 1. Files changed (`git diff --stat 0f4c2ce95...HEAD`)

- go/internal/web/ai/guide_qr.go (126 lines, sha256 OK)
- go/internal/web/ai/guide/templates/guide_qr.tmpl (23 lines, sha256 OK)
- go/internal/web/ai/guide_qr_test.go (89 lines, sha256 OK)
- docs/tasks/1443-report.md, docs/tasks/1443-go-guide-editor-qr.md (Status: review)

Commits: `1443 step 1` (sidecars copied, hashes checked). Step 5 commit contains this report and the Status line.

## 2. Commands (last lines of output)

- Step 1 `sha256sum -c`: `go/internal/web/ai/guide_qr.go: OK`, `.../guide/templates/guide_qr.tmpl: OK`, `.../guide_qr_test.go: OK`
- Step 2 `gofmt -l`, `go build ./...`, `go vet`: no output (clean).
- Step 4 `go test ./internal/web/ai/ ./cmd/ubyhost-web/ -count=1` (PostgreSQL 16, port 5564):
  `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai 3.921s`
  `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web 0.107s`
- Step 4 named tests: `--- PASS: TestGuideQRPNGMatchesTheCode (0.01s)`, `--- PASS: TestGuideQRRoutes (10.29s)`, `ok ... 10.316s`. No SKIP, no FAIL.
- `git diff --stat -- go/go.mod go/go.sum`: empty.
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings only, none about this brief's files).

## 3. Acceptance (§7)

- [x] sha256 OK for all 3 files
- [x] step 2 silent
- [x] step 4 both packages ok; both named tests PASS on PostgreSQL
- [x] go.mod and go.sum unchanged
- [x] diff against base lists only the 3 §3 Go files (sidecars were already committed with the brief)
- [x] no UBYHOST_GO_PATHS, Caddy, compose, env or Python change; no push
- [x] UI: not applicable (dormant pages, no path routes to them)

## 4. Deviations

- PR-mode overrides applied: stayed on the worktree branch (not `task/1443-...`); step 0 branch check and base commit `68c0e0985` replaced by the current HEAD (`0f4c2ce95`, anchors matched).
- Step 3 used a fresh disposable PostgreSQL 16 on port 5564, data dir `/var/tmp/pg1443/data` (the 1440 server was not running). Stopped and deleted after the run.
- Step 2 and step 3 changed no files, so no commits for them.
- The session was interrupted by a usage limit after step 1; resumed at step 2 after checking `git log` (step 1 was committed).

## 5. Questions

None.

## 6. Owner steps left

Before the switch, scan the printed QR code of one real property with a phone (the PNG bytes differ from Python's). Test-map row for `go/internal/web/ai` is for the coordinator to add.
