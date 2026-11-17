# 1835: `guestcontract` package: contract version, form config and payload types, payload encoding, shared guest checks

Status: in-progress
Depends on: 1834 (table and column names) | Base commit: current tip of the working branch | Branch: task/1835-guestcontract-package
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (the guest checks decide what a guest may submit for UbyPort filing; exact diffs only; orchestrator reads the full diff before ready)
Plan: [guest-form-isolation](../plans/guest-form-isolation.md) section 3 (rules 4-6) and 11 (D4).

> **One PR mode.** Commit each step as `1835 step k`. Never push, merge or deploy. The files are written by one extraction command (step 1): do not retype them.
>
> **Reading this brief (it is over 350 lines):** read up to the line `## Files`, then from `## 5. Do not touch` to the end (`grep -n '^## ' docs/tasks/1835-guestcontract-package.md` gives the ranges). Skip the "Files" section: step 1 copies it. Open a file there only when a test fails and the report needs a line number.

## 1. Objective

Add `go/internal/guestcontract`, the one package both the app and the future guest program compile: contract version (`V1`, `Supported`), the Go types of `guest_form_snapshot.form_config` and of the `guest_inbox` payload, payload encode/decode (gzip, then the data-key Fernet of the `_enc` columns), and `CheckNewGuest`, the guest save route's checks that need no database. It also adds the missing Go port of `normalise_guest` and the stay-date checks to `go/internal/validation`, pinned byte for byte against the real Python by a golden file.

## 2. Context

Hard rules: 1 filing correctness first; 4 no new dependency (only the standard library and `golang.org/x/text`, already in `go/go.mod`); 11 Go first.

**Rule 1 of the plan: nothing here changes what is filed.** The payload carries the guest's fields **as posted** (`GuestForm`), never normalised values. On processing the app normalises them exactly as the guest route does today, so UbyPort receives the same values. `CheckNewGuest` only decides whether the guest may submit; the app runs the same checks again on processing and a disagreement is an alert (plan rule 6). No existing behaviour changes: `go/internal/validation` gets one new file of new exported functions; no existing function changes.

**Where the checks come from.** `App/app/routes/guest.py`, `guest_form_save`, lines 2410-2475 (new guest, so `existing` is `None`):
```
    raw = _guest_form_raw(form, apartment)
    values = validation.normalise_guest(raw, clamp=False)
    stay_from, stay_to = _locked_stay_dates(reservation, existing)
```
then `validation.validate_guest(values, ..., raw=raw)`, `validate_stay_dates`, `validate_stay_date_text`, the party-size check when `expected_guest_count(reservation) is None`, `reporting.guest_signature_issue(signature, translate, allow_imported=False, under_15=child)`, the `signed_by` check, `legal_ack`, the passport photo. `_guest_form_raw` is `App/app/routes/admin_helpers.py` `guest_form_raw` (line 158). `go/internal/validation/validation.go` already ports `validate_guest` (unexported `validateGuest`) and the signature parser; it does not port `normalise_guest` ("the NFKD folding in the normalisers is not ported", its package comment).

**Excluded (need the database or a stored row):** editing an existing guest (stored stay dates, kept signature), `signed_by` (the adults on the stay), the passport photo (stored photo, policy), the PIN. Display localisation (`_localize_issues`, `_name_latin_issues`) is the form's job (brief 1840); the checks return English messages and the form localises by field, as Python does.

**Encryption (D4).** Same scheme as the `_enc` columns and `db.encrypt_blob` (`App/app/db.py` line 2391): MultiFernet with the data keys. Go: `secure.LoadDataKeys(os.Getenv)` returns `*secure.MultiFernet` with `Encrypt([]byte) (string, error)` and `Decrypt(token string, ttl time.Duration, now time.Time) ([]byte, error)` (`go/internal/secure/fernet.go` lines 156 and 166). Python reads a payload with `gzip.decompress(db.decrypt_blob(value))` then `json.loads`.

**Anchors** (verify with `grep -nF`; if one is missing, STOP):

- `go/internal/validation/validation.go`: `func validateGuest(g GuestRow, stayFrom, stayTo *time.Time, today time.Time, raw map[string]string) []Issue {`
- same file: `func certainlyUnderAge(raw string, when time.Time, years int) bool {`
- same file: `func parseSignatureDataURL(value string) ([]byte, error) {`
- same file: `func pyUpper(s string) string {`
- same file: `inpassDoc               = "INPASS"`
- `go/internal/secure/fernet.go`: `func (m *MultiFernet) Decrypt(token string, ttl time.Duration, now time.Time) ([]byte, error) {`
- `go/go.mod`: `golang.org/x/text v0.44.0`
- `App/app/validation.py`: `def normalise_guest(data: Dict[str, Optional[str]], clamp: bool = True) -> Dict[str, str]:`
- `App/app/reporting.py`: `UNDER_SIGN_AGE = 15`
- `App/migrations_pg/00020_guest_contract.sql` exists (brief 1834 merged).

