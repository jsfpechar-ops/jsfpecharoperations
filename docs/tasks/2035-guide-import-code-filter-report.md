# 2035 report: guide import code filter

Status: review

## Files changed

- `go/internal/guideimport/codefilter.go` (new): `FilterCodes`, `FilterCardFields`, `CodeKeywords`, `AsksForCode`
- `go/internal/guideimport/codefilter_test.go` (new): `TestFilterCodes`, `TestFilterCodesIdempotent`, `TestAsksForCode` (EN/CZ/DE), `TestFilterCardFields`

## §7 acceptance

- [x] Table rows pass (EN/CZ/DE removed, kept, overlap, idempotence, 20k line)
- [x] No log/slog/fmt.Print in `codefilter.go`
- [x] stdlib only; `go.mod` unchanged
- [x] Existing `guideimport` tests green

## Commands (last 5 lines)

`gofmt -l internal/guideimport/`: (empty)

`go vet ./internal/guideimport/`: (empty)

`go test … -run 'FilterCodes|FilterCardFields|AsksForCode' -v`: all subtests PASS; `ok …/guideimport`

`go test ./internal/guideimport/`: `ok …/guideimport 0.095s`

`python3 scripts/context_lint.py`: `ERROR docs/context/test-map.md: ~1265 tokens > cap 1200` … `context lint: FAIL` (pre-existing)

`rg log… codefilter.go`: (empty)

## Deviations

- **DE Garagencode row:** brief allows `Garage code 5566`; table uses that (not `Garagencode 5566`).
- **Digit guard:** trailing `.` after a code is allowed so rows like `The door code is 4827.` remove the run (brief adjacency list is ambiguous on sentence-final period).
- **ß:** folded to single `s` per rune (1:1 index map with original runes; full `ss` expansion skipped).
- **No PR / push** per executor instructions.

## Row changes

None required beyond the DE garage wording noted in the brief.

## Owner steps

None.