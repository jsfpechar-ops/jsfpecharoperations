package ubyport

import (
	"reflect"
	"testing"
)

func TestIsSamePersonAndPossibleDuplicate(t *testing.T) {
	base := GuestIdentity{ID: 10, Surname: "Novak", FirstName: "Jan", BirthDate: "01021990", DocNumber: "AB-123 456", Nationality: "DEU"}

	// Case / whitespace normalization on name + DOB
	sameName := GuestIdentity{ID: 11, Surname: "  novak ", FirstName: "JAN", BirthDate: "01021990", DocNumber: "ZZ999", Nationality: "DEU"}
	if !IsSamePerson(base, sameName) {
		t.Fatal("expected same name + DOB to match")
	}

	// Doc normalization + DOB (even with typo in name)
	sameDoc := GuestIdentity{ID: 12, Surname: "Novakova", FirstName: "J", BirthDate: "01021990", DocNumber: "ab123456", Nationality: "DEU"}
	if !IsSamePerson(base, sameDoc) {
		t.Fatal("expected same doc + DOB to match")
	}

	// Parent + child with INPASS or different DOB must never match IsSamePerson
	child := GuestIdentity{ID: 13, Surname: "Novak", FirstName: "Eva", BirthDate: "15052020", DocNumber: "INPASS", Nationality: "DEU"}
	child2 := GuestIdentity{ID: 14, Surname: "Novak", FirstName: "Tomas", BirthDate: "15052020", DocNumber: "INPASS", Nationality: "DEU"}
	if IsSamePerson(base, child) || IsSamePerson(child, child2) {
		t.Fatal("INPASS children with different names must not match")
	}

	// Same doc + nationality with DOB typo: not IsSamePerson, YES IsPossibleDuplicate
	dobTypo := GuestIdentity{ID: 15, Surname: "Novak", FirstName: "Jan", BirthDate: "02021990", DocNumber: "AB123456", Nationality: "deu"}
	if IsSamePerson(base, dobTypo) {
		t.Fatal("different DOB should not hard-match IsSamePerson")
	}
	if !IsPossibleDuplicate(base, dobTypo) {
		t.Fatal("same doc + nationality should trigger IsPossibleDuplicate")
	}

	// DuplicateGuestIDs keeps lowest ID
	dups := DuplicateGuestIDs([]GuestIdentity{sameName, base, child})
	if len(dups) != 1 || !dups[11] || dups[10] {
		t.Fatalf("expected only higher ID 11 marked duplicate, got %v", dups)
	}

	// PossibleDuplicateGuestIDs returns sorted IDs
	ids := PossibleDuplicateGuestIDs([]GuestIdentity{dobTypo, base, child})
	if !reflect.DeepEqual(ids, []int64{10, 15}) {
		t.Fatalf("got %v, want [10 15]", ids)
	}
}