**Contract surface (later briefs reuse these names):** package `guestcontract`; constants `V1`, `Current`, `UnderSignAge`, `MaxPayloadBytes`; `Supported(v int) bool`; `TokenHash(linkKey string) string`; `NewIdempotencyKey() (string, error)`; `ValidIdempotencyKey(string) bool`; types `FormConfig`, `Stay`, `Submission`, `GuestForm` (JSON names in `types.go`); `EncodePayload(*secure.MultiFernet, Submission) ([]byte, error)`; `DecodePayload(*secure.MultiFernet, []byte) (Submission, error)`; errors `ErrUnsupportedVersion`, `ErrPayloadTooLarge`, `ErrBadIdempotencyKey`; `CheckNewGuest(GuestForm, FormConfig, Stay, time.Time) []validation.Issue`. In `validation`: `GuestTextFields`, `Strip`, `NormaliseGuest`, `NoteForParentDocument`, `GuestFormRaw`, `ValidateGuestForm`, `CertainlyUnderAge`, `ValidateStayDates`, `ValidateStayDateText`, `GuestFormSignatureIssue`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/validation/guest_form.go` | create | port of `normalise_guest` and helpers, stay-date checks, guest signature check; exported wrappers |
| `go/internal/guestcontract/contract.go` | create | package doc, versions, token hash, idempotency key |
| `go/internal/guestcontract/types.go` | create | `FormConfig`, `Stay`, `Submission`, `GuestForm` |
| `go/internal/guestcontract/payload.go` | create | encode/decode |
| `go/internal/guestcontract/check.go` | create | `CheckNewGuest` |
| `go/internal/guestcontract/contract_test.go` | create | table tests: version, hash, key, payload |
| `go/internal/guestcontract/check_test.go` | create | golden test against Python |
| `App/scripts/guest_form_golden.py` | create | writes the golden from the real Python |
| `go/internal/guestcontract/testdata/guest_form_golden.json` | generate | by the script, never by hand |
| `docs/tasks/1835-report.md` | create | the report (section 9) |

No other file may change.

## 4. Steps

0. **Anchors.** Verify every anchor in section 2 with `grep -nF`. If one is missing, STOP. Command: `ls App/migrations_pg/00020_guest_contract.sql` (expect the path).

1. **Write the eight files.** From the repo root run exactly (it copies each block under "Files" below to its path; nothing is retyped):
```
python3 - <<'PY'
import re, pathlib
text = pathlib.Path("docs/tasks/1835-guestcontract-package.md").read_text(encoding="utf-8")
blocks = re.findall(r"<!-- file: (\S+) -->\n```[a-z]*\n(.*?)\n```\n", text, re.S)
for path, body in blocks:
    p = pathlib.Path(path)
    if p.exists():
        raise SystemExit(f"STOP: {path} already exists")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body + "\n", encoding="utf-8")
    print("wrote", path)
print(len(blocks), "files")
PY
```
   Expected: eight `wrote` lines and `8 files`. Any other count: STOP.

2. **Golden.** From `App/`: if `.venv/bin/python` is missing, run `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt 2>&1 | tail -5`. Then `.venv/bin/python scripts/guest_form_golden.py 2>&1 | tail -5`. Expected: `wrote .../guest_form_golden.json (37 cases)`.

3. **Format and vet.** From `go/`: `gofmt -l internal/guestcontract internal/validation 2>&1 | tail -5` (expect no output) and `go vet ./internal/guestcontract/... ./internal/validation/... 2>&1 | tail -10` (expect no output).

4. **Tests.** Section 6. If `TestCheckNewGuestMatchesPython` or `TestNormaliseGuestMatchesPython` fails, do not change Go code or the golden to make it pass: STOP and put the failing case names and the want/got lines in the report.

5. Write the report.

## Files

<!-- file: go/internal/validation/guest_form.go -->
```go
package validation

// Guest form normalisation and the stay-date checks, ported from
// App/app/validation.py (normalise_guest with clamp=False and its helpers,
// note_for_parent_document, validate_stay_dates, validate_stay_date_text) and
// the guest-path signature check of App/app/reporting.py
// (guest_signature_issue with allow_imported=False and the English catalog).
// Brief 1835. go/internal/guestcontract/testdata/guest_form_golden.json,
// written by App/scripts/guest_form_golden.py from the real Python, pins it.
//
// Known differences, outside the golden cases: Python str.upper() also expands
// ligatures and a few other letters (pyUpper here handles only ß, like
// ubyport.pyUpper); the Unicode tables of Go and Python may differ for letters
// added in newer Unicode versions.

import (
	"strings"
	"time"
	"unicode"

	"golang.org/x/text/unicode/norm"
)

const (
	inpassNotePrefix             = "Dítě zapsané v pasu rodiče, číslo dokladu rodiče: "
	defaultPurpose               = "99"
	stayOutsideBookingMessage    = "These dates do not match your booking. Reload this page, or ask your host."
	stayDateUnreadableMessage    = "The stay dates on this page are not readable. Reload the page and try again."
	guestSignatureMissingMessage = "Please sign in the box before you continue."
	nameLetters                  = "abcdefghijklmnopqrstuvwxyz" +
		"ABCDEFGHIJKLMNOPQRSTUVWXYZ" +
		"ĄŁĽŚŠŞŤŹŽŻąłľśšşťźžżŔÁÂĂÄĹĆÇČÉĘËĚÍÎĎĐŃŇÓÔŐÖŘŮÚŰÜÝŢ" +
		"ŕáâăäĺćçčéęëěíîďđńňóôőöřůúűüýţß"
)

// GuestTextFields is validation.GUEST_TEXT_FIELDS, in order.
var GuestTextFields = []string{
	"surname", "first_name", "birth_date", "nationality", "doc_number", "visa_number",
	"res_street", "res_city", "res_country", "purpose", "note",
}

var (
	nameAllowed      = runeSet(nameLetters + " '-")
	residenceAllowed = runeSet(nameLetters + " '-" + "0123456789/.,;:()&#@")
	docAllowed       = runeSet("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
	// mrzFold is validation._MRZ_FOLD.
	mrzFold = map[rune]string{
		'Đ': "D", 'đ': "d", 'Ð': "D", 'ð': "d",
		'Ø': "O", 'ø': "o", 'Œ': "OE", 'œ': "oe",
		'Æ': "AE", 'æ': "ae", 'Þ': "TH", 'þ': "th",
		'İ': "I", 'ı': "i", 'Ħ': "H", 'ħ': "h",
		'Ŧ': "T", 'ŧ': "t", 'Ə': "E", 'ə': "e",
		'Ŀ': "L", 'ŀ': "l", 'Ŋ': "N", 'ŋ': "n",
		'Ƶ': "Z", 'ƶ': "z", 'Ɖ': "D", 'ɖ': "d",
	}
)

func runeSet(s string) map[rune]bool {
	m := make(map[rune]bool)
	for _, r := range s {
		m[r] = true
	}
	return m
}

// isPySpace is Python str.isspace() for one character (the pyStrip rule).
func isPySpace(r rune) bool {
	return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f)
}

// Strip is Python str.strip() with no arguments.
func Strip(s string) string { return pyStrip(s) }

// firstRunes is Python s[:n] on a str.
func firstRunes(s string, n int) string {
	i := 0
	for pos := range s {
		if i == n {
			return s[:pos]
		}
		i++
	}
	return s
}

