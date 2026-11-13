package guideimport

// The pure half of App/app/guest_guide_merge.py: text helpers, the prompt,
// verify and clean. No database here. testdata/golden.json pins every
// function against the Python output.

import (
	_ "embed"
	"encoding/json"
	"regexp"
	"strings"
	"unicode"
	"unicode/utf8"

	"golang.org/x/text/cases"
	"golang.org/x/text/unicode/norm"
)

// Feature is the ai_usage feature name of the merge.
const Feature = "guide_import"

const (
	maxCards      = 12
	maxQuotes     = 4
	minQuoteChars = 10
	maxQuoteChars = 300
	// MaxAttempts is the number of model failures per import before it is marked failed.
	MaxAttempts = 3
)

// systemRulesFile is SYSTEM_RULES, written by guide_import_golden.py and
// compared with Python's own string in the tests.
//
//go:embed system_rules.txt
var systemRulesFile string

// SchemaJSON is SCHEMA as compact JSON; the tests compare it with Python's SCHEMA.
//
//go:embed schema.json
var schemaFile []byte

// SystemRules returns the system prompt, byte for byte (the file's final newline removed).
func SystemRules() string { return strings.TrimSuffix(systemRulesFile, "\n") }

// Schema returns the JSON schema of the model answer.
func Schema() json.RawMessage {
	var v any
	if err := json.Unmarshal(schemaFile, &v); err != nil {
		panic("schema.json is not JSON")
	}
	b, _ := json.Marshal(v)
	return b
}

var platform = map[string]string{"booking": "Booking.com", "airbnb": "Airbnb"}

var langLine = map[string]string{"cs": "Write the cards in Czech.", "en": "Write the cards in English."}

// fieldOrder is _FIELD_ORDER: the stored fields in reading order.
var fieldOrder = []string{
	"name", "title", "propertyType", "roomType", "address", "checkIn", "checkOut",
	"description", "subDescription", "houseRules", "amenities", "highlights", "locationDescriptions",
}

// Python's \s, \w and \d are Unicode aware; RE2's are ASCII. These classes
// spell the Python meaning.
const (
	reSpace = `\t\n\v\f\r \x{1c}-\x{1f}\x{85}\x{a0}\x{1680}\x{2000}-\x{200a}\x{2028}\x{2029}\x{202f}\x{205f}\x{3000}`
	reWord  = `\p{L}\p{N}_`
)

var (
	reNumber  = regexp.MustCompile(`\p{Nd}+(?:[.,:/-]\p{Nd}+)*`)
	reURL     = regexp.MustCompile(`(?i)https?://|www\.|[` + reWord + `.+-]+@[` + reWord + `-]+\.[a-z]{2,}|\+?\p{Nd}[\p{Nd}` + reSpace + `().-]{7,}\p{Nd}`)
	reNonWord = regexp.MustCompile(`[^` + reWord + `]+`)
)

const czechLetters = "ěščřžýáíéúůďťňĚŠČŘŽÝÁÍÉÚŮĎŤŇ"

func isWord(r rune) bool { return unicode.IsLetter(r) || unicode.IsNumber(r) || r == '_' }

// orStr is str(value or ""): Python's falsy values become the empty string.
func orStr(v any) string {
	if !pyTruthy(v) {
		return ""
	}
	return pyStr(v)
}

// normalise is the comparison form for quotes: NFKC, casefold, every run of
// non-word characters one space, trimmed.
func normalise(text string) string {
	t := cases.Fold().String(norm.NFKC.String(text))
	return pyStrip(reNonWord.ReplaceAllString(t, " "))
}

func normaliseAny(v any) string { return normalise(orStr(v)) }

// listingText is listing_text(): the stored fields in reading order, one per line.
func listingText(data map[string]any) string {
	var lines []string
	for _, key := range fieldOrder {
		switch v := data[key].(type) {
		case []any:
			for _, item := range v {
				if s := pyStr(item); pyStrip(s) != "" {
					lines = append(lines, s)
				}
			}
		case string:
			if s := pyStrip(v); s != "" {
				lines = append(lines, s)
			}
		}
	}
	return strings.Join(lines, "\n")
}

// languageOf is language_of(): "cs" when 1 in 100 letters is a Czech letter.
func languageOf(data map[string]any) string {
	text := listingText(data)
	letters, czech := 0, 0
	for _, r := range text {
		if unicode.IsLetter(r) {
			letters++
		}
		if strings.ContainsRune(czechLetters, r) {
			czech++
		}
	}
	if letters > 0 && czech*100 >= letters {
		return "cs"
	}
	return "en"
}

// Card is an earlier draft (a guide_item row an import wrote).
type Card struct {
	ID                                  int64
	Kind, Topic, Title, Location, Steps string
	WatchOut, Source                    string
}

func earlierText(earlier []Card) string {
	var lines []string
	for _, c := range earlier {
		name, ok := platform[c.Source]
		if !ok {
			name = "earlier"
		}
		head := "[" + name + " draft, kind " + c.Kind + "]"
		body := pyStrip(strings.Join([]string{c.Title, c.Location, c.Steps, c.WatchOut}, " "))
		if body != "" {
			lines = append(lines, head+" "+body)
		}
	}
	return strings.Join(lines, "\n")
}

