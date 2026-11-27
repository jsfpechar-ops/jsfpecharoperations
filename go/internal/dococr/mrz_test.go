package dococr

import (
	"bytes"
	"errors"
	"testing"
)

func td3Sample(surname, given, doc, nat, birth string) string {
	l1 := "P<UTO" + surname + "<<" + given
	for len(l1) < 44 {
		l1 += "<"
	}
	l1 = l1[:44]
	for len(doc) < 9 {
		doc += "<"
	}
	doc = doc[:9]
	docCD := string(checkDigit(doc))
	birthCD := string(checkDigit(birth))
	l2 := doc + docCD + nat + birth + birthCD + "M3001015<<<<<<<<<<<<<<00"
	for len(l2) < 44 {
		l2 += "<"
	}
	return l1 + "\n" + l2[:44]
}

func td2Sample(surname, given, doc, nat, birth string) string {
	l1 := "I<UTO" + surname + "<<" + given
	for len(l1) < 36 {
		l1 += "<"
	}
	l1 = l1[:36]
	for len(doc) < 9 {
		doc += "<"
	}
	doc = doc[:9]
	docCD := string(checkDigit(doc))
	birthCD := string(checkDigit(birth))
	l2 := doc + docCD + nat + birth + birthCD + "F3001015<<<<<<<0"
	for len(l2) < 36 {
		l2 += "<"
	}
	return l1 + "\n" + l2[:36]
}

func td1Sample(surname, given, doc, nat, birth string) string {
	for len(doc) < 9 {
		doc += "<"
	}
	doc = doc[:9]
	l1 := "IDUTO" + doc + string(checkDigit(doc)) + "<<<<<<<<<<<<<<<"
	l1 = l1[:30]
	l2 := birth + string(checkDigit(birth)) + "F3001015" + nat + "<<<<<<<<<<<0"
	l2 = l2[:30]
	l3 := surname + "<<" + given
	for len(l3) < 30 {
		l3 += "<"
	}
	return l1 + "\n" + l2 + "\n" + l3[:30]
}

func TestCheckDigitICAO731(t *testing.T) {
	if got := checkDigit("AB2134<<<"); got != '5' {
		t.Fatalf("checkDigit(AB2134<<<) = %c, want 5", got)
	}
	if got := checkDigit("520727"); got != '3' {
		t.Fatalf("checkDigit(520727) = %c, want 3", got)
	}
	if got := checkDigit("L898902C3"); got != '6' {
		t.Fatalf("checkDigit(L898902C3) = %c, want 6", got)
	}
}

func TestOAndZeroConfusionResolvesByCheckDigit(t *testing.T) {
	cd := checkDigit("900101")
	got, ok := fixOConfusion("9OO1O1", cd)
	if !ok || got != "900101" {
		t.Fatalf("fixOConfusion = (%q, %v), want (900101, true)", got, ok)
	}
	zeroField := "000000"
	if got, ok := fixOConfusion(zeroField, 'O'); !ok || got != zeroField {
		t.Fatalf("fixOConfusion check O->0 = (%q, %v), want true", got, ok)
	}
}

func TestParseMRZTD3(t *testing.T) {
	raw := td3Sample("ERIKSSON", "ANNA<MARIA", "L898902C3", "SWE", "740812")
	got, err := ParseMRZ(raw)
	if err != nil {
		t.Fatalf("ParseMRZ TD3: %v", err)
	}
	want := map[string]string{
		"surname":     "ERIKSSON",
		"first_name":  "ANNA MARIA",
		"birth_date":  "12081974",
		"nationality": "SWE",
		"doc_number":  "L898902C3",
	}
	for k, w := range want {
		if got[k] != w {
			t.Errorf("%s = %q, want %q", k, got[k], w)
		}
	}
}

func TestParseMRZTD3RequiresPassportMarker(t *testing.T) {
	raw := td3Sample("NOVAK", "JAN", "P1234567", "CZE", "900101")
	lines := bytes.Split([]byte(raw), []byte("\n"))
	if got := parseTD3("I<"+string(lines[0][2:]), string(lines[1])); got != nil {
		t.Fatalf("TD3 accepted non-passport line1: %v", got)
	}
}

func TestParseMRZTD2(t *testing.T) {
	raw := td2Sample("ERIKSSON", "ANNA<MARIA", "D23145890", "DEU", "850420")
	got, err := ParseMRZ(raw)
	if err != nil {
		t.Fatalf("ParseMRZ TD2: %v", err)
	}
	want := map[string]string{
		"surname":     "ERIKSSON",
		"first_name":  "ANNA MARIA",
		"birth_date":  "20041985",
		"nationality": "DEU",
		"doc_number":  "D23145890",
	}
	for k, w := range want {
		if got[k] != w {
			t.Errorf("%s = %q, want %q", k, got[k], w)
		}
	}
}

func TestParseMRZTD1(t *testing.T) {
	raw := td1Sample("NOVAK", "JANA", "ID123456", "SVK", "050315")
	got, err := ParseMRZ(raw)
	if err != nil {
		t.Fatalf("ParseMRZ TD1: %v", err)
	}
	want := map[string]string{
		"surname":     "NOVAK",
		"first_name":  "JANA",
		"birth_date":  "15032005",
		"nationality": "SVK",
		"doc_number":  "ID123456",
	}
	for k, w := range want {
		if got[k] != w {
			t.Errorf("%s = %q, want %q", k, got[k], w)
		}
	}
}

func TestParseMRZBadCheckDigitRefused(t *testing.T) {
	raw := td3Sample("SMITH", "JOHN", "P1234567", "GBR", "900101")
	lines := bytes.Split([]byte(raw), []byte("\n"))
	bad := append([]byte{}, lines[1]...)
	if bad[9] == '0' {
		bad[9] = '1'
	} else {
		bad[9] = '0'
	}
	if _, err := ParseMRZ(string(lines[0]) + "\n" + string(bad)); !errors.Is(err, ErrNothingRead) {
		t.Fatalf("expected ErrNothingRead for bad check digit, got %v", err)
	}
}