// stripForbidden is validation.strip_forbidden.
func stripForbidden(v string) string {
	return strings.Map(func(r rune) rune {
		switch {
		case r == '\r' || r == '\n' || r == '|':
			return ' '
		case r <= 0x08 || r == 0x0b || r == 0x0c || (r >= 0x0e && r <= 0x1f) || r == 0x7f:
			return ' '
		}
		return r
	}, v)
}

// collapseSpaces is validation.collapse_spaces: re.sub(r"\s+", " ", v).strip().
func collapseSpaces(v string) string {
	return strings.Join(strings.FieldsFunc(v, isPySpace), " ")
}

// foldToAllowed is validation.fold_to_allowed.
func foldToAllowed(text string, allowed map[rune]bool) string {
	var b strings.Builder
	for _, ch := range text {
		if allowed[ch] {
			b.WriteRune(ch)
			continue
		}
		mapped, ok := mrzFold[ch]
		if !ok {
			var m strings.Builder
			for _, c := range norm.NFKD.String(string(ch)) {
				if norm.NFKD.PropertiesString(string(c)).CCC() == 0 {
					m.WriteRune(c)
				}
			}
			mapped = m.String()
		}
		for _, c := range mapped {
			if allowed[c] {
				b.WriteRune(c)
			}
		}
	}
	return b.String()
}

func normaliseName(v string) string {
	text := pyUpper(collapseSpaces(stripForbidden(v)))
	return collapseSpaces(foldToAllowed(text, nameAllowed))
}

func normaliseResidencePart(v string) string {
	text := collapseSpaces(stripForbidden(v))
	text = strings.Map(func(r rune) rune {
		if (r >= 0x2010 && r <= 0x2015) || r == 0x2212 {
			return '-'
		}
		return r
	}, text)
	return collapseSpaces(foldToAllowed(text, residenceAllowed))
}

func normaliseDocument(v string) string {
	return foldToAllowed(pyUpper(stripForbidden(v)), docAllowed)
}

func normaliseNote(v string) string {
	return firstRunes(collapseSpaces(stripForbidden(v)), maxNote)
}

// decimalValue is unicodedata.decimal for a character in category Nd. Decimal
// digits are encoded in runs that start at zero, so the value is the distance
// from the start of the run, modulo 10.
func decimalValue(r rune) (int, bool) {
	if !unicode.Is(unicode.Nd, r) {
		return 0, false
	}
	start := r
	for start > 0 && unicode.Is(unicode.Nd, start-1) {
		start--
	}
	return int(r-start) % 10, true
}

// asciiDecimals is validation._ascii_decimals.
func asciiDecimals(v, keep string) string {
	var b strings.Builder
	for _, ch := range v {
		switch {
		case strings.ContainsRune(keep, ch):
			b.WriteRune(ch)
		case ch >= '0' && ch <= '9':
			b.WriteRune(ch)
		default:
			if d, ok := decimalValue(ch); ok {
				b.WriteByte(byte('0' + d))
			}
		}
	}
	return b.String()
}

// expandTwoDigitYear is validation._expand_two_digit_year with today injected.
func expandTwoDigitYear(two string, today time.Time) string {
	n := 0
	for _, c := range two {
		n = n*10 + int(c-'0')
	}
	current := today.Year()
	a, b := 1900+n, 2000+n
	best := 0
	for _, c := range []int{a, b} {
		if c <= current && c > best {
			best = c
		}
	}
	if best == 0 {
		best = a
	}
	return itoa(best)
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var d []byte
	for n > 0 {
		d = append([]byte{byte('0' + n%10)}, d...)
		n /= 10
	}
	return string(d)
}

// pad2 is f"{int(s):02d}" for a string of ASCII digits of any length.
func pad2(s string) string {
	t := strings.TrimLeft(s, "0")
	if t == "" {
		t = "0"
	}
	for len(t) < 2 {
		t = "0" + t
	}
	return t
}

// zfill4 is str.zfill(4) for a string of ASCII digits.
func zfill4(s string) string {
	for len(s) < 4 {
		s = "0" + s
	}
	return s
}

// normaliseBirthDate is validation.normalise_birth_date with today injected.
func normaliseBirthDate(v string, today time.Time) string {
	raw := pyStrip(stripForbidden(v))
	if raw == "" {
		return ""
	}
	separated := strings.NewReplacer("/", ".", "-", ".").Replace(raw)
	digitsAndDots := asciiDecimals(separated, ".")
	if strings.Contains(digitsAndDots, ".") {
		var parts []string
		for _, p := range strings.Split(digitsAndDots, ".") {
			if p != "" {
				parts = append(parts, p)
			}
		}
		if len(parts) == 3 {
			day, month, year := parts[0], parts[1], parts[2]
			if len(year) == 2 {
				year = expandTwoDigitYear(year, today)
			}
			return pad2(day) + pad2(month) + zfill4(year)
		}
	}
	digits := asciiDecimals(raw, "")
	if len(digits) == 8 {
		return digits
	}
	if len(digits) == 6 {
		return digits[:4] + expandTwoDigitYear(digits[4:], today)
	}
	return digits
}

// NormaliseGuest is validation.normalise_guest(raw, clamp=False). raw holds the
// GuestTextFields as GuestFormRaw builds them. today is the clock of
// _expand_two_digit_year. Stay dates and signature stay empty.
func NormaliseGuest(raw map[string]string, today time.Time) GuestRow {
	return GuestRow{
		Surname:     normaliseName(raw["surname"]),
		FirstName:   normaliseName(raw["first_name"]),
		BirthDate:   normaliseBirthDate(raw["birth_date"], today),
		Nationality: firstRunes(pyUpper(pyStrip(raw["nationality"])), 3),
		DocNumber:   normaliseDocument(raw["doc_number"]),
		VisaNumber:  normaliseDocument(raw["visa_number"]),
		ResStreet:   normaliseResidencePart(raw["res_street"]),
		ResCity:     normaliseResidencePart(raw["res_city"]),
		ResCountry:  firstRunes(pyUpper(pyStrip(raw["res_country"])), 3),
		Purpose:     firstRunes(pyStrip(raw["purpose"]), 2),
		Note:        normaliseNote(raw["note"]),
	}
}

