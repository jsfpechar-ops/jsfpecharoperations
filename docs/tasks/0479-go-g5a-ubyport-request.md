# 0479: Go G5a: the UbyPort ZapisUbytovane request built in Go, byte for byte
Status: todo
Depends on: 0477 (#632) | Base commit: main | Branch: task/0479-go-g5a-ubyport-request
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
Plan v4 step 17 (G5), first slice, rule 1 (filing correctness). A Go package builds the police filing request from apartment, reservation and guest values and matches the 0477 golden envelopes byte for byte. No network, no database, no wiring into the service: this slice only proves the bytes.
## 2. Context
- Golden files: `App/tests/golden/ubyport/cases.json` (6 cases: `apartment`, `reservation`, `guests`, `wsa`) and `<name>.xml` for each. The auth code is `GOLDEN-AUTH` (`App/scripts/ubyport_golden.py` line 24, `render` lines 27-33). Do not regenerate or edit them.
- Envelope: `App/app/ubyport/soap.py` lines 27-133: namespaces, `ACTION_PREFIX`, `_XML_ILLEGAL` (control chars become one space), `HEADER_FIELDS`, `GUEST_FIELDS` (fixed order), `_node` (None gives `<d:X i:nil="true" />` with the space; bool gives `true`/`false`), `build_envelope`, `build_zapis_ubytovane`.
- **Escaping trap:** Python uses `xml.sax.saxutils.escape`, which replaces only `&`, `<`, `>` (in that order, `&` first). Go `encoding/xml` escapes quotes and more, so do not use it; write a three-replacement `strings.NewReplacer("&", "&amp;", "<", "&lt;", ">", "&gt;")`. The auth code is escaped the same way.
- Payload: `App/app/reporting.py` `header_from_apartment` (lines 115-129), `_stay_dates` (131-139), `guest_payload` (142-163). Truncations like `[:35]` count characters: slice runes, not bytes. `.strip()` is Unicode whitespace (`strings.TrimSpace`). `.upper()`: use `strings.ToUpper`; the only known difference is `ß` (Python gives `SS`), so map `ß` to `SS` before `ToUpper`. `cPurp` is an int only when the stripped purpose is all ASCII digits and non-empty, otherwise nil. An empty string becomes nil everywhere Python has `or None`.
- Helpers: `App/app/validation.py` `normalise_zip` (313-314, keep ASCII and Unicode digits: use `unicode.IsDigit`), `parse_iso_date` (1110-1116: first 10 chars as `YYYY-MM-DD`, else none), `compose_residence` (415-428, `MAX_RESIDENCE` 255 runes, lang `cs`), `country_name` (199-205), `countries` (174-184) reading `App/app/data/countries.json`.
- Countries in Go: `go:embed` cannot reach `App/`, so commit a copy at `go/internal/ubyport/countries.json` and add a Python test that it equals `App/app/data/countries.json` byte for byte.
- Go test pattern: `go/internal/billing/quote_test.go` reads fixtures from a relative path.
## 3. Files
New: `go/internal/ubyport/request.go` (+ `request_test.go`), `go/internal/ubyport/countries.json`, `App/tests/test_go_countries_copy.py`. Write `docs/tasks/0479-report.md`.
## 4. Steps
1. `request.go`: types `Apartment` and `Guest` (string fields named as the JSON keys of `cases.json`, with JSON tags) and `Reservation{DateFrom, DateTo}`; `Header(a Apartment) map[string]*string`, `GuestFields(g Guest, r Reservation) map[string]any` (nil values for Python None), `BuildZapisUbytovane(header, guests, authCode string, wsa bool) string`, and `CountryName(code, lang string) string`. Package comment: the bytes must equal the Python builder; the golden test is the contract.
2. `request_test.go`: for every case in `../../../App/tests/golden/ubyport/cases.json`, build with `GOLDEN-AUTH` and compare to the `.xml` file byte for byte; on mismatch print the first differing offset and 60 bytes around it. Add small unit tests for: `ß` upper-casing, a 40-rune Czech name cut to 35 runes, `&<>"'` escaping, a control char becoming a space, purpose `"10 "` gives 10 and `"1a"` gives nil, empty `stay_from` falling back to the reservation date.
3. Copy `App/app/data/countries.json` to `go/internal/ubyport/countries.json` with `cp`. `App/tests/test_go_countries_copy.py`: the two files are byte-identical; the failure message says to re-copy.
## 5. Do not touch
Every file under `App/app/`, the golden files, `go/cmd/`, `go/internal/jobs`, compose, CI.
## 6. Commands
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/ubyport/ -count=1 -v 2>&1 | tail -30`.
- From `App/`: `.venv/bin/python -m pytest tests/test_go_countries_copy.py tests/test_ubyport_golden.py -q --tb=short -x 2>&1 | tail -30`; check `${PIPESTATUS[0]}` before pushing.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
All 6 golden envelopes match byte for byte, and the unit tests pass. `git diff --stat origin/main` lists only section 3 files and the brief.
## 8. Stop and ask
Stop if a golden case cannot be matched without changing a golden file or Python code; report the case, the offset and both byte runs.
## 9. Report
`docs/tasks/0479-report.md`: command tails, the diff stat, and any Python/Go difference you had to handle beyond section 2.