func userTurn(source string, data map[string]any, earlier []Card, lang string) string {
	text := []string{"Platform: " + platform[source] + ". " + langLine[lang], "", `<listing source="` + source + `">`,
		listingText(data), "</listing>"}
	if len(earlier) > 0 {
		text = append(text, "", "<earlier_drafts>", earlierText(earlier), "</earlier_drafts>")
	}
	text = append(text, "", "Draft the cards now.")
	return strings.Join(text, "\n")
}

func isUpper(r rune) bool { return unicode.IsUpper(r) || unicode.Is(unicode.Other_Uppercase, r) }
func isLower(r rune) bool { return unicode.IsLower(r) || unicode.Is(unicode.Other_Lowercase, r) }

// pyIsLower is str.islower(): at least one cased character and none upper or title case.
func pyIsLower(rs []rune) bool {
	cased := false
	for _, r := range rs {
		if isUpper(r) || unicode.IsTitle(r) {
			return false
		}
		if isLower(r) {
			cased = true
		}
	}
	return cased
}

// names is _names(): capitalised words that do not open a line or a sentence.
// _WORD is \b(\w)(\w{2,})\b, which matches each whole run of three or more
// word characters; the runs are scanned by hand because RE2's \b is ASCII only.
func names(draft string) []string {
	rs := []rune(draft)
	var out []string
	for i := 0; i < len(rs); {
		if !isWord(rs[i]) {
			i++
			continue
		}
		j := i
		for j < len(rs) && isWord(rs[j]) {
			j++
		}
		start := i
		i = j
		if j-start < 3 {
			continue
		}
		before := pyTrimRight(rs[:start])
		if len(before) == 0 || strings.ContainsRune(".!?:\n", before[len(before)-1]) || rs[start-1] == '\n' {
			continue
		}
		if isUpper(rs[start]) && pyIsLower(rs[start+1:j]) {
			out = append(out, string(rs[start:j]))
		}
	}
	return out
}

// verify is verify(): "" when the card may be kept, else the reason it is
// dropped. On success it rewrites the four text fields in card, as Python does.
func verify(card map[string]any, corpus string) string {
	kind, isStr := card["kind"].(string)
	if !isStr {
		return "kind"
	}
	if _, known := kindOrder(kind); kind != "custom" && !known {
		return "kind"
	}
	names4 := []string{"title", "location", "steps", "watch_out"}
	fields := map[string]string{}
	for _, name := range names4 {
		fields[name] = pyStrip(strings.ReplaceAll(orStr(card[name]), "\r\n", "\n"))
	}
	if kind == "custom" {
		topic, _ := card["topic"].(string)
		if !topicOK(topic) || fields["title"] == "" {
			return "topic"
		}
	} else {
		fields["title"] = ""
	}
	if fields["steps"] == "" && fields["location"] == "" {
		return "empty"
	}
	for _, name := range names4 {
		if utf8.RuneCountInString(fields[name]) > Limits[name] {
			return "length"
		}
	}
	quotes, ok := card["quotes"].([]any)
	if !ok || len(quotes) < 1 || len(quotes) > maxQuotes {
		return "quotes"
	}
	var normal []string
	for _, quote := range quotes {
		q := normaliseAny(quote)
		if n := utf8.RuneCountInString(q); n < minQuoteChars || n > maxQuoteChars || !strings.Contains(corpus, q) {
			return "quote"
		}
		normal = append(normal, q)
	}
	quoted := " " + strings.Join(normal, " ") + " "
	var parts []string
	for _, name := range names4 {
		if fields[name] != "" {
			parts = append(parts, fields[name])
		}
	}
	draft := strings.Join(parts, "\n")
	for _, number := range reNumber.FindAllString(draft, -1) {
		if !strings.Contains(quoted, " "+normalise(number)+" ") {
			return "number"
		}
	}
	for _, name := range names(draft) {
		if !strings.Contains(quoted, " "+normalise(name)+" ") {
			return "name"
		}
	}
	for _, contact := range reURL.FindAllString(draft, -1) {
		if !strings.Contains(quoted, normalise(contact)) {
			return "contact"
		}
	}
	for _, name := range names4 {
		card[name] = fields[name]
	}
	return ""
}

// clean is clean(): the verified cards, one per kind (custom: one per title),
// and the drop reasons counted.
func clean(cards []any, corpus string) ([]map[string]any, map[string]int) {
	var kept []map[string]any
	seen := map[[2]string]bool{}
	dropped := map[string]int{}
	if len(cards) > maxCards {
		cards = cards[:maxCards]
	}
	for _, raw := range cards {
		card, ok := raw.(map[string]any)
		if !ok {
			dropped["shape"]++
			continue
		}
		reason := verify(card, corpus)
		if reason == "" {
			ident := [2]string{card["kind"].(string), ""}
			if ident[0] == "custom" {
				ident = [2]string{"custom", normalise(card["title"].(string))}
			}
			if seen[ident] {
				reason = "duplicate"
			}
			seen[ident] = true
		}
		if reason != "" {
			dropped[reason]++
			continue
		}
		kept = append(kept, card)
	}
	return kept, dropped
}

// attempts is _attempts(): the count in "merge:<reason>:<n>", else 0.
func attempts(errText string) int {
	parts := strings.Split(errText, ":")
	if len(parts) != 3 || parts[0] != "merge" || parts[2] == "" {
		return 0
	}
	n := 0
	for _, c := range parts[2] {
		if c < '0' || c > '9' || n > 1<<30 {
			return 0
		}
		n = n*10 + int(c-'0')
	}
	return n
}