// NoteForParentDocument is validation.note_for_parent_document.
func NoteForParentDocument(parentDocument, note string) string {
	parent := normaliseDocument(parentDocument)
	if parent == "" {
		return note
	}
	text := inpassNotePrefix + parent
	if note != "" {
		text += " " + note
	}
	return firstRunes(text, maxNote)
}

// GuestFormRaw is admin_helpers.guest_form_raw for the guest link: form holds
// the posted values by field name (missing means empty), defaultPurpose is the
// apartment's default_purpose column.
func GuestFormRaw(form map[string]string, defaultPurposeOfApartment string) map[string]string {
	raw := make(map[string]string, len(GuestTextFields))
	for _, f := range GuestTextFields {
		raw[f] = pyStrip(form[f])
	}
	if raw["purpose"] == "" {
		if defaultPurposeOfApartment != "" {
			raw["purpose"] = defaultPurposeOfApartment
		} else {
			raw["purpose"] = defaultPurpose
		}
	}
	if raw["doc_number"] == inpassDoc {
		raw["note"] = NoteForParentDocument(pyStrip(form["parent_doc_number"]), raw["note"])
	}
	return raw
}

// ValidateGuestForm is validation.validate_guest(values, stay_from, stay_to, raw=raw).
func ValidateGuestForm(g GuestRow, stayFrom, stayTo *time.Time, today time.Time, raw map[string]string) []Issue {
	return validateGuest(g, stayFrom, stayTo, today, raw)
}

// CertainlyUnderAge is validation.certainly_under_age; a nil date is false.
func CertainlyUnderAge(birth string, when *time.Time, years int) bool {
	if when == nil {
		return false
	}
	return certainlyUnderAge(birth, *when, years)
}

// ValidateStayDates is validation.validate_stay_dates (tolerance 0 days).
func ValidateStayDates(stayFrom, stayTo, allowedFrom, allowedTo *time.Time) []Issue {
	var issues []Issue
	if stayFrom != nil && allowedFrom != nil && stayFrom.Before(*allowedFrom) {
		issues = append(issues, Issue{"stay_from", stayOutsideBookingMessage, severityError})
	}
	if stayTo != nil && allowedTo != nil && stayTo.After(*allowedTo) {
		issues = append(issues, Issue{"stay_to", stayOutsideBookingMessage, severityError})
	}
	return issues
}

// ValidateStayDateText is validation.validate_stay_date_text.
func ValidateStayDateText(stayFrom, stayTo string) []Issue {
	var issues []Issue
	for _, p := range [][2]string{{"stay_from", stayFrom}, {"stay_to", stayTo}} {
		if p[1] == "" {
			continue
		}
		if _, ok := ParseISODate(p[1]); !ok {
			issues = append(issues, Issue{p[0], stayDateUnreadableMessage, severityError})
		}
	}
	return issues
}

// GuestFormSignatureIssue is reporting.guest_signature_issue(value,
// translate=English catalog, allow_imported=False, under_15=under15).
func GuestFormSignatureIssue(value string, under15 bool) *Issue {
	text := pyStrip(value)
	if under15 && text == "" {
		return nil
	}
	if text == importedSignature || text == "" {
		return &Issue{"signature", guestSignatureMissingMessage, severityError}
	}
	if _, err := parseSignatureDataURL(value); err != nil {
		return &Issue{"signature", signatureInvalidMessage, severityError}
	}
	return nil
}
```

<!-- file: go/internal/guestcontract/contract.go -->
```go
// Package guestcontract is the contract between the app and the guest program
// (plan docs/plans/guest-form-isolation.md section 3): the contract version,
// the form config JSON of guest_form_snapshot, the payload of guest_inbox and
// its encoding, and the guest checks that need no database. Both programs
// compile this one package, so they cannot disagree on a field or a check.
// Brief 1835; the tables are migration 00020 (brief 1834).
package guestcontract

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"regexp"
)

// V1 is contract version 1. Current is the version this build writes.
const (
	V1      = 1
	Current = V1
)

// Supported reports whether a row of contract version v can be read: the
// current version N and the one before it, N-1 (plan section 3 rule 5).
func Supported(v int) bool {
	return v >= V1 && (v == Current || v == Current-1)
}

var idempotencyKeyRE = regexp.MustCompile(`^[0-9a-f]{32}$`)

// TokenHash is the SHA-256 hex of a guest link key, as claim.token_hash in
// App/app/claim.py. It is the token_hash column of both contract tables.
func TokenHash(linkKey string) string {
	sum := sha256.Sum256([]byte(linkKey))
	return hex.EncodeToString(sum[:])
}

// NewIdempotencyKey returns 32 lower-case hex characters (128 random bits).
// The form page makes one when it is drawn, so a repeated post is one row.
func NewIdempotencyKey() (string, error) {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", err
	}
	return hex.EncodeToString(b[:]), nil
}

// ValidIdempotencyKey matches the CHECK on guest_inbox.idempotency_key.
func ValidIdempotencyKey(key string) bool {
	return idempotencyKeyRE.MatchString(key)
}
```

<!-- file: go/internal/guestcontract/types.go -->
```go
package guestcontract

// FormConfig is guest_form_snapshot.form_config (JSONB): everything the guest
// program needs to draw and check the form for one link key without the app.
type FormConfig struct {
	ApartmentID         int64             `json:"apartment_id"`
	ApartmentName       string            `json:"apartment_name"`
	Languages           []string          `json:"languages"`
	DefaultPurpose      string            `json:"default_purpose"`
	PassportPhotoPolicy string            `json:"passport_photo_policy"`
	LegalVersions       map[string]string `json:"legal_versions"`
	Stays               []Stay            `json:"stays"`
}

// Stay is one stay the link may register guests for.
type Stay struct {
	ReservationID int64  `json:"reservation_id"`
	DateFrom      string `json:"date_from"` // ISO date, the booking's date_from
	DateTo        string `json:"date_to"`   // ISO date, the booking's date_to
	// ExpectedGuests is nil when the stay has no expected count yet; the form
	// then asks for party_size.
	ExpectedGuests   *int `json:"expected_guests"`
	RegisteredGuests int  `json:"registered_guests"`
}

