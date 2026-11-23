package guideimport

import (
	"regexp"
	"strings"
	"unicode"
)

// CodeKeywords lists access and password trigger words (exported for brief 2037).
var CodeKeywords = []string{
	"code", "kod", "kody",
	"pin",
	"door", "dvere", "dveri",
	"brana", "brany",
	"gate",
	"garaz", "garaze", "garage",
	"tor", "tur", "turcode",
	"zugangscode", "zugang", "eingang",
	"wifi", "wi-fi", "wlan",
	"keypad", "klavesnice",
	"domovni", "vchod", "entrance",
	"lock", "zamek", "schloss",
	"box", "keybox", "klicovnik",
	"heslo", "hesla",
	"password", "passwort", "kennwort", "passcode", "psk",
}

var kwWords = []string{
	"code", "kod", "kody",
	"pin",
	"door", "dvere", "dveri",
	"brana", "brany",
	"gate",
	"garaz", "garaze", "garage",
	"tor", "tur", "turcode",
	"zugangscode", "zugang", "eingang",
	"wifi", "wi-fi", "wlan",
	"keypad", "klavesnice",
	"domovni", "vchod", "entrance",
	"lock", "zamek", "schloss",
	"box", "keybox", "klicovnik",
}

var pwWords = []string{
	"heslo", "hesla",
	"password", "passwort", "kennwort", "passcode", "psk",
}

var foldReplacer = strings.NewReplacer(
	"á", "a", "é", "e", "ě", "e", "í", "i", "ó", "o", "ú", "u", "ů", "u", "ý", "y",
	"č", "c", "ď", "d", "ň", "n", "ř", "r", "š", "s", "ť", "t", "ž", "z",
	"ä", "a", "ö", "o", "ü", "u", "ß", "ss",
	"Á", "a", "É", "e", "Ě", "e", "Í", "i", "Ó", "o", "Ú", "u", "Ů", "u", "Ý", "y",
	"Č", "c", "Ď", "d", "Ň", "n", "Ř", "r", "Š", "s", "Ť", "t", "Ž", "z",
	"Ä", "a", "Ö", "o", "Ü", "u",
)

type span struct{ start, end int }

func foldRunes(text string) (orig, folded []rune) {
	orig = []rune(text)
	folded = make([]rune, len(orig))
	for i, r := range orig {
		s := foldReplacer.Replace(string(r))
		rs := []rune(s)
		if len(rs) == 0 {
			folded[i] = unicode.ToLower(r)
		} else if len(rs) == 1 {
			folded[i] = rs[0]
		} else {
			folded[i] = 's'
		}
	}
	for i, r := range folded {
		if r >= 'A' && r <= 'Z' {
			folded[i] = r + ('a' - 'A')
		}
	}
	return orig, folded
}

func foldedString(folded []rune) string {
	var b strings.Builder
	b.Grow(len(folded))
	for _, r := range folded {
		b.WriteRune(r)
	}
	return b.String()
}

func wordAt(folded []rune, start, end int) string {
	if start < 0 || end > len(folded) || start >= end {
		return ""
	}
	return string(folded[start:end])
}

func lineEnd(folded []rune, from int) int {
	for i := from; i < len(folded); i++ {
		if folded[i] == '\n' {
			return i
		}
	}
	return len(folded)
}

func mergeSpans(spans []span) []span {
	if len(spans) == 0 {
		return nil
	}
	sorted := append([]span(nil), spans...)
	for i := 1; i < len(sorted); i++ {
		for j := i; j > 0 && sorted[j-1].start > sorted[j].start; j-- {
			sorted[j-1], sorted[j] = sorted[j], sorted[j-1]
		}
	}
	var out []span
	cur := sorted[0]
	for i := 1; i < len(sorted); i++ {
		if sorted[i].start <= cur.end {
			if sorted[i].end > cur.end {
				cur.end = sorted[i].end
			}
		} else {
			out = append(out, cur)
			cur = sorted[i]
		}
	}
	return append(out, cur)
}

