# 0555: Go police: guest and apartment validation, matching Python byte for byte
Status: todo
Depends on: 0554 | Base commit: main | Branch: claude/project-thread-dwlrdj
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
Plan v4 step 17 (G5), rule 1. The Go sweep (0556-0558) may only send a guest Python would call complete, and only from an apartment Python would accept. Go gets the checks behind `reporting.guest_is_complete` and `validation.validate_apartment` in a new shared package, proven equal to Python by a golden file Python writes. Nothing calls the new code; nothing changes in production.
## 2. Context
- Python source of truth, `App/app/validation.py`: `Issue` (219), `validate_guest` (534-651) and every helper it calls (`validate_birth_date` 391, `parse_birth_date` 361, `_expand_two_digit_year` 352, `age_on` 164, `validate_residence` 448, `signature_issue` 797, `parse_signature_data_url` 754, constants and regexes at the top of the file), `guest_is_reportable` (815), `validate_apartment` (1018-1101) with its regexes (974-987), `errors_only` (1102), `parse_iso_date` (1110). `App/app/reporting.py`: `_stay_dates` (132), `guest_dict` (212), `guest_signature_issue` (236, the `translate=None`, `allow_imported=True` path only), `guest_issues` (319), `guest_is_complete` (333).
- Country list: `go/internal/ubyport/countries.json` already exists; if `validate_guest` needs the country codes, load the same embedded data, do not copy the file.
- **Traps:**
  - Message strings, field names, severities and issue order are byte-for-byte copies; Python f-strings become `fmt.Sprintf` with the same text.
  - Python `len()` counts code points: use `utf8.RuneCountInString`, never `len`. `.upper()`/`.strip()` follow Python (see `pyUpper` in `go/internal/ubyport/request.go`; reuse the same rule, do not import ubyport from the new package, copy the small helper with a comment).
  - Python `re.match` anchors only at the start; `re.fullmatch` at both ends. Check each regex call and anchor the Go regexp the same way.
  - `parse_iso_date` returns None on any bad input; a nil date in Go must flow through `validate_guest` exactly as Python's None does (some checks are skipped when a date is None).
  - The signature check decodes base64 and may check image bytes: port it exactly, including the size cap `_MAX_SIGNATURE_PAYLOAD_CHARS`.
  - `age_on` and any "today" logic: if Python reads the clock, the Go function takes `today` as a parameter and the golden file pins it.
## 3. Files
New: `go/internal/validation/validation.go`, `go/internal/validation/validation_test.go`, `go/internal/validation/testdata/golden.json`, `App/scripts/validation_golden.py` (writes the golden file from the real Python functions; header comment says how to run it from `App/`). Write `docs/tasks/0555-report.md`. Nothing else.
## 4. Steps
1. `validation_golden.py`: at least 80 guest cases and 25 apartment cases covering every message branch of `validate_guest`, `guest_signature_issue` and `validate_apartment` (empty, too long, bad pattern, non-Latin letters, Czech vs foreign nationality, visa rules, birth date too old/young/future/two-digit year, stay dates missing or swapped, residence parts, imported signature, empty signature, bad data URL, oversized payload, valid PNG data URL), plus a few fully valid ones. Each guest case: the guest row fields, the reservation `date_from`/`date_to`, and the expected `guest_issues` list as `[field, message, severity]` and `guest_is_complete`. Each apartment case: the row and the expected `validate_apartment` list. Pin any clock. Run it to write `testdata/golden.json` (sorted keys, indent 1, UTF-8 not escaped).
2. `validation.go`, top comment naming the Python lines: `type Issue struct{ Field, Message, Severity string }`; `GuestRow` holding the fields `guest_dict` reads plus `stay_from`, `stay_to`, `signature_png` (strings, empty for NULL); `func GuestIssues(g GuestRow, dateFrom, dateTo string) []Issue`, `func GuestIsComplete(g GuestRow, dateFrom, dateTo string) bool`, `func GuestIsReportable(nationality string) bool`, `func ValidateApartment(ap map[string]string) []Issue`, `func ErrorsOnly([]Issue) []Issue`, `func ParseISODate(s string) (time.Time, bool)`. Unexported helpers for the rest.
3. `validation_test.go`: load the golden file with `embed`, compare every case exactly (message bytes, order, severity), and print the case name on failure.
4. Commit: `0555: Go guest and apartment validation matching Python`.
## 5. Do not touch
Every other file in `App/` and `go/`, `go.mod`/`go.sum`, compose, CI, templates/CSS/JS.
## 6. Commands
- From `App/`: `.venv/bin/python scripts/validation_golden.py 2>&1 | tail -5` (create the venv first if missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt`).
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/validation/ -count=1 -v 2>&1 | tail -30`.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
`git diff --stat origin/main` lists only section 3 files and this brief. Every golden case passes in Go; the script rerun gives a byte-identical golden file.
## 8. Stop and ask
Stop if `validate_guest` depends on a database read, a config value that differs in production, or a translation catalog on the `translate=None` path.
## 9. Report
`docs/tasks/0555-report.md`: command tails, diff stat, case counts, anything you decided beyond section 2.