// Submission is the plaintext of guest_inbox.payload_enc. received_at and
// token_hash are columns, not payload fields.
type Submission struct {
	ContractVersion int       `json:"contract_version"`
	IdempotencyKey  string    `json:"idempotency_key"`
	ReservationID   int64     `json:"reservation_id"`
	Lang            string    `json:"lang"`
	Guest           GuestForm `json:"guest"`
}

// GuestForm holds one guest as posted, by the form field names of the guest
// page, before any normalisation. The app normalises on processing exactly as
// today, so what is filed with UbyPort does not depend on this package.
type GuestForm struct {
	Surname         string `json:"surname"`
	FirstName       string `json:"first_name"`
	BirthDate       string `json:"birth_date"`
	Nationality     string `json:"nationality"`
	DocNumber       string `json:"doc_number"`
	VisaNumber      string `json:"visa_number"`
	ResStreet       string `json:"res_street"`
	ResCity         string `json:"res_city"`
	ResCountry      string `json:"res_country"`
	Purpose         string `json:"purpose"`
	Note            string `json:"note"`
	ParentDocNumber string `json:"parent_doc_number"`
	Signature       string `json:"signature"`
	PartySize       string `json:"party_size"`
	LegalAck        bool   `json:"legal_ack"`
	ChildSignRole   string `json:"child_sign_role"`
	SignedBy        string `json:"signed_by"`
}

// Fields returns the posted text fields by form name, as the guest route reads
// them from the request (missing means empty).
func (g GuestForm) Fields() map[string]string {
	return map[string]string{
		"surname":           g.Surname,
		"first_name":        g.FirstName,
		"birth_date":        g.BirthDate,
		"nationality":       g.Nationality,
		"doc_number":        g.DocNumber,
		"visa_number":       g.VisaNumber,
		"res_street":        g.ResStreet,
		"res_city":          g.ResCity,
		"res_country":       g.ResCountry,
		"purpose":           g.Purpose,
		"note":              g.Note,
		"parent_doc_number": g.ParentDocNumber,
	}
}
```

<!-- file: go/internal/guestcontract/payload.go -->
```go
package guestcontract

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// MaxPayloadBytes caps the decompressed JSON. A signature is at most about
// 350 KB of base64 (validation.maxSignaturePayloadChars), so 1 MiB is ample.
const MaxPayloadBytes = 1 << 20

var (
	// ErrUnsupportedVersion: the row's contract version is not N or N-1.
	ErrUnsupportedVersion = errors.New("guestcontract: unsupported contract version")
	// ErrPayloadTooLarge: the decompressed payload exceeds MaxPayloadBytes.
	ErrPayloadTooLarge = errors.New("guestcontract: payload too large")
	// ErrBadIdempotencyKey: not 32 lower-case hex characters.
	ErrBadIdempotencyKey = errors.New("guestcontract: bad idempotency key")
)

// EncodePayload is the value of guest_inbox.payload_enc: JSON, gzip, then a
// Fernet token with the data keys (decision D4: the encryption of the _enc
// columns). Python reads it with gzip.decompress(db.decrypt_blob(value)).
func EncodePayload(keys *secure.MultiFernet, s Submission) ([]byte, error) {
	if !Supported(s.ContractVersion) {
		return nil, ErrUnsupportedVersion
	}
	if !ValidIdempotencyKey(s.IdempotencyKey) {
		return nil, ErrBadIdempotencyKey
	}
	plain, err := json.Marshal(s)
	if err != nil {
		return nil, err
	}
	if len(plain) > MaxPayloadBytes {
		return nil, ErrPayloadTooLarge
	}
	var buf bytes.Buffer
	zw := gzip.NewWriter(&buf)
	if _, err := zw.Write(plain); err != nil {
		return nil, err
	}
	if err := zw.Close(); err != nil {
		return nil, err
	}
	token, err := keys.Encrypt(buf.Bytes())
	if err != nil {
		return nil, err
	}
	return []byte(token), nil
}

// DecodePayload reverses EncodePayload. It refuses a version other than N or
// N-1 and a payload over MaxPayloadBytes once decompressed.
func DecodePayload(keys *secure.MultiFernet, data []byte) (Submission, error) {
	var s Submission
	compressed, err := keys.Decrypt(string(data), 0, time.Now())
	if err != nil {
		return s, err
	}
	zr, err := gzip.NewReader(bytes.NewReader(compressed))
	if err != nil {
		return s, fmt.Errorf("guestcontract: payload is not gzip: %w", err)
	}
	plain, err := io.ReadAll(io.LimitReader(zr, MaxPayloadBytes+1))
	if err != nil {
		return s, fmt.Errorf("guestcontract: payload gzip: %w", err)
	}
	if len(plain) > MaxPayloadBytes {
		return s, ErrPayloadTooLarge
	}
	if err := json.Unmarshal(plain, &s); err != nil {
		return s, fmt.Errorf("guestcontract: payload json: %w", err)
	}
	if !Supported(s.ContractVersion) {
		return s, ErrUnsupportedVersion
	}
	return s, nil
}
```

<!-- file: go/internal/guestcontract/check.go -->
```go
package guestcontract

