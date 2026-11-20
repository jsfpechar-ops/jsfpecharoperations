package policyletter

import (
	"sort"
	"strings"
	"unicode/utf8"
)

func parsePassword(text string, starts []int, fields map[string]FieldResult) FieldResult {
	labels := pwLabelRE.FindAllStringIndex(text, -1)
	if len(labels) == 0 {
		return missingField
	}
	var values []string
	bad := false
	var valueLine int
	for _, loc := range labels {
		rest := text[loc[1]:]
		m := pwValueRE.FindStringSubmatch(rest)
		if m == nil {
			bad = true
			continue
		}
		idx := strings.Index(rest, m[1])
		values = append(values, m[1])
		valueLine = lineOf(starts, loc[1]+idx)
	}
	firstLine := lineOf(starts, labels[0][0])
	distinct := make(map[string]struct{})
	for _, v := range values {
		distinct[v] = struct{}{}
	}
	if len(distinct) > 1 {
		return FieldResult{State: "ambiguous", Line: firstLine}
	}
	if bad || len(distinct) == 0 {
		return FieldResult{State: "unreadable", Line: firstLine}
	}
	value := values[0]
	known := map[string]struct{}{
		fields["uby_idub"].Value:    {},
		fields["uby_ws_user"].Value: {},
	}
	if _, ok := known[value]; ok {
		return FieldResult{State: "unreadable", Line: firstLine}
	}
	if _, ok := known[strings.ToUpper(value)]; ok {
		return FieldResult{State: "unreadable", Line: firstLine}
	}
	if idubShapeRE.MatchString(value) || wsUserShapeRE.MatchString(value) || wsUserShapeRE.MatchString(strings.ToUpper(value)) {
		return FieldResult{State: "unreadable", Line: firstLine}
	}
	return FieldResult{State: "found", Value: value, Line: valueLine}
}

func parseFacility(text string, starts []int, lines []string) FieldResult {
	labels := facilityLabelRE.FindAllStringIndex(text, -1)
	if len(labels) == 0 {
		return missingField
	}
	labelLine := lineOf(starts, labels[0][0])
	if len(labels) > 1 {
		return FieldResult{State: "ambiguous", Line: labelLine}
	}
	end := len(text)
	if labelLine < len(starts) {
		end = starts[labelLine]
	}
	value := strings.TrimSpace(text[labels[0][1]:end])
	valueLine := labelLine
	if value == "" {
		for n := labelLine + 1; n <= len(lines); n++ {
			if strings.TrimSpace(lines[n-1]) != "" {
				value = strings.TrimSpace(lines[n-1])
				valueLine = n
				break
			}
		}
	}
	if value == "" || utf8.RuneCountInString(value) > maxFacility {
		return FieldResult{State: "unreadable", Line: labelLine}
	}
	return FieldResult{State: "found", Value: value, Line: valueLine}
}

func markWords(line string) []string {
	clean := strings.ReplaceAll(line, softHyphen, "")
	var out []string
	for _, word := range wordRE.FindAllString(clean, -1) {
		if l := utf8.RuneCountInString(word); l >= 4 && l <= 7 && !strings.Contains(plain(word), markWord) {
			out = append(out, word)
		}
	}
	return out
}

func markConflicts(lines []string, derived string) []int {
	wanted := strings.ToUpper(derived)
	var conflicts []int
	for index, line := range lines {
		if !strings.Contains(plain(strings.ReplaceAll(line, softHyphen, "")), markWord) {
			continue
		}
		number := index + 1
		soft := strings.Contains(line, softHyphen)
		words := markWords(line)
		if len(words) == 0 {
			for later := index + 1; later < len(lines); later++ {
				if strings.TrimSpace(lines[later]) != "" {
					words = markWords(lines[later])
					if strings.Contains(lines[later], softHyphen) {
						soft = true
					}
					if !soft {
						number = later + 1
					}
					break
				}
			}
		}
		if soft {
			conflicts = append(conflicts, number)
			continue
		}
		for _, word := range words {
			if strings.ToUpper(word) != wanted {
				conflicts = append(conflicts, number)
				break
			}
		}
	}
	return conflicts
}

func sortedUniqueInts(in []int) []int {
	m := make(map[int]struct{})
	var out []int
	for _, n := range in {
		if n == 0 {
			continue
		}
		if _, ok := m[n]; !ok {
			m[n] = struct{}{}
			out = append(out, n)
		}
	}
	sort.Ints(out)
	return out
}

func formatLetterResult(r LetterResult, _ bool) string {
	var b strings.Builder
	b.WriteString("LetterResult{Status:")
	b.WriteString(r.Status)
	b.WriteString("}")
	return b.String()
}