var digitRunRe = regexp.MustCompile(`\d(?:[ -]?\d){3,7}`)

func postalGuardBefore(folded []rune, kwStart int) bool {
	from := kwStart - 20
	if from < 0 {
		from = 0
	}
	window := strings.ToLower(wordAt(folded, from, kwStart))
	for _, p := range []string{"postal", "postovni", "zip", "psc"} {
		if strings.Contains(window, p) {
			return true
		}
	}
	return false
}

func hasDigitGuard(folded []rune, start, end int, keyword string) bool {
	text := foldedString(folded)

	if start > 0 {
		prev := text[start-1]
		if prev >= '0' && prev <= '9' || prev == ':' || prev == '.' || prev == '/' || prev == '+' {
			return true
		}
		if prev == ',' && end < len(text) && text[end] >= '0' && text[end] <= '9' {
			return true
		}
	}
	if end < len(text) {
		next := text[end]
		if next >= '0' && next <= '9' || next == ':' || next == '/' {
			return true
		}
	}

	plain := strings.ReplaceAll(strings.ReplaceAll(strings.TrimSpace(text[start:end]), " ", ""), "-", "")
	if len(plain) == 4 && plain >= "1900" && plain <= "2099" {
		kw := strings.ToLower(keyword)
		if kw == "code" || kw == "kod" {
			rest := strings.TrimSpace(text[end:])
			for _, nw := range []string{"compliance", "of", "civil", "zakon", "zakonik"} {
				if strings.HasPrefix(rest, nw) || strings.HasPrefix(rest, nw+" ") {
					return true
				}
			}
		}
	}

	after := strings.ToLower(text[end:])
	for _, unit := range []string{"kc", "czk", "eur", "€", "$", "usd", "%", "m2", "m²", "km", "kg", "min", "h", "uhr"} {
		if strings.HasPrefix(after, unit) || strings.HasPrefix(after, " "+unit) {
			return true
		}
	}
	if start > 0 {
		before := text[:start]
		for _, unit := range []string{"€", "$"} {
			if strings.HasSuffix(before, unit) {
				return true
			}
		}
	}
	return false
}

func ruleAMatches(folded []rune) []span {
	var out []span
	text := foldedString(folded)
	for _, keyword := range append(append([]string{}, kwWords...), pwWords...) {
		re := regexp.MustCompile(`(?i)\b` + regexp.QuoteMeta(keyword) + `\b`)
		for _, kwIdx := range re.FindAllStringIndex(text, -1) {
			if postalGuardBefore(folded, kwIdx[0]) {
				continue
			}
			kwEnd := kwIdx[1]
			searchEnd := kwEnd + 40
			if le := lineEnd(folded, kwEnd); searchEnd > le {
				searchEnd = le
			}
			segment := text[kwEnd:searchEnd]
			for _, m := range digitRunRe.FindAllStringIndex(segment, -1) {
				if strings.ContainsAny(segment[:m[0]], ".!?") {
					continue
				}
				ds := kwEnd + m[0]
				de := kwEnd + m[1]
				if !hasDigitGuard(folded, ds, de, keyword) {
					out = append(out, span{ds, de})
				}
			}
		}
	}
	return out
}

func ruleBMatches(folded []rune) []span {
	var out []span
	text := foldedString(folded)
	for _, m := range digitRunRe.FindAllStringIndex(text, -1) {
		ds, de := m[0], m[1]
		searchEnd := de + 40
		if le := lineEnd(folded, de); searchEnd > le {
			searchEnd = le
		}
		segment := text[de:searchEnd]
		var matchedKW string
		for _, keyword := range append(append([]string{}, kwWords...), pwWords...) {
			kre := regexp.MustCompile(`(?i)\b` + regexp.QuoteMeta(keyword) + `\b`)
			km := kre.FindStringIndex(segment)
			if km == nil {
				continue
			}
			if strings.ContainsAny(segment[:km[0]], ".!?") {
				continue
			}
			matchedKW = keyword
			break
		}
		if matchedKW == "" {
			continue
		}
		if !hasDigitGuard(folded, ds, de, matchedKW) {
			out = append(out, span{ds, de})
		}
	}
	return out
}

