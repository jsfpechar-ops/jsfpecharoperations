package ubyport

// Go port of App/app/ubyport/errors.py (code book and classification). The
// Python oracle in App/tests/golden/ubyport/responses/expected.json is the
// contract.

import (
	"strings"
	"unicode"
	"unicode/utf8"
)

// KnownCodes mirrors errors.KNOWN_CODES.
var KnownCodes = map[string]string{
	"1":   "Incorrect file extension",
	"106": "Invalid value in a guest field",
	"112": "Reported after the deadline - the record was accepted",
	"150": "Duplicate record - the register already holds it",
}

// KnownSeverity mirrors errors.KNOWN_SEVERITY.
var KnownSeverity = map[string]int{"1": 0, "112": 0, "150": 4}

// AcceptedMaxSeverity mirrors errors.ACCEPTED_MAX_SEVERITY.
const AcceptedMaxSeverity = 2

// FallbackText mirrors errors.FALLBACK_TEXT.
var FallbackText = map[string]string{
	"en": "UbyPort error %(code)s — refresh code lists on the property page to see the explanation.",
	"cs": "Chyba UbyPortu %(code)s — vysvětlení uvidíte po obnovení číselníků na stránce ubytování.",
}

// NormaliseCode mirrors errors.normalise_code: "ERR_CZE_112", "0112" and "112" give "112".
func NormaliseCode(code string) string {
	bare := pyStrip(code)
	if len(bare) >= 8 && strings.EqualFold(bare[:8], "ERR_CZE_") {
		bare = bare[8:]
	}
	if trimmed := strings.TrimLeft(bare, "0"); trimmed != "" {
		return trimmed
	}
	if bare != "" {
		return "0"
	}
	return ""
}

// SplitCodes mirrors errors.split_codes: "5;6;7;" gives ["5", "6", "7"].
func SplitCodes(raw *string) []string {
	out := []string{}
	if raw == nil || *raw == "" {
		return out
	}
	for _, part := range strings.Split(*raw, ";") {
		if p := pyStrip(part); p != "" {
			out = append(out, p)
		}
	}
	return out
}

// zfill3 mirrors Python str.zfill(3), sign aware and rune counted.
func zfill3(code string) string {
	n := utf8.RuneCountInString(code)
	if n >= 3 {
		return code
	}
	sign, body := "", code
	if strings.HasPrefix(code, "+") || strings.HasPrefix(code, "-") {
		sign, body = code[:1], code[1:]
	}
	return sign + strings.Repeat("0", 3-n) + body
}

// Describe mirrors errors.describe.
func Describe(code string, codebook map[string]string, lang string) string {
	padded := zfill3(code)
	for _, key := range []string{code, padded, "ERR_CZE_" + padded} {
		if text := codebook[key]; text != "" {
			return text
		}
	}
	if text, ok := KnownCodes[code]; ok {
		return text
	}
	tmpl, ok := FallbackText[lang]
	if !ok {
		tmpl = FallbackText["en"]
	}
	return strings.ReplaceAll(tmpl, "%(code)s", code)
}

// Severity mirrors errors.severity: nil when nobody has told us.
func Severity(code string, severities map[string]int) *int {
	key := NormaliseCode(code)
	if v, ok := severities[key]; ok {
		return &v
	}
	if v, ok := KnownSeverity[key]; ok {
		return &v
	}
	return nil
}

// IsAcceptedCode mirrors errors.is_accepted_code.
func IsAcceptedCode(code string, severities map[string]int) bool {
	v := Severity(code, severities)
	return v != nil && *v <= AcceptedMaxSeverity
}

func isWordRune(r rune) bool {
	return unicode.IsLetter(r) || unicode.IsNumber(r) || r == '_'
}

// hasWord reports whether word occurs in s with a non-word rune (or the start)
// before it, and, when wholeEnd is set, a non-word rune (or the end) after it.
// It stands in for the Python \b regex, which Go RE2 does not match for Unicode.
func hasWord(s, word string, wholeEnd bool) bool {
	for i := 0; ; {
		j := strings.Index(s[i:], word)
		if j < 0 {
			return false
		}
		start := i + j
		end := start + len(word)
		leftOK := true
		if start > 0 {
			r, _ := utf8.DecodeLastRuneInString(s[:start])
			leftOK = !isWordRune(r)
		}
		rightOK := true
		if wholeEnd && end < len(s) {
			r, _ := utf8.DecodeRuneInString(s[end:])
			rightOK = !isWordRune(r)
		}
		if leftOK && rightOK {
			return true
		}
		i = start + 1
	}
}

// IsNonCorrectable mirrors errors.is_non_correctable (_NON_CORRECTABLE_RE).
func IsNonCorrectable(text string) bool {
	lowered := strings.ToLower(text)
	return strings.Contains(lowered, "duplic") ||
		hasWord(lowered, "pozdě", true) ||
		hasWord(lowered, "pozdn", false) ||
		hasWord(lowered, "late", true)
}

// IsDuplicate mirrors errors.is_duplicate.
func IsDuplicate(text string) bool {
	lowered := strings.ToLower(text)
	return strings.Contains(lowered, "duplic") || strings.HasPrefix(lowered, "150:")
}

// IsDuplicateCode mirrors errors.is_duplicate_code.
func IsDuplicateCode(code string, codebook map[string]string) bool {
	key := NormaliseCode(code)
	if key == "150" {
		return true
	}
	if len(codebook) == 0 {
		return false
	}
	padded := zfill3(key)
	for _, candidate := range []string{key, padded, "ERR_CZE_" + padded} {
		if text := codebook[candidate]; text != "" {
			return strings.HasPrefix(strings.ToLower(pyStrip(text)), "duplic")
		}
	}
	return false
}

// RecordIsDuplicate mirrors errors.record_is_duplicate.
func RecordIsDuplicate(recordErrors *string, codebook map[string]string) bool {
	for _, code := range SplitCodes(recordErrors) {
		if IsDuplicateCode(code, codebook) {
			return true
		}
	}
	return false
}

// Classify mirrors errors.classify: it returns the state and the messages.
func Classify(headerErrors, recordErrors *string, codebook map[string]string, lang string, severities map[string]int) (string, []string) {
	messages := []string{}
	codes := append(SplitCodes(headerErrors), SplitCodes(recordErrors)...)
	if len(codes) == 0 {
		return "accepted", messages
	}
	refused, nonCorrectable := false, false
	for _, code := range codes {
		text := Describe(code, codebook, "en")
		shown := text
		if lang != "en" {
			shown = Describe(code, codebook, lang)
		}
		messages = append(messages, code+": "+shown)
		if IsAcceptedCode(code, severities) {
			continue
		}
		refused = true
		if NormaliseCode(code) == "150" || IsNonCorrectable(text) {
			nonCorrectable = true
		}
	}
	if !refused {
		return "accepted", messages
	}
	if nonCorrectable {
		return "not_correctable", messages
	}
	return "error", messages
}
