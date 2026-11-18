package policyletter

import (
	"regexp"
	"sort"
	"strings"
	"unicode"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"golang.org/x/text/transform"
	"golang.org/x/text/unicode/norm"
)

const maxSource = 120
const maxFacility = 35

var (
	missingField = FieldResult{State: "missing"}

	gapSame = `[ \t]*(?:[:\-–][ \t]*)?`
	gapNext = `[ \t]*:[ \t]*\n[ \t]*`
	endPat  = `(?:[ \t]*(?:[.,;][ \t]*)?)(?:\n|$)`

	nfcKeepRE = regexp.MustCompile(`([;`K])`)
	proseRE   = regexp.MustCompile(`[ \t]*[.,;!?…]`)

	wsUserLabelRE = regexp.MustCompile(`(?i)p[rř][ií]hla[sš]ovac[ií]\s+jm[eé]no`)
	idubTailRE    = regexp.MustCompile(`(?i)(?:` + gapNext + `|` + gapSame + `)([0-9]{12,14})` + endPat)
	wsUserTailRE  = regexp.MustCompile(`(?i)(?:` + gapNext + `|` + gapSame + `)(uby-t?ws_?[A-Za-z0-9]{5,6})` + endPat)

	digitRunRE      = regexp.MustCompile(`[0-9]+`)
	digitChainRE    = regexp.MustCompile(`[0-9]+(?:(?:[ \t]*[-–.,/_][ \t]*|[ \t]+)[0-9]+)*`)
	chainSepRE      = regexp.MustCompile(`[-–.,/_ \t]+`)
	dsBarcodeRE     = regexp.MustCompile(`^[0-9]{3}\.[0-9]{4}\.[0-9]{7}$`)
	loginTokenRE    = regexp.MustCompile(`(?i)uby[ \t]*[-‐‑‒–—−][ \t]*t?ws[_A-Za-z0-9]*`)
	labelPrefixRE   = regexp.MustCompile(`^[ \t|_>•*\-]*$`)
	passwordWordRE  = regexp.MustCompile(`(?i)hesl|password|passwort`)
	wordRE          = regexp.MustCompile(`[\p{L}\p{N}_]+`)
	leadingNoiseRE  = regexp.MustCompile(`^[^\p{L}\p{N}_]+`)
	trailingNoiseRE = regexp.MustCompile(`[^\p{L}\p{N}_]+$`)
	pwLabelRE       = regexp.MustCompile(`(?i)(?:p[rř][ií]stupov[eé][ \t]+heslo|\bheslo\b|\bpassword\b)[ \t]*:`)
	pwValueRE       = regexp.MustCompile(`[ \t]*(?:\n[ \t]*)?([!-~]{6,64})[ \t]*(?:\n|$)`)
	idubShapeRE     = regexp.MustCompile(`^[0-9]{12,14}$`)
	facilityLabelRE = regexp.MustCompile(`(?im)^[ \t]*Ubytovac[ií][ \t]+za[rř][ií]zen[ií][ \t]*:`)
	wsUserShapeRE   = regexp.MustCompile(`(?i)^(?:uby-ws[A-Za-z0-9]{6}|uby-ws_[A-Za-z0-9]{5,6}|uby-tws[A-Za-z0-9]{5})$`)
	idubLabelBodyRE = regexp.MustCompile(`(?i)IDUB`)
)

const (
	softHyphen = "\u00ad"
	markWord   = "zkratk"
)

var spaceTranslate = strings.NewReplacer(
	"\u00a0", " ",
	"\u202f", " ",
	"\u2009", " ",
	"\t", " ",
)

// ParseLetter reads IDUB, login, password and facility; derives the short name.
func ParseLetter(text string) LetterResult {
	if text == "" || strings.TrimSpace(text) == "" {
		return LetterResult{Status: "empty", Fields: allMissing()}
	}
	if len(text) > MaxLetterChars {
		return LetterResult{Status: "too_long", Fields: allMissing()}
	}

	normalised := normalise(text)
	starts := lineStarts(normalised)
	lines := strings.Split(normalised, "\n")
	fields := allMissing()
	for name := range patterns {
		fields[name] = parseField(name, normalised, starts, lines)
	}

	user := fields["uby_ws_user"]
	if user.State == "found" {
		derived := validation.MarkFromWSUser(user.Value)
		if derived != "" && isASCII(derived) {
			conflictLines := markConflicts(lines, derived)
			if len(conflictLines) > 0 {
				both := sortedUniqueInts(append([]int{user.Line}, conflictLines...))
				conflict := FieldResult{State: "conflict", Lines: both}
				fields["uby_ws_user"] = conflict
				fields["uby_mark"] = conflict
			} else {
				fields["uby_mark"] = FieldResult{
					State:  "derived",
					Value:  derived,
					Line:   user.Line,
					Label:  user.Label,
					Lines:  user.Lines,
					Source: user.Source,
				}
			}
		}
	}
	return LetterResult{
		Status:   "ok",
		Fields:   fields,
		Password: parsePassword(normalised, starts, fields),
		Facility: parseFacility(normalised, starts, lines),
	}
}

var patterns = map[string]bool{
	"uby_idub":    true,
	"uby_ws_user": true,
}

func allMissing() map[string]FieldResult {
	out := make(map[string]FieldResult, len(Fields))
	for _, name := range Fields {
		out[name] = missingField
	}
	return out
}

func normalise(text string) string {
	var b strings.Builder
	last := 0
	for _, loc := range nfcKeepRE.FindAllStringSubmatchIndex(text, -1) {
		b.WriteString(norm.NFC.String(text[last:loc[0]]))
		b.WriteString(text[loc[2]:loc[3]])
		last = loc[1]
	}
	b.WriteString(norm.NFC.String(text[last:]))
	text = b.String()
	text = strings.ReplaceAll(text, "\r\n", "\n")
	text = strings.ReplaceAll(text, "\r", "\n")
	return spaceTranslate.Replace(text)
}

func lineStarts(text string) []int {
	starts := []int{0}
	for i := 0; i < len(text); i++ {
		if text[i] == '\n' {
			starts = append(starts, i+1)
		}
	}
	return starts
}

func lineOf(starts []int, pos int) int {
	return sort.Search(len(starts), func(i int) bool { return starts[i] > pos })
}

func lineAt(lines []string, number int) string {
	if number < 1 || number > len(lines) {
		return ""
	}
	return lines[number-1]
}

func plain(line string) string {
	t := transform.Chain(norm.NFD, transform.RemoveFunc(func(r rune) bool {
		return unicode.Is(unicode.Mn, r)
	}))
	out, _, _ := transform.String(t, line)
	return strings.ToLower(out)
}

func hasPasswordWord(line string) bool {
	return passwordWordRE.MatchString(plain(line))
}

func isASCIIAlphaNum(b byte) bool {
	return (b >= 'A' && b <= 'Z') || (b >= 'a' && b <= 'z') || (b >= '0' && b <= '9')
}

type labelHit struct {
	start, end int
	label      string
}

func findIDUBLabels(text string) []labelHit {
	var out []labelHit
	for _, loc := range idubLabelBodyRE.FindAllStringIndex(text, -1) {
		if loc[0] > 0 && isASCIIAlphaNum(text[loc[0]-1]) {
			continue
		}
		if loc[1] < len(text) && isASCIIAlphaNum(text[loc[1]]) {
			continue
		}
		out = append(out, labelHit{loc[0], loc[1], text[loc[0]:loc[1]]})
	}
	return out
}

func findWSUserLabels(text string) []labelHit {
	var out []labelHit
	for _, loc := range wsUserLabelRE.FindAllStringIndex(text, -1) {
		out = append(out, labelHit{loc[0], loc[1], text[loc[0]:loc[1]]})
	}
	return out
}
