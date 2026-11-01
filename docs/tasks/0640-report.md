# 0640 report: Go iCal parser

Status: review

## Files changed
- `App/scripts/ical_golden.py` (new): writes `<name>.json` next to each fixture from `parse_events`.
- `App/tests/test_ical_golden.py` (new): regenerates into a temp dir, asserts byte equality.
- `go/internal/ical/testdata/*.ics` and `*.json` (new): 22 fixtures, invented data only.
- `go/internal/ical/parse.go` (new): stdlib-only parser, `ParseEvents`, `PlatformOf`, `IsBlock`.
- `go/internal/ical/parse_test.go` (new): golden byte test, `IsBlock` and `PlatformOf` tables.
- `docs/tasks/0640-go-ical-parse.md`: Status `ready` changed to `review` (the lint rejects `ready`).

## Commands (last lines)
- Python: `.venv/bin/python -m pytest tests/test_ical_golden.py tests/test_icalsync.py -q --tb=short -x` gives `51 passed in 4.81s`.
- Go: `gofmt -l` empty, `go vet ./...` clean, `go test ./internal/ical/ -count=1` gives `ok ... internal/ical 0.006s`.
- Lint: `python3 scripts/context_lint.py` fails only on the brief's old `Status: ready`; fixed as above.

## Brief section 7
- [x] Diff lists only section 3 files and the brief.
- [x] Both test commands pass, 0 skipped.

## Deviations (Python behaviour that Go copies)
- **BOM (stop-and-ask, see Questions):** Python does not strip a UTF-8 BOM and raises. Golden `lf_bom.json` is `{"error": true}`; Go errors too.
- A line with no colon is skipped silently. A line with a non-name token before the colon errors.
- URL is unescaped like TEXT (`\,` gives `,`), not kept raw.
- SEQUENCE: `01` becomes `1`; `0` becomes `""` (Python's `or ""` on a falsy int); non-integer text is kept as written.
- Unknown TZID: date taken as written, no zone shift (probed with 23:30).
- Email regex is greedy: `jana.novakova@example.org.` keeps the trailing dot.
- DURATION `PT5H` gives end = start (date arithmetic drops hours).
- Empty document and any document without exactly one VCALENDAR root: error.
- `TrimSpace` per brief; Python `strip()` also removes `\x1c` to `\x1f`. Differs only for those control characters.
- `\w` written as `[\p{L}\p{N}_]`, `\s` and `\d` as Python's Unicode classes.

## Environment
- `App/.venv` lacked pytest; installed `requirements-dev.txt` into it (not a repo change).

## Questions
1. Should the Go parser strip the BOM (brief trap) or keep Python's error? Python is the source of truth, so Go currently errors. Changing this means changing `ical_golden.py` expectations and the Python parser.

## Owner steps left
- None. Nothing pushed; PR not opened (branch `task/0640-go-ical-parse`).
