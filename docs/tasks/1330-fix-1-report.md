# 1330-fix-1 report

Status: review
Commit: 101aaea70 "1330-fix-1 step 3: stay fee review fixes" (patch applied, sha256 6321385313e4...ad446d matched; both file hashes OK)

## 1. Files changed (step 3 commit only)
- go/internal/web/stayfees/handlers.go (edit)
- go/internal/web/stayfees/actions_test.go (edit)
`git diff --stat bafc793..HEAD` lists 54 files: branch HEAD carries commits from other briefs (1200-fix-1, INPASS, 1330 steps) on top of bafc793. Only the step 3 commit is this brief's change.

## 2. Commands
- `gofmt -l internal/web/stayfees cmd/ubyhost-web && go vet ./internal/web/stayfees/ ./cmd/ubyhost-web/` -> no output, rc 0.
- `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:54330/postgres go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1 -v | grep ...` -> DB tests RAN (not skipped; no SKIP lines):
  - `--- PASS: TestActionsMatchPython`, `TestCSRFRequired`, `TestCSVHeadNotAllowed`, `TestOverflowIDNotFound`, `TestMultipartForm` (all PASS)
  - `ok github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stayfees`
  - `ok github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web`
- `python3 scripts/context_lint.py | tail -3` -> `WARN 19 commit(s) touched App/ after the last status.md update` (warning only), `next free: task 1331 | migration 0046`, `context lint: OK`.

## 3. Section 7
- [x] Patch sha256 matched; file hashes matched after step 2.
- [x] gofmt and go vet print nothing.
- [x] Go tests PASS, five named tests ran.
- [ ] `git diff --stat bafc793..HEAD` lists only §3 paths: NOT MET, see Deviations.
- [x] context lint ends `context lint: OK`.

## 4. Deviations
- Patch file written to the session scratchpad instead of /tmp (session rule). Same content, same sha256.
- §7 stat check fails for the reason in section 1; the step 3 commit itself touches only the two §3 files.

## 5. Questions
- Should the orchestrator confirm the branch base? bafc793 is not the merge base of HEAD's extra commits.

## 6. Fixes in the PR (for the PR body)
1. HEAD on the CSV route answers 405 (Allow: GET, JSON body) before CSRF/login/DB.
2. Path ids outside int64 are looked up and answer not-found; non-integer ids stay 422.
3. multipart/form-data bodies are parsed before CSRF (1 MiB cap).
4. Test sets the legal versions in goldenEnv and seeds the same constant.
Corrected deviation 2 text: "Month and form ids: Python str.isdigit also accepts non-ASCII digits (a month like ２０２６-10 parses; a form id like ٣ is looked up as 3; ² crashes int() with a 500). Go accepts only ASCII digits: such a month falls back to the default month, such a form id means not found. Path ids: FastAPI answers 422 for non-ASCII digits, as Go does, and an id outside int64 is looked up and not found, as Go now does (1330-fix-1). Left: pydantic also accepts 1_0, ' 5' and '5.0' as path ids, where Go answers 422; on SQLite (tests only) Python answers 500 for an id outside int64."
No new outbound request. No new personal-data field. Routes stay off: Caddy routes only UBYHOST_GO_PATHS to Go.

## 7. Owner steps left
None for this brief. Merge follows the 1330 owner step (merge-pr-on-green.sh after CI green).
