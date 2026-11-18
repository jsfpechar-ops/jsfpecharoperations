package policyletter

import (
	"strings"
	"testing"
)

const (
	sampleIDUB       = "209988776655"
	sampleZkratka    = "DEMO1"
	sampleWSUser     = "UBY-WS_" + sampleZkratka
	sampleWSPassword = "Uk@zKa-H3sl0-FAKE"
	sampleFacility1  = "BYT Č. [2] FIKTVNÍ 1234/56 (PRAHA,"
)

var (
	title = "Přihlašovací údaje pro robotické vkládání Ubyport Webová služba"
	lUser = "Přihlašovací jméno:"
	lPW   = "Přístupové heslo:"
	lMark = "Zkratka ubytovacího zařízení:"
)

func official() string {
	return title + "\n" + lUser + " " + sampleWSUser + "\n" + lPW + " " + sampleWSPassword + "\nIDUB: " + sampleIDUB + "\n"
}

func TestConstantsMatchPython(t *testing.T) {
	if MaxLetterChars != 20000 {
		t.Fatalf("MaxLetterChars = %d", MaxLetterChars)
	}
	if len(Fields) != 3 || Fields[0] != "uby_idub" || Fields[1] != "uby_ws_user" || Fields[2] != "uby_mark" {
		t.Fatalf("Fields = %v", Fields)
	}
	if !FilledStates["found"] || !FilledStates["derived"] || len(FilledStates) != 2 {
		t.Fatalf("FilledStates = %v", FilledStates)
	}
}

func TestParseOfficial(t *testing.T) {
	r := ParseLetter(official())
	if r.Status != "ok" {
		t.Fatalf("status %q", r.Status)
	}
	idub := r.Fields["uby_idub"]
	if idub.State != "found" || idub.Value != sampleIDUB || idub.Line != 4 {
		t.Fatalf("idub %+v", idub)
	}
	user := r.Fields["uby_ws_user"]
	if user.State != "found" || user.Value != sampleWSUser || user.Line != 2 {
		t.Fatalf("user %+v", user)
	}
	mark := r.Fields["uby_mark"]
	if mark.State != "derived" || mark.Value != sampleZkratka {
		t.Fatalf("mark %+v", mark)
	}
	if r.Password.State != "found" || r.Password.Value != sampleWSPassword {
		t.Fatalf("password %+v", r.Password)
	}
	if strings.Contains(r.String(), sampleWSPassword) {
		t.Fatal("password leaked in String()")
	}
}

func TestMarkConflict(t *testing.T) {
	text := official() + lMark + " XYZ12\n"
	r := ParseLetter(text)
	if r.Fields["uby_ws_user"].State != "conflict" || r.Fields["uby_mark"].State != "conflict" {
		t.Fatalf("fields %+v", r.Fields)
	}
	want := []int{2, 5}
	if !intSliceEqual(r.Fields["uby_mark"].Lines, want) {
		t.Fatalf("lines %v want %v", r.Fields["uby_mark"].Lines, want)
	}
}

func TestEmptyAndTooLong(t *testing.T) {
	if ParseLetter("").Status != "empty" {
		t.Fatal("blank should be empty")
	}
	if ParseLetter(strings.Repeat("x", MaxLetterChars+1)).Status != "too_long" {
		t.Fatal("over max should be too_long")
	}
}

func TestConfirmedFieldsAndLineFromForm(t *testing.T) {
	listed, unconfirmed := ConfirmedFields(map[string]string{
		"letter_fields": "uby_idub,uby_ws_user,uby_mark",
	})
	if len(unconfirmed) != 0 || len(listed) != 3 {
		t.Fatalf("listed=%v unconfirmed=%v", listed, unconfirmed)
	}
	n := LineFromForm(map[string]string{"letter_line_uby_idub": "7"}, "uby_idub")
	if n == nil || *n != 7 {
		t.Fatalf("line %v", n)
	}
	if LineFromForm(map[string]string{"letter_line_uby_idub": "abc"}, "uby_idub") != nil {
		t.Fatal("letters should be nil")
	}
}

func TestPasswordTrailingDot(t *testing.T) {
	text := lPW + " Ab3x9q.\n"
	r := ParseLetter(text)
	if r.Password.State != "found" || r.Password.Value != "Ab3x9q." {
		t.Fatalf("password %+v", r.Password)
	}
}

func TestFacilityOnSameLine(t *testing.T) {
	text := "Ubytovací zařízení: " + sampleFacility1 + "\n"
	r := ParseLetter(text)
	if r.Facility.State != "found" || r.Facility.Value != sampleFacility1 {
		t.Fatalf("facility %+v", r.Facility)
	}
}

func intSliceEqual(a, b []int) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
