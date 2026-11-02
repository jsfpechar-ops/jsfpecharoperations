# 0640: Go iCal: parse feed documents exactly like Python `parse_events`
Status: review
Depends on: none | Base commit: origin/main | Branch: task/0640-go-ical-parse
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
First slice of porting the `ical` job (Airbnb/Booking calendar sync) to Go. Go gets a pure parser that turns an iCal document into the same event list as `App/app/icalsync.py` `parse_events` (line 302), plus `platform_of` (363). No database, no network, nothing calls it yet, nothing changes in production. Rule 1: a wrong date here becomes a wrong police deadline, so Go must match Python byte for byte on golden files.
## 2. Context
- Python source of truth: `App/app/icalsync.py` lines 40-128 (regexes, `PLATFORM_HINTS`, `RECURRENCE_PROPERTIES`) and 194-370 (`_as_date`, `_event_status`, `is_block`, `_guest_name_hint`, `_synthetic_uid`, `_ambiguous_synthetic_keys`, `parse_events`, `platform_of`). Python uses `icalendar` 7.3.0; the venv is at `App/.venv` (already installed).
- Pattern to copy: golden files in `App/tests/golden/ubyport/` pinned by `App/tests/test_ubyport_golden.py` and read by `go/internal/ubyport/request_test.go`.
- **No new Go dependency.** Write a small RFC 5545 reader with the standard library only.
- **Traps:**
  - Unfold lines: a CRLF or LF followed by one space or tab joins to the previous line (drop the newline and that one whitespace char). Accept LF-only files. Strip a leading UTF-8 BOM.
  - Property names and parameter names are case-insensitive; parameter values may be quoted (`TZID="Europe/Prague"`); the value starts after the first `:` that is not inside quotes.
  - TEXT values (SUMMARY, DESCRIPTION, UID, LOCATION, URL as icalendar treats it): unescape `\n`/`\N` to newline, `\,` `\;` `\\` to the char. Python then also replaces any remaining literal backslash-n in DESCRIPTION with a newline; do the same, in that order. Check against the golden output, not your reading.
  - `.strip()` in Python strips Unicode whitespace; use `strings.TrimSpace`. `text[:80]` counts code points: slice runes.
  - Python `\w` is Unicode; Go RE2 `\w` is ASCII. Write `[\p{L}\p{N}_]` wherever the Python regex has `\w`. Use `(?i)` and `(?m)` where Python has IGNORECASE / MULTILINE.
  - Dates: `VALUE=DATE` or an 8-digit value is a bare date. `...Z` is UTC: convert to `Europe/Prague` then take the date. `TZID=X` with a known zone: that zone, then Prague. No Z and no TZID: floating, take the date as written. Import `time/tzdata` so zones work in the Alpine image. For an unknown TZID and for `SEQUENCE:01`, do what the golden file says Python does.
  - No DTEND: positive DURATION adds only its whole days to the start date (Python `date + timedelta` drops hours); otherwise one night. An event without DTSTART is skipped.
  - `METHOD:CANCEL` on the calendar cancels every event. STATUS `CANCELLED` or `CANCELED` (case-insensitive after trim).
  - `recurring` is true when RRULE, RDATE or EXDATE is present with a non-empty value.
  - `reservation_url`: first `https?://\S+` in description, else in URL, then trim trailing `.,);` chars.
  - Synthetic UIDs: sha1 over `summary\x1fdescription\x1fsequence`, first 16 hex; ambiguity counted over UID-less events with a DTSTART before any event is read; ambiguous ones get `-YYYY-MM-DD`.
  - A document Python cannot parse must make Go return an error (no partial list).
## 3. Files
New: `App/scripts/ical_golden.py` (generator: reads every `go/internal/ical/testdata/*.ics`, writes `<name>.json` next to it with `json.dumps(events, ensure_ascii=False, indent=2, sort_keys=True)` + newline, or `{"error": true}` when `parse_events` raises), `App/tests/test_ical_golden.py` (regenerates into a temp dir and asserts byte equality with the committed json, like the ubyport test), `go/internal/ical/testdata/*.ics` and `*.json` (at least 14 cases: Airbnb reserved + not-available with phone and URL; Booking `CLOSED - Not available`; folded long DESCRIPTION; escaped commas/semicolons/`\\n`; UTC late-evening DTSTART that moves to the next Prague day; TZID start; floating datetime; VALUE=DATE; DURATION without DTEND (P3D and PT5H); no DTEND/no DURATION; two UID-less identical events plus one unique; METHOD:CANCEL; STATUS:CANCELLED; RRULE; name hint with Czech letters longer than 80 chars; email in description; LF-only file with BOM; one malformed document). All data invented, no real guests. New Go: `go/internal/ical/parse.go`, `go/internal/ical/parse_test.go`. Write `docs/tasks/0640-report.md`. Nothing else.
## 4. Steps
1. Write the .ics fixtures, then the generator, run it: `cd App && .venv/bin/python scripts/ical_golden.py 2>&1 | tail -5`.
2. `parse.go`, package `ical`, top comment naming the Python lines: `type Event struct` with JSON tags equal to the Python keys (`*string` for the three nullable fields), `func ParseEvents(text string) ([]Event, error)`, `func PlatformOf(url, text string) string` (first 800 runes of text, lowercased), `func IsBlock(summary string) bool`.
3. `parse_test.go`: for each fixture, marshal Go's result the same way (sorted keys, 2-space indent, no HTML escaping, trailing newline; an error gives `{"error": true}`) and compare bytes with the json file. Add table tests for `IsBlock` and `PlatformOf`.
4. Commit: `0640: Go iCal parser matching Python parse_events, golden files`.
## 5. Do not touch
`App/app/` (all), `go/internal/` outside `ical/`, `go/cmd/`, `go.mod`/`go.sum`, compose, CI, templates/CSS/JS.
## 6. Commands
- From `App/`: `.venv/bin/python -m pytest tests/test_ical_golden.py tests/test_icalsync.py -q --tb=short -x 2>&1 | tail -30`.
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/ical/ -count=1 2>&1 | tail -30`.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
`git diff --stat origin/main` lists only section 3 files and this brief. Both test commands pass, 0 skipped.
## 8. Stop and ask
Stop if matching Python needs a new dependency, or a fixture shows Python behaviour that looks like a bug (report it, do not copy it silently).
## 9. Report
`docs/tasks/0640-report.md`: command tails, diff stat, each place where Go had to imitate a surprising Python result.
