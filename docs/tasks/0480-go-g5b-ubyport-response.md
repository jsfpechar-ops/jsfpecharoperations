# 0480: Go G5b: UbyPort responses parsed and classified in Go, matching Python
Status: todo
Depends on: 0479 (#634) | Base commit: main | Branch: claude/project-thread-b1f6s1
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
Plan v4 step 17 (G5), second slice, rule 1 (filing correctness). Go reads what UbyPort answers (fault, Chyby result, receipt PDF, scalar and code-list answers) and decides per guest record "accepted", "error" or "not_correctable" exactly as Python does. No network, no database, no wiring into the service: transport (NTLM) and the submission claim are G5c.
## 2. Context
- Python source of truth: `App/app/ubyport/soap.py` lines 150-308 (`_find` walks `root.iter()`, pre-order, root included; `_is_nil`; `parse_fault`; `MAX_PDF_BYTES`; `clean_pdf_base64`; `response_element_names`; `parse_zapis_response`; `parse_scalar_response`; `parse_ciselnik_response`) and `App/app/ubyport/errors.py` lines 30-205 (`KNOWN_CODES`, `KNOWN_SEVERITY`, `ACCEPTED_MAX_SEVERITY`, `_NON_CORRECTABLE_RE`, `FALLBACK_TEXT`, `normalise_code`, `split_codes`, `describe`, `severity`, `is_accepted_code`, `is_non_correctable`, `is_duplicate`, `is_duplicate_code`, `record_is_duplicate`, `classify`).
- Pattern to copy: `App/scripts/ubyport_golden.py` + `App/tests/test_ubyport_golden.py` (Python writes the oracle, a test regenerates it and compares) and `go/internal/ubyport/request_test.go` (Go reads `../../../App/tests/golden/...`). `test_ubyport_golden.py` globs `golden/ubyport/*.xml`, so the new files go in the subfolder `golden/ubyport/responses/`.
- **Traps (Python and Go differ here):**
  - `el.text` is only the text **before the first child**, `None` when empty. Build a small tree with `encoding/xml` `Decoder.Token()` (local name, attributes, leading text, children); skip comments and processing instructions. Do not use `xml.Unmarshal`.
  - A parse error must be an error in Go too: empty input, truncated XML, non-XML text, and anything but whitespace after the root element closes (Go's decoder keeps reading; Python refuses).
  - nil = an attribute with namespace `http://www.w3.org/2001/XMLSchema-instance`, local name `nil`, value exactly `true`.
  - `.strip()`: use `strings.TrimSpace`. Base64 whitespace removal uses Python `\s` on str, which is Unicode (includes U+00A0): remove runes with `unicode.IsSpace`, not Go regexp `\s` (ASCII only). The `too_large` length check counts characters (runes). Check order: empty, too_large (length), decode (`base64.StdEncoding`), too_large (bytes), not `%PDF` prefix. Return `base64.StdEncoding.EncodeToString(raw)`.
  - `parse_fault`: `Reason` in SOAP 1.2 has only whitespace before its `Text` child, so it is skipped and `Text` is used; parts joined with ` / `; no parts gives `Unspecified SOAP fault`.
  - `_NON_CORRECTABLE_RE` uses Python Unicode `\b`/`\w`; Go RE2 `\b` is ASCII-only and breaks on `pozdě` and `ápozdní`. Write `IsNonCorrectable` by hand on `strings.ToLower(text)`: `duplic` anywhere; `pozdě` with a word boundary on both sides; `pozdn` with a boundary before; `late` with a boundary on both sides. Word rune = `unicode.IsLetter || unicode.IsNumber || '_'`.
  - `describe` uses `code.zfill(3)`: pad with `0` to 3 runes, after a leading `+` or `-` if present (`"-5"` gives `"-05"`). Codebook lookup order `code`, padded, `ERR_CZE_`+padded, non-empty values only, then `KNOWN_CODES`, then `FALLBACK_TEXT[lang]` (unknown lang: `en`) with `%(code)s` replaced.
  - `normalise_code`: trim, drop a case-insensitive leading `ERR_CZE_`, strip leading `0`s; all zeros gives `"0"`, empty stays empty.
  - `classify` messages are `"<raw code>: <text>"`; the state uses the English text even when `lang` is `cs`.
## 3. Files
New: `App/scripts/ubyport_golden_responses.py`, `App/tests/test_ubyport_golden_responses.py`, `App/tests/golden/ubyport/responses/` (inputs `*.xml`, `classify_cases.json`; oracle `expected.json`), `go/internal/ubyport/response.go` (+ `response_test.go`), `go/internal/ubyport/codes.go` (+ `codes_test.go`). Write `docs/tasks/0480-report.md`.
## 4. Steps
1. Response inputs (invented values only; PDFs are base64 of a short text starting `%PDF-1.4`). One file each: `accepted_receipt` (header nil, two empty `string` items, receipt base64 wrapped with CRLF, spaces and one U+00A0, error PDF nil, `PseudoRazitko`); `record_errors` (header `5;`, items `106;` and `112;150;`, valid error PDF, receipt nil, misspelt `PseudoRazirko`); `bad_documents` (receipt `@@@`, error PDF = base64 of `hello`); `empty_documents` (receipt empty element, error PDF whitespace only); `text_then_child` (`ChybyHlavicky` with text, a child element and tail text; members in another order and another prefix); `fault11`; `fault12` (Code, Reason/Text); `fault_empty`; `scalar_availability`; `scalar_max`; `ciselnik` (two `CiselnikType` entries); `truncated`; `not_xml` (`Service Unavailable`); `empty` (0 bytes); `trailing_garbage` (valid envelope then `junk`).
2. `classify_cases.json`: list of `{name, header, record, codebook, severities, lang}` (null allowed). Cover at least: no codes; `112;`; `150;`; `106;`; unknown `999;` in `en` and `cs`; `0112` and `ERR_CZE_112`; `-5`; severities overriding 112 to 5; header plus record codes; codebook texts with unknown severity: `Oznámeno pozdě`, `pozdě,` at the end, `později`, `ápozdní`, `zpozdněno`, `related`, `LATE fee`; codebook `Duplicitní záznam` under `ERR_CZE_151` with record `151;`.
3. `ubyport_golden_responses.py` (header like `ubyport_golden.py`, `--out DIR`): writes `expected.json` (`indent=1, ensure_ascii=False, sort_keys=True`, trailing newline) with `tables` (`known_codes`, `known_severity`, `fallback_text`, `accepted_max_severity`, `max_pdf_bytes`), `responses` keyed by file name: `fault`, `element_names`, `zapis` (the dict, or the string `"parse_error"`), `scalar` for `TestDostupnosti` and `MaximalniDelkaSeznamu` (value, null, or `"parse_error"`), `ciselnik` (list or `"parse_error"`); `classify` keyed by case name: `state`, `messages`, `record_is_duplicate`. Run it once to write the committed `expected.json`.
4. `test_ubyport_golden_responses.py`: regenerate into `tmp_path` and assert equal bytes to the committed `expected.json`; assert every input file has an entry.
5. `response.go` and `codes.go`: exported Go versions of each function in section 2 (Go names, `*string` for Python `None`), tables as Go maps. Package comments: the Python oracle in `golden/ubyport/responses/expected.json` is the contract.
6. `response_test.go` / `codes_test.go`: load `expected.json`; compare every response and classify case; compare the Go tables to `tables`. On mismatch print the case name, want and got.
## 5. Do not touch
Every file under `App/app/`, the 0477 golden files, `go/internal/ubyport/request*.go`, `go/cmd/`, `go/internal/jobs`, `go.mod`, compose, CI.
## 6. Commands
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/ubyport/ -count=1 2>&1 | tail -30`.
- From `App/`: `python3 scripts/ubyport_golden_responses.py --out /tmp/g && diff /tmp/g/expected.json tests/golden/ubyport/responses/expected.json && echo SAME`. If `.venv/bin/python` exists, also `.venv/bin/python -m pytest tests/test_ubyport_golden_responses.py tests/test_ubyport_golden.py -q --tb=short -x 2>&1 | tail -30` and check `${PIPESTATUS[0]}`; otherwise CI is the gate, say so in the report.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
Every response and classify case in `expected.json` matches in Go, and the tables match. `git diff --stat origin/main` lists only section 3 files, this brief and `docs/context/status.md`.
## 8. Stop and ask
Stop if a case cannot be matched without changing Python code; report the case, want and got.
## 9. Report
`docs/tasks/0480-report.md`: command tails, the diff stat, and any Python/Go difference you handled beyond section 2.