import (
	"strconv"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// UnderSignAge is reporting.UNDER_SIGN_AGE: a guest under 15 on arrival does
// not sign.
const UnderSignAge = 15

const (
	partySizeMessage = "Please enter how many people are staying (1–60)."
	legalAckMessage  = "Please confirm that you have read the legal information."
)

// CheckNewGuest runs the checks of the guest save route (App/app/routes/guest.py,
// guest_form_save) that need no database, for a NEW guest (no stored row), in
// the route's order: validate_guest, validate_stay_dates,
// validate_stay_date_text, party size, signature, legal acknowledgement.
// Messages are the English ones; the form localises by field, as
// _localize_issues does.
//
// Not here, because they need the database or a stored row: editing an
// existing guest (its stored stay dates and kept signature), "signed_by" (the
// list of adults on the stay), the passport photo (stored photo and policy
// decision), and the PIN.
//
// Known difference: Python int() also reads "1_0" and non-ASCII digits as a
// party size; strconv.Atoi does not. Such a post is refused here and would
// be accepted by Python.
func CheckNewGuest(g GuestForm, cfg FormConfig, st Stay, today time.Time) []validation.Issue {
	raw := validation.GuestFormRaw(g.Fields(), cfg.DefaultPurpose)
	values := validation.NormaliseGuest(raw, today)
	from := isoDate(st.DateFrom)
	to := isoDate(st.DateTo)
	signature := validation.Strip(g.Signature)
	child := validation.CertainlyUnderAge(values.BirthDate, from, UnderSignAge)
	if child {
		signature = ""
	}
	issues := validation.ValidateGuestForm(values, from, to, today, raw)
	issues = append(issues, validation.ValidateStayDates(from, to, from, to)...)
	issues = append(issues, validation.ValidateStayDateText(st.DateFrom, st.DateTo)...)
	if st.ExpectedGuests == nil {
		n, err := strconv.Atoi(validation.Strip(g.PartySize))
		if err != nil {
			n = 0
		}
		if n < 1 || n > 60 {
			issues = append(issues, validation.Issue{Field: "party_size", Message: partySizeMessage, Severity: "error"})
		}
	}
	if sig := validation.GuestFormSignatureIssue(signature, child); sig != nil {
		issues = append(issues, *sig)
	}
	if !g.LegalAck {
		issues = append(issues, validation.Issue{Field: "legal_ack", Message: legalAckMessage, Severity: "error"})
	}
	return issues
}

func isoDate(s string) *time.Time {
	t, ok := validation.ParseISODate(s)
	if !ok {
		return nil
	}
	return &t
}
```

<!-- file: go/internal/guestcontract/contract_test.go -->
```go
package guestcontract

import (
	"bytes"
	"encoding/base64"
	"errors"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

func TestSupported(t *testing.T) {
	cases := []struct {
		v    int
		want bool
	}{{-1, false}, {0, false}, {1, true}, {2, false}}
	for _, c := range cases {
		if got := Supported(c.v); got != c.want {
			t.Errorf("Supported(%d) = %v, want %v", c.v, got, c.want)
		}
	}
}

func TestTokenHash(t *testing.T) {
	// SHA-256("abc"), the same as hashlib.sha256(b"abc").hexdigest().
	want := "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
	if got := TokenHash("abc"); got != want {
		t.Errorf("TokenHash = %s, want %s", got, want)
	}
}

func TestIdempotencyKey(t *testing.T) {
	k, err := NewIdempotencyKey()
	if err != nil {
		t.Fatal(err)
	}
	cases := []struct {
		key  string
		want bool
	}{
		{k, true},
		{"0123456789abcdef0123456789abcdef", true},
		{"0123456789ABCDEF0123456789ABCDEF", false},
		{"0123456789abcdef", false},
		{"0123456789abcdef0123456789abcdeg", false},
		{"", false},
	}
	for _, c := range cases {
		if got := ValidIdempotencyKey(c.key); got != c.want {
			t.Errorf("ValidIdempotencyKey(%q) = %v, want %v", c.key, got, c.want)
		}
	}
}

func testKeys(t *testing.T, fill byte) *secure.MultiFernet {
	t.Helper()
	key := []byte(base64.URLEncoding.EncodeToString(bytes.Repeat([]byte{fill}, 32)))
	m, err := secure.NewMultiFernet(key)
	if err != nil {
		t.Fatal(err)
	}
	return m
}

func sample() Submission {
	return Submission{
		ContractVersion: V1,
		IdempotencyKey:  "0123456789abcdef0123456789abcdef",
		ReservationID:   42,
		Lang:            "de",
		Guest:           GuestForm{Surname: "Novák", FirstName: "Jan", LegalAck: true, Signature: "data:image/png;base64,AAAA"},
	}
}

func TestPayloadRoundTrip(t *testing.T) {
	keys := testKeys(t, 1)
	enc, err := EncodePayload(keys, sample())
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Contains(enc, []byte("Nov")) {
		t.Fatal("payload is not encrypted")
	}
	compressed, err := keys.Decrypt(string(enc), 0, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	if len(compressed) < 2 || compressed[0] != 0x1f || compressed[1] != 0x8b {
		t.Fatal("plaintext is not gzip")
	}
	got, err := DecodePayload(keys, enc)
	if err != nil {
		t.Fatal(err)
	}
	if got != sample() {
		t.Errorf("round trip\nwant %+v\ngot  %+v", sample(), got)
	}
}

func TestPayloadRefusals(t *testing.T) {
	keys := testKeys(t, 1)
	bad := sample()
	bad.ContractVersion = 2
	if _, err := EncodePayload(keys, bad); !errors.Is(err, ErrUnsupportedVersion) {
		t.Errorf("version 2: err = %v, want ErrUnsupportedVersion", err)
	}
	bad = sample()
	bad.IdempotencyKey = "short"
	if _, err := EncodePayload(keys, bad); !errors.Is(err, ErrBadIdempotencyKey) {
		t.Errorf("bad key: err = %v, want ErrBadIdempotencyKey", err)
	}
	enc, err := EncodePayload(keys, sample())
	if err != nil {
		t.Fatal(err)
	}
	if _, err := DecodePayload(testKeys(t, 2), enc); err == nil {
		t.Error("decoded with the wrong key")
	}
	tampered := append([]byte(nil), enc...)
	tampered[len(tampered)/2] ^= 1
	if _, err := DecodePayload(keys, tampered); err == nil {
		t.Error("decoded a tampered payload")
	}
}
```

<!-- file: go/internal/guestcontract/check_test.go -->
```go
package guestcontract

import (
	_ "embed"
	"encoding/json"
	"reflect"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// guest_form_golden.json is written by App/scripts/guest_form_golden.py from
// the real Python with the clock pinned to 2026-11-01. Regenerate it, never
// edit it by hand.
//
//go:embed testdata/guest_form_golden.json
var guestFormGolden []byte

type goldenIssue struct {
	Field    string `json:"field"`
	Message  string `json:"message"`
	Severity string `json:"severity"`
}

type goldenCase struct {
	Name           string            `json:"name"`
	Form           map[string]string `json:"form"`
	Stay           Stay              `json:"stay"`
	DefaultPurpose string            `json:"default_purpose"`
	Values         map[string]string `json:"values"`
	Issues         []goldenIssue     `json:"issues"`
}

func loadGolden(t *testing.T) (time.Time, []goldenCase) {
	t.Helper()
	var g struct {
		Today string       `json:"today"`
		Cases []goldenCase `json:"cases"`
	}
	if err := json.Unmarshal(guestFormGolden, &g); err != nil {
		t.Fatal(err)
	}
	today, err := time.Parse("2006-01-02", g.Today)
	if err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) < 30 {
		t.Fatalf("golden has %d cases, want at least 30", len(g.Cases))
	}
	return today, g.Cases
}

func formOf(m map[string]string) GuestForm {
	return GuestForm{
		Surname: m["surname"], FirstName: m["first_name"], BirthDate: m["birth_date"],
		Nationality: m["nationality"], DocNumber: m["doc_number"], VisaNumber: m["visa_number"],
		ResStreet: m["res_street"], ResCity: m["res_city"], ResCountry: m["res_country"],
		Purpose: m["purpose"], Note: m["note"], ParentDocNumber: m["parent_doc_number"],
		Signature: m["signature"], PartySize: m["party_size"], LegalAck: m["legal_ack"] != "",
		ChildSignRole: m["child_sign_role"], SignedBy: m["signed_by"],
	}
}

func valuesOf(g validation.GuestRow) map[string]string {
	return map[string]string{
		"surname": g.Surname, "first_name": g.FirstName, "birth_date": g.BirthDate,
		"nationality": g.Nationality, "doc_number": g.DocNumber, "visa_number": g.VisaNumber,
		"res_street": g.ResStreet, "res_city": g.ResCity, "res_country": g.ResCountry,
		"purpose": g.Purpose, "note": g.Note,
	}
}

func TestNormaliseGuestMatchesPython(t *testing.T) {
	today, cases := loadGolden(t)
	for _, c := range cases {
		t.Run(c.Name, func(t *testing.T) {
			raw := validation.GuestFormRaw(formOf(c.Form).Fields(), c.DefaultPurpose)
			got := valuesOf(validation.NormaliseGuest(raw, today))
			if !reflect.DeepEqual(got, c.Values) {
				t.Errorf("values\nwant %q\ngot  %q", c.Values, got)
			}
		})
	}
}

func TestCheckNewGuestMatchesPython(t *testing.T) {
	today, cases := loadGolden(t)
	for _, c := range cases {
		t.Run(c.Name, func(t *testing.T) {
			cfg := FormConfig{DefaultPurpose: c.DefaultPurpose, Stays: []Stay{c.Stay}}
			got := []goldenIssue{}
			for _, i := range CheckNewGuest(formOf(c.Form), cfg, c.Stay, today) {
				got = append(got, goldenIssue{i.Field, i.Message, i.Severity})
			}
			want := c.Issues
			if want == nil {
				want = []goldenIssue{}
			}
			if !reflect.DeepEqual(got, want) {
				t.Errorf("issues\nwant %+v\ngot  %+v", want, got)
			}
		})
	}
}
```

<!-- file: App/scripts/guest_form_golden.py -->
```python
"""Write go/internal/guestcontract/testdata/guest_form_golden.json from the real Python.

Brief 1835. Run from App/ (no database needed):

    .venv/bin/python scripts/guest_form_golden.py

For each made-up case it runs the database-free part of the guest save route
(App/app/routes/guest.py guest_form_save, a new guest): guest_form_raw,
normalise_guest(clamp=False), validate_guest, validate_stay_dates,
validate_stay_date_text, the party-size check, guest_signature_issue with the
English catalog and allow_imported=False, and the legal_ack check. The Go test
in go/internal/guestcontract/ compares the normalised values and the issues.
The clock is pinned to 2026-11-01, as in scripts/validation_golden.py.
"""

from __future__ import annotations

import base64
import io
import json
import sys
from datetime import date
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from PIL import Image  # noqa: E402

from app import i18n, reporting, validation  # noqa: E402
from app.routes import admin_helpers  # noqa: E402

OUT = APP.parent / "go" / "internal" / "guestcontract" / "testdata" / "guest_form_golden.json"


class PinnedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 11, 1)


validation.date = PinnedDate  # the only clock read in validation.py


def _png_data_url() -> str:
    buf = io.BytesIO()
    Image.new("L", (40, 20), 255).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


SIG = _png_data_url()
STAY = {"reservation_id": 1, "date_from": "2026-11-10", "date_to": "2026-11-12",
        "expected_guests": 2, "registered_guests": 0}
ADULT = {
    "surname": "Novák", "first_name": "Jan", "birth_date": "01.02.1990",
    "nationality": "DEU", "doc_number": "C01X00T47", "res_street": "Hauptstraße 5",
    "res_city": "Berlin", "res_country": "DEU", "signature": SIG, "legal_ack": "1",
}


def case(name, changes=None, stay=None, default_purpose="10"):
    form = dict(ADULT)
    for key, value in (changes or {}).items():
        if value is None:
            form.pop(key, None)
        else:
            form[key] = value
    return {"name": name, "form": form, "stay": {**STAY, **(stay or {})},
            "default_purpose": default_purpose}


CASES = [
    case("valid adult"),
    case("diacritics fold", {"surname": "nguyễn văn", "first_name": "  øyvind  ærø "}),
    case("eszett upper", {"surname": "straße"}),
    case("pipe and newline", {"surname": "Smith|Jones\nBrown", "note": "a|b\r\nc"}),
    case("empty surname", {"surname": ""}),
    case("cyrillic surname", {"surname": "Иванов"}),
    case("surname too long", {"surname": "A" * 60}),
    case("first name too long", {"first_name": "B" * 30}),
    case("birth slashes two digit year", {"birth_date": "01/02/90"}),
    case("birth six digits", {"birth_date": "010224"}),
    case("birth eight digits", {"birth_date": "01021990"}),
    case("birth arabic indic digits", {"birth_date": "٠١٠٢١٩٩٠"}),
    case("birth unknown day and month", {"birth_date": "0.0.1990"}),
    case("birth long day", {"birth_date": "123.4.1990"}),
    case("birth in future", {"birth_date": "01.01.2030"}),
    case("birth missing", {"birth_date": ""}),
    case("doc with spaces", {"doc_number": "ab 12 34 56"}),
    case("doc too short", {"doc_number": "AB1"}),
    case("inpass child with parent doc", {"doc_number": "INPASS", "parent_doc_number": "c01 x00", "birth_date": "01.01.2020", "signature": ""}),
    case("child under 15 no signature", {"birth_date": "05.05.2015", "signature": ""}),
    case("signature imported", {"signature": "imported"}),
    case("signature missing", {"signature": ""}),
    case("signature bad", {"signature": "data:image/png;base64,AAAA"}),
    case("legal ack missing", {"legal_ack": None}),
    case("party size asked and missing", stay={"expected_guests": None}),
    case("party size asked and given", {"party_size": " 3 "}, stay={"expected_guests": None}),
    case("party size too big", {"party_size": "61"}, stay={"expected_guests": None}),
    case("party size not a number", {"party_size": "abc"}, stay={"expected_guests": None}),
    case("residence dash", {"res_city": "Praha–Řepy", "res_country": "cze", "nationality": "deu "}),
    case("czech national", {"nationality": "CZE", "doc_number": "", "res_street": "", "res_city": "", "res_country": ""}),
    case("empty purpose takes default", {"purpose": ""}, default_purpose="10"),
    case("empty purpose no default", {"purpose": ""}, default_purpose=""),
    case("purpose given", {"purpose": "01"}),
    case("unknown nationality", {"nationality": "XXX"}),
    case("visa given", {"visa_number": "v 123 456"}),
    case("stay date unreadable", stay={"date_from": "2026-13-01"}),
    case("everything empty", {k: "" for k in ADULT}),
]


def run(c):
    form = c["form"]
    apartment = {"default_purpose": c["default_purpose"]}
    stay = c["stay"]
    raw = admin_helpers.guest_form_raw(form, apartment)
    values = validation.normalise_guest(raw, clamp=False)
    stay_from, stay_to = stay["date_from"], stay["date_to"]
    signature = admin_helpers.kept_signature(form.get("signature"), None)
    child = validation.certainly_under_age(
        values["birth_date"], validation.parse_iso_date(stay_from), reporting.UNDER_SIGN_AGE
    )
    if child:
        signature = ""
    issues = validation.validate_guest(
        values, validation.parse_iso_date(stay_from), validation.parse_iso_date(stay_to), raw=raw
    )
    issues.extend(validation.validate_stay_dates(
        validation.parse_iso_date(stay_from), validation.parse_iso_date(stay_to),
        validation.parse_iso_date(stay_from), validation.parse_iso_date(stay_to),
    ))
    issues.extend(validation.validate_stay_date_text(stay_from, stay_to))
    translate = i18n.translator("en")
    if stay["expected_guests"] is None:
        try:
            party_size = int((form.get("party_size") or "").strip())
        except ValueError:
            party_size = 0
        if party_size < 1 or party_size > 60:
            issues.append(validation.Issue("party_size", translate("error_party_size")))
    sig = reporting.guest_signature_issue(signature, translate, allow_imported=False, under_15=child)
    if sig:
        issues.append(sig)
    if not form.get("legal_ack"):
        issues.append(validation.Issue("legal_ack", translate("legal_ack_missing")))
    return {
        "name": c["name"], "form": form, "stay": stay, "default_purpose": c["default_purpose"],
        "values": values,
        "issues": [{"field": i.field, "message": i.message, "severity": i.severity} for i in issues],
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = {"today": "2026-11-01", "cases": [run(c) for c in CASES]}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(CASES)} cases)")


if __name__ == "__main__":
    main()
```

## 5. Do not touch

`go/internal/validation/validation.go` and every other existing file in `go/internal/validation/` and `go/internal/secure/`; `App/app/` (the Python checks are the reference, never changed here); `go/go.mod` and `go/go.sum` (no new dependency: `golang.org/x/text/unicode/norm` is already a module dependency); `App/migrations_pg/`. Rules 1, 4, 11.

## 6. Commands

From `go/`:
- `go test ./internal/guestcontract/... ./internal/validation/... 2>&1 | tail -30`. Expected: two `ok` lines.

From `App/`:
- `sha256sum ../go/internal/guestcontract/testdata/guest_form_golden.json && .venv/bin/python scripts/guest_form_golden.py >/dev/null && sha256sum ../go/internal/guestcontract/testdata/guest_form_golden.json`. Expected: the two hashes are equal (the golden is deterministic).

From the repo root:
- `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: `context lint: OK`.

## 7. Acceptance

- [ ] Eight files written by the step 1 command, the golden by the script.
- [ ] `gofmt -l` and `go vet` print nothing.
- [ ] `go test ./internal/guestcontract/... ./internal/validation/...`: two `ok`.
- [ ] `git diff --stat` shows no change to an existing file.
- [ ] `git diff --quiet go/go.mod go/go.sum && echo unchanged` prints `unchanged` (no dependency added).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found, or step 1 does not write exactly 8 files;
- the golden script fails to import the app;
- a golden test fails (report the cases; never edit the golden or the Go code to pass);
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1835-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat` and `git status --short`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/validation/guest_form.go`: each function against its Python twin in `App/app/validation.py` (lines 275-460, 587-614, 747-790) and `App/app/reporting.py` `guest_signature_issue`; the golden covers 37 cases (folding, ß, MRZ letters, pipes, Cyrillic, lengths, birth-date forms including Arabic-Indic digits and 2-digit years, INPASS, children, signatures, party size, purpose default, unreadable stay date).
- `go/internal/guestcontract/check.go`: order of issues equals the route's; excluded checks are listed; known party-size difference ("1_0", non-ASCII digits).
- `go/internal/guestcontract/payload.go`: gzip then Fernet with the data keys (D4), size cap before and after, version refused both ways.
- `go/internal/guestcontract/types.go`: JSON names are the contract v1 surface; a rename later is a contract change (two releases, plan rule 5).
- `App/scripts/guest_form_golden.py`: calls the real `guest_form_raw`, `kept_signature`, `normalise_guest`, `validate_guest`, `guest_signature_issue`; nothing re-implemented.
- Verified by the brief writer in a scratch copy of `go/` on Go 1.26.0: `go vet`, `gofmt -l` clean, both packages `ok` with the golden generated from the real Python.

## Owner steps

None. This brief adds code that nothing calls yet.
