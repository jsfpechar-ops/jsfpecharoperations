# 0480 report: Go G5b UbyPort response parse and classify

Status: review

## Files changed (steps 1 to 6)
- Fixtures: `App/tests/golden/ubyport/responses/*.xml` (15 inputs), `classify_cases.json` (23 cases), `expected.json` (oracle).
- Python: `App/scripts/ubyport_golden_responses.py`, `App/tests/test_ubyport_golden_responses.py`.
- Go: `go/internal/ubyport/response.go`, `codes.go`, `response_test.go`, `codes_test.go`.
- Commits: `0480 step 1` to `0480 step 6`. Step 7 adds this report.

## Commands (last lines)
- `gofmt -l .` empty, `go vet ./...` clean, `go test ./internal/ubyport/ -count=1` ok (all response, classify and table cases pass).
- `python3 scripts/ubyport_golden_responses.py --out /tmp/g` then `diff` against committed `expected.json`: `SAME`.
- `python3 scripts/context_lint.py`: `context lint: OK` (warning only: status.md is older than 4 commits, orchestrator updates it).
- pytest: not run, App/.venv does not exist here. CI is the gate. I called the two test functions directly with python3 and they passed.

## Diff stat
`git diff --stat origin/main` (before this report was added) lists 25 files, 1377 insertions, 1 deletion. It includes earlier branch commits that touched `docs/context/status.md` and `docs/tasks/0480-go-g5b-ubyport-response.md`, which I did not edit in this session.

## Deviations
- `scalar` in each response is a dict with both methods (`TestDostupnosti`, `MaximalniDelkaSeznamu`) for every file. The brief did not say which files get it, so I applied it to all.
- Go identifiers renamed to avoid clashes with `request.go` (`respNSXSI`, `respGoldenDir`).
- Also ported `IsDuplicate` (listed in brief section 2, not in the Go list).
- Python `str.strip()` and `\s` treat U+001C to U+001F as whitespace; Go uses `isPySpace` to match.
- Go `\b` replaced by a hand-written word-boundary check (`hasWord`).
- Known residual difference: Go's `encoding/xml` accepts an unbound namespace prefix, which Python's ElementTree refuses. No fixture covers it.

## Questions
- Should `scalar` appear only on the two scalar fixtures? I kept the all-files reading above.

## Owner steps left
- None for this step. No PR opened, as instructed. The orchestrator updates `docs/context/status.md`.
