package dococr

import (
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

const (
	td3Len    = 44
	td2Len    = 36
	td2MaxLen = 40
	td1Len    = 30
)

var mrzWeights = [3]int{7, 3, 1}

// ParseMRZ extracts normalised guest fields from raw OCR text, trying ICAO 9303
// TD3 (2x44 passports), TD2 (2x36 ID/travel docs), then TD1 (3x30 ID cards).
func ParseMRZ(rawText string) (map[string]string, error) {
	lines := mrzLines(rawText)
	for i := 0; i+1 < len(lines); i++ {
		if v := parseTD3(lines[i], lines[i+1]); v != nil {
			return v, nil
		}
	}
	for i := 0; i+1 < len(lines); i++ {
		if v := parseTD2(lines[i], lines[i+1]); v != nil {
			return v, nil
		}
	}
	for i := 0; i+2 < len(lines); i++ {
		if v := parseTD1(lines[i], lines[i+1], lines[i+2]); v != nil {
			return v, nil
		}
	}
	return nil, ErrNothingRead
}

func mrzLines(rawText string) []string {
	var out []string
	for _, raw := range strings.Split(strings.ToUpper(rawText), "\n") {
		raw = strings.TrimSpace(raw)
		if raw == "" {
			continue
		}
		var b strings.Builder
		b.Grow(len(raw))
		for i := 0; i < len(raw); i++ {
			c := raw[i]
			if (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '<' {
				b.WriteByte(c)
			}
		}
		cleaned := b.String()
		if len(cleaned) >= td1Len {
			out = append(out, cleaned)
		}
	}
	return out
}

func checkDigit(field string) byte {
	total := 0
	for i := 0; i < len(field); i++ {
		c := field[i]
		val := 0
		switch {
		case c >= '0' && c <= '9':
			val = int(c - '0')
		case c >= 'A' && c <= 'Z':
			val = 10 + int(c-'A')
		}
		total += val * mrzWeights[i%3]
	}
	return byte('0' + (total % 10))
}

func normCheckByte(c byte) byte {
	if c == 'O' {
		return '0'
	}
	return c
}

func fixOConfusion(field string, check byte) (string, bool) {
	want := normCheckByte(check)
	if want < '0' || want > '9' {
		return field, false
	}
	if checkDigit(field) == want {
		return field, true
	}
	for _, cand := range []string{
		strings.ReplaceAll(field, "O", "0"),
		strings.ReplaceAll(field, "0", "O"),
	} {
		if checkDigit(cand) == want {
			return cand, true
		}
	}
	return field, false
}

func cleanMRZField(s string) string {
	return strings.TrimSpace(strings.ReplaceAll(s, "<", " "))
}

func yymmddToDDMMYYYY(s string) string {
	if len(s) != 6 {
		return ""
	}
	for i := 0; i < 6; i++ {
		if s[i] < '0' || s[i] > '9' {
			return ""
		}
	}
	yy := int(s[0]-'0')*10 + int(s[1]-'0')
	mm := int(s[2]-'0')*10 + int(s[3]-'0')
	dd := int(s[4]-'0')*10 + int(s[5]-'0')
	year := 1900 + yy
	if yy <= 29 {
		year = 2000 + yy
	}
	if mm < 1 || mm > 12 || dd < 1 || dd > 31 {
		return ""
	}
	return string([]byte{
		byte('0' + dd/10), byte('0' + dd%10),
		byte('0' + mm/10), byte('0' + mm%10),
		byte('0' + year/1000), byte('0' + (year/100)%10), byte('0' + (year/10)%10), byte('0' + year%10),
	})
}

func splitMRZNames(zone string) (surname, firstName string) {
	parts := strings.SplitN(zone, "<<", 2)
	surname = cleanMRZField(parts[0])
	if len(parts) > 1 {
		firstName = cleanMRZField(parts[1])
	}
	return surname, firstName
}

func buildMRZResult(surname, firstName, birth, nationality, doc string) map[string]string {
	if surname == "" || birth == "" {
		return nil
	}
	return map[string]string{
		"surname":     validation.NormaliseName(surname),
		"first_name":  validation.NormaliseName(firstName),
		"birth_date":  birth,
		"nationality": nationality,
		"doc_number":  validation.NormaliseDocument(doc),
	}
}

func parseTD3(line1, line2 string) map[string]string {
	if len(line1) < td3Len || len(line2) < td3Len {
		return nil
	}
	if line1[0] != 'P' || line1[1] != '<' {
		return nil
	}
	doc, ok := fixOConfusion(line2[0:9], line2[9])
	if !ok {
		return nil
	}
	birthRaw, ok := fixOConfusion(line2[13:19], line2[19])
	if !ok {
		return nil
	}
	surname, firstName := splitMRZNames(line1[5:])
	birth := yymmddToDDMMYYYY(birthRaw)
	return buildMRZResult(surname, firstName, birth, line2[10:13], doc)
}

func parseTD2(line1, line2 string) map[string]string {
	if len(line1) < td2Len || len(line2) < td2Len || len(line1) > td2MaxLen || len(line2) > td2MaxLen {
		return nil
	}
	switch line1[0] {
	case 'I', 'A', 'C', 'V':
	default:
		return nil
	}
	doc, ok := fixOConfusion(line2[0:9], line2[9])
	if !ok {
		return nil
	}
	birthRaw, ok := fixOConfusion(line2[13:19], line2[19])
	if !ok {
		return nil
	}
	surname, firstName := splitMRZNames(line1[5:td2Len])
	birth := yymmddToDDMMYYYY(birthRaw)
	return buildMRZResult(surname, firstName, birth, line2[10:13], doc)
}

func parseTD1(line1, line2, line3 string) map[string]string {
	if len(line1) < td1Len || len(line2) < td1Len || len(line3) < td1Len {
		return nil
	}
	doc, ok := fixOConfusion(line1[5:14], line1[14])
	if !ok {
		return nil
	}
	birthRaw, ok := fixOConfusion(line2[0:6], line2[6])
	if !ok {
		return nil
	}
	surname, firstName := splitMRZNames(line3)
	birth := yymmddToDDMMYYYY(birthRaw)
	return buildMRZResult(surname, firstName, birth, line2[15:18], doc)
}
