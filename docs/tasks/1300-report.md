# 1300 report

Status: review. Branch `task/1300-go-property-actions`, commit `1300: Go port of property settings POST actions`.

## 1. Files changed (`git diff --stat a83df54..HEAD`)

Brief commit (docs): `docs/tasks/1300-go-property-actions.md` (Status line), `docs/plans/1300-files/*` (8 bundle files).
Step commit (code, 10 files, 2027 insertions): `go/internal/web/properties/{properties.go, localpath.go, slug.go, properties_test.go, i18n_keys.txt, i18n.json, testdata/actions_cases.json, testdata/actions_golden.json}`, `go/cmd/ubyhost-web/register_web_properties.go`, `App/tests/test_go_properties_actions.py`.
Report commit: `docs/tasks/1300-report.md`, brief Status line.

## 2. Commands (last 5 lines of output)

- Step 1 copies: `Switched to a new branch 'task/1300-go-property-actions'`, `COPY OK`.
- Step 2 sha256 (8 files): all `OK`.
- Step 3 `i18n.json` sha256: `4296e438fc7898167208410d0d58735ebe4098dd56dede30353f3f9331bf2828`, matches.
- Step 4 golden: `2 passed in 1.62s`; sha256 `7a17d6974ee4c552aed292edcc7cb5150a94b7dd6513a344ebf2385cffdd770f`, matches.
- §6 Go (`gofmt`, `go vet`, `go test -count=1 -v`, build): PASS for `TestActionsMatchPython`, `TestReturnToMatchesPython`, `TestReadableMatchesPython`, `TestRandomShapes`, `TestCatalogHasEveryKey`, `TestRegisterDoesNotTouchThePool`, `TestRoutesRegisterOnce` (and the cmd package tests); two `ok` lines; no SKIP; `BUILD OK`.
- §6 Python: `2 passed in 1.75s`.
- §6 lint: `next free: task 1301 | migration 0046`, `context lint: OK` (one unrelated WARN about shared test names in other briefs).
- §6 `git status`: clean after commit.

## 3. §7 acceptance

- [x] Step 2: 8 OK; steps 3 and 4 sums match.
- [x] `go vet` clean, `gofmt -l` empty, `go build ./cmd/ubyhost-web` OK.
- [x] `TestActionsMatchPython` ran (not skipped) and passed; other properties tests and `./cmd/ubyhost-web` pass.
- [x] `tests/test_go_properties_actions.py`: 2 passed.
- [x] `git diff --stat a83df54..HEAD` lists only §3 paths plus the brief and `docs/plans/1300-files/`.
- [ ] `grep -rn UBYHOST_GO_PATHS go/internal/web go/cmd/ubyhost-web/register_web_properties.go` prints nothing. It prints one hit: a comment at `register_web_properties.go:4` ("nothing sends these paths here until UBYHOST_GO_PATHS names them"). Left as is, because the brief says not to edit copied files. Nothing is added to the variable.

## 4. Deviations

- Brief step 1 creates `task/1300-go-property-actions` from the current `claude/1300-go-property-settings` HEAD (`109f8a3`), not from `a83df54`; the brief's `git diff --stat a83df54..HEAD` still covers it.
- Commit message trailers: the brief's commit command has no trailers; I added the two `Co-Authored-By` / `Claude-Session` lines as the orchestrator asked.
- The `UBYHOST_TEST_DATABASE_URL` variable was set on each command (shell state does not persist); the Go replay did not skip.

## 5. Questions

- Accept the comment hit in `register_web_properties.go:4` for the acceptance grep, or should a later brief reword the comment?

## 6. Owner steps left

1. Wait for the draft PR's CI `go` job (Postgres replay) to go green.
2. Nothing to deploy or configure: routes stay off until a later brief adds them to `UBYHOST_GO_PATHS`.