func ruleCMatches(folded []rune) []span {
	text := foldedString(folded)
	var out []span
	for _, pat := range []string{`\*\d{2,8}#`, `\d{3,8}[#*]`, `[#*]\d{3,8}`} {
		re := regexp.MustCompile(pat)
		for _, m := range re.FindAllStringIndex(text, -1) {
			out = append(out, span{m[0], m[1]})
		}
	}
	return out
}

var sepRe = regexp.MustCompile(`(?i)[:=]|(?:\b)(?:is|je|ist|lautet|byl)(?:\b)`)

func ruleDMatches(folded []rune) []span {
	text := foldedString(folded)
	var out []span
	for _, pwWord := range pwWords {
		pwRe := regexp.MustCompile(`(?i)\b` + regexp.QuoteMeta(pwWord) + `\b`)
		for _, pwIdx := range pwRe.FindAllStringIndex(text, -1) {
			pwEnd := pwIdx[1]
			searchEnd := pwEnd + 50
			if le := lineEnd(folded, pwEnd); searchEnd > le {
				searchEnd = le
			}
			searchText := text[pwEnd:searchEnd]
			sep := sepRe.FindStringIndex(searchText)
			if sep == nil {
				continue
			}
			tokenStart := pwEnd + sep[1]
			for tokenStart < len(text) && (text[tokenStart] == ' ' || text[tokenStart] == '\t') {
				tokenStart++
			}
			if tokenStart < len(text) && (text[tokenStart] == '"' || text[tokenStart] == '\'' || text[tokenStart] == '`') {
				tokenStart++
			}
			tokenEnd := tokenStart
			for tokenEnd < len(text) && tokenEnd-tokenStart < 64 {
				c := text[tokenEnd]
				if c == ' ' || c == ',' || c == ';' || c == '"' || c == '\'' || c == '(' || c == ')' {
					break
				}
				tokenEnd++
			}
			if tokenEnd-tokenStart >= 4 && tokenEnd-tokenStart <= 64 {
				out = append(out, span{tokenStart, tokenEnd})
			}
		}
	}
	return out
}

func AsksForCode(text string) bool {
	_, folded := foldRunes(text)
	s := foldedString(folded)
	for _, keyword := range CodeKeywords {
		re := regexp.MustCompile(`(?i)\b` + regexp.QuoteMeta(keyword) + `\b`)
		if re.MatchString(s) {
			return true
		}
	}
	return false
}

func FilterCodes(text string) (string, int) {
	if text == "" {
		return "", 0
	}
	orig, folded := foldRunes(text)
	var all []span
	all = append(all, ruleAMatches(folded)...)
	all = append(all, ruleBMatches(folded)...)
	all = append(all, ruleCMatches(folded)...)
	all = append(all, ruleDMatches(folded)...)

	merged := mergeSpans(all)
	if len(merged) == 0 {
		return text, 0
	}

	replacement := []rune("[left out]")
	var result []rune
	last := 0
	for _, s := range merged {
		result = append(result, orig[last:s.start]...)
		result = append(result, replacement...)
		last = s.end
	}
	result = append(result, orig[last:]...)
	return string(result), len(merged)
}

func FilterCardFields(card map[string]any) int {
	total := 0
	for _, field := range []string{"title", "location", "steps", "watch_out"} {
		if val, ok := card[field].(string); ok {
			clean, n := FilterCodes(val)
			card[field] = clean
			total += n
		}
	}
	return total
}
