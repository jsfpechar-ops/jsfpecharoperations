package policyletter

import (
	"regexp"
	"sort"
	"strings"
	"unicode"
	"unicode/utf8"
)

func candidates(name, text string) []struct {
	value string
	end   int
} {
	var found []struct {
		value string
		end   int
	}
	if name == "uby_idub" {
		for _, m := range digitChainRE.FindAllStringIndex(text, -1) {
			chain := text[m[0]:m[1]]
			joined := chainSepRE.ReplaceAllString(chain, "")
			if l := len(joined); l < 12 || l > 14 {
				continue
			}
			if dsBarcodeRE.MatchString(chain) {
				continue
			}
			before := strings.TrimRight(text[:m[0]], " \t")
			if len(before) > 0 && before[len(before)-1] == '+' {
				continue
			}
			found = append(found, struct {
				value string
				end   int
			}{chain, m[1]})
		}
		for _, m := range digitRunRE.FindAllStringIndex(text, -1) {
			digits := text[m[0]:m[1]]
			size := len(digits)
			plus := m[0] > 0 && text[m[0]-1] == '+'
			if (size >= 12 && size <= 14) || (plus && size >= 12) {
				found = append(found, struct {
					value string
					end   int
				}{digits, m[1]})
			}
		}
	} else {
		for _, m := range loginTokenRE.FindAllStringIndex(text, -1) {
			found = append(found, struct {
				value string
				end   int
			}{strings.ToUpper(text[m[0]:m[1]]), m[1]})
		}
	}
	return found
}

func wrapped(name, nextLine string) bool {
	rest := leadingNoiseRE.ReplaceAllString(nextLine, "")
	if rest == "" {
		return false
	}
	if name == "uby_idub" && rest[0] >= '0' && rest[0] <= '9' {
		return true
	}
	if name == "uby_ws_user" {
		if loc := wordRE.FindStringIndex(rest); loc != nil {
			word := rest[loc[0]:loc[1]]
			if l := utf8.RuneCountInString(word); l >= 1 && l <= 3 {
				return true
			}
		}
	}
	fragment := trailingNoiseRE.ReplaceAllString(rest, "")
	n := utf8.RuneCountInString(fragment)
	return n >= 1 && n <= 3 && isAlnum(fragment)
}

func isAlnum(s string) bool {
	for _, r := range s {
		if !unicode.IsLetter(r) && !unicode.IsDigit(r) {
			return false
		}
	}
	return true
}

func validValue(name, raw string) string {
	if !isASCII(raw) {
		return ""
	}
	if name == "uby_ws_user" {
		if wsUserShapeRE.MatchString(raw) {
			return raw
		}
		return ""
	}
	return raw
}

func parseField(name, text string, starts []int, lines []string) FieldResult {
	type hit struct {
		valueStr  string
		valueLine int
		label     string
		source    []string
	}
	var (
		hits              []hit
		labels, badLabels []struct {
			line  int
			label string
		}
		guarded      bool
		tailRE       *regexp.Regexp
		labelMatches []labelHit
	)
	switch name {
	case "uby_idub":
		tailRE = idubTailRE
		labelMatches = findIDUBLabels(text)
	case "uby_ws_user":
		tailRE = wsUserTailRE
		labelMatches = findWSUserLabels(text)
	default:
		return missingField
	}

	for _, lm := range labelMatches {
		if proseRE.MatchString(text[lm.end:]) {
			continue
		}
		label := lm.label
		labelLine := lineOf(starts, lm.start)
		labels = append(labels, struct {
			line  int
			label string
		}{labelLine, label})
		before := text[starts[labelLine-1]:lm.start]
		if !labelPrefixRE.MatchString(before) {
			badLabels = append(badLabels, struct {
				line  int
				label string
			}{labelLine, label})
			continue
		}
		loc := tailRE.FindStringSubmatchIndex(text[lm.end:])
		if loc == nil {
			badLabels = append(badLabels, struct {
				line  int
				label string
			}{labelLine, label})
			continue
		}
		valStart := lm.end + loc[2]
		valEnd := lm.end + loc[3]
		value := validValue(name, text[valStart:valEnd])
		if value == "" {
			badLabels = append(badLabels, struct {
				line  int
				label string
			}{labelLine, label})
			continue
		}
		valueLine := lineOf(starts, valStart)
		for n := labelLine; n <= valueLine; n++ {
			if hasPasswordWord(lineAt(lines, n)) {
				guarded = true
			}
		}
		gap := text[lm.end:valStart]
		var source []string
		if strings.Contains(gap, "\n") {
			colon := lm.end + strings.Index(gap, ":") + 1
			source = []string{text[lm.start:colon], text[valStart:valEnd]}
		} else {
			source = []string{text[lm.start : lm.end+loc[1]]}
		}
		for i := range source {
			if len(source[i]) > maxSource {
				source[i] = source[i][:maxSource]
			}
		}
		hits = append(hits, hit{value, valueLine, label, source})
	}

	if len(labels) == 0 {
		return missingField
	}
	unreadable := func(marked []struct {
		line  int
		label string
	}) FieldResult {
		linesSet := make(map[int]struct{})
		for _, m := range marked {
			linesSet[m.line] = struct{}{}
		}
		var ls []int
		for n := range linesSet {
			ls = append(ls, n)
		}
		sort.Ints(ls)
		return FieldResult{
			State: "unreadable",
			Line:  marked[0].line,
			Label: marked[0].label,
			Lines: ls,
		}
	}
	if len(badLabels) > 0 {
		return unreadable(badLabels)
	}
	cands := candidates(name, text)
	distinct := make(map[string]struct{})
	for _, c := range cands {
		distinct[c.value] = struct{}{}
	}
	if len(distinct) != 1 {
		return unreadable(labels)
	}
	var only string
	for v := range distinct {
		only = v
	}
	for _, h := range hits {
		if strings.ToUpper(h.valueStr) != only {
			return unreadable(labels)
		}
	}
	for _, c := range cands {
		endLine := lineOf(starts, c.end-1)
		if wrapped(name, lineAt(lines, endLine+1)) {
			return unreadable(labels)
		}
	}
	var hitLineNums []int
	for _, h := range hits {
		hitLineNums = append(hitLineNums, h.valueLine)
	}
	hitLines := sortedUniqueInts(hitLineNums)
	if guarded {
		return FieldResult{State: "ambiguous", Lines: hitLines}
	}
	h := hits[0]
	return FieldResult{
		State:  "found",
		Value:  h.valueStr,
		Line:   h.valueLine,
		Label:  h.label,
		Lines:  hitLines,
		Source: h.source,
	}
}
