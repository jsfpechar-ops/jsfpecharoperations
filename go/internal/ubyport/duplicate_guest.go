package ubyport

import (
	"slices"
	"strings"
)

// GuestIdentity holds the normalized-on-demand identity fields of a live guest
// row used to detect duplicate registrations within a single stay.
type GuestIdentity struct {
	ID          int64
	Surname     string
	FirstName   string
	BirthDate   string
	DocNumber   string
	Nationality string
}

func normGuestText(s string) string {
	return strings.ToLower(strings.Join(strings.Fields(strings.TrimSpace(s)), " "))
}

func normGuestDoc(s string) string {
	s = strings.ToUpper(strings.TrimSpace(s))
	if s == "" {
		return ""
	}
	var b strings.Builder
	b.Grow(len(s))
	for _, r := range s {
		if r == ' ' || r == '-' || r == '\t' {
			continue
		}
		b.WriteRune(r)
	}
	out := b.String()
	// Children registered in a parent's passport use the sentinel INPASS and must
	// never be treated as sharing a real document number.
	if out == "INPASS" {
		return ""
	}
	return out
}

func normGuestDOB(s string) string {
	return strings.TrimSpace(s)
}

// IsSamePerson reports whether two guest records on the same stay represent
// the same individual: matching (surname, first_name, birth_date) OR matching
// (doc_number, birth_date). Parent + child sharing a passport never match
// because birth_date and first_name differ.
func IsSamePerson(a, b GuestIdentity) bool {
	dobA, dobB := normGuestDOB(a.BirthDate), normGuestDOB(b.BirthDate)
	if dobA == "" || dobA != dobB {
		return false
	}
	surA, surB := normGuestText(a.Surname), normGuestText(b.Surname)
	firA, firB := normGuestText(a.FirstName), normGuestText(b.FirstName)
	if surA != "" && firA != "" && surA == surB && firA == firB {
		return true
	}
	docA, docB := normGuestDoc(a.DocNumber), normGuestDoc(b.DocNumber)
	return docA != "" && docA == docB
}

// IsPossibleDuplicate is broader than IsSamePerson for host alerting: it also
// flags two guests on the same stay sharing the exact same (doc_number,
// nationality) even if a birth date typo occurred.
func IsPossibleDuplicate(a, b GuestIdentity) bool {
	if IsSamePerson(a, b) {
		return true
	}
	docA, docB := normGuestDoc(a.DocNumber), normGuestDoc(b.DocNumber)
	natA, natB := normGuestText(a.Nationality), normGuestText(b.Nationality)
	return docA != "" && natA != "" && docA == docB && natA == natB
}

// DuplicateGuestIDs returns the set of higher-ID duplicate guest IDs within a
// stay that should be held out of automatic UbyPort filing. For each
// IsSamePerson group, the lowest-ID guest is kept sendable so the guest is
// still legally filed on time.
func DuplicateGuestIDs(guests []GuestIdentity) map[int64]bool {
	if len(guests) < 2 {
		return nil
	}
	sorted := make([]GuestIdentity, len(guests))
	copy(sorted, guests)
	slices.SortFunc(sorted, func(a, b GuestIdentity) int {
		if a.ID < b.ID {
			return -1
		}
		if a.ID > b.ID {
			return 1
		}
		return 0
	})
	var dups map[int64]bool
	var kept []GuestIdentity
	for _, g := range sorted {
		isDup := false
		for _, prev := range kept {
			if IsSamePerson(prev, g) {
				isDup = true
				break
			}
		}
		if isDup {
			if dups == nil {
				dups = make(map[int64]bool)
			}
			dups[g.ID] = true
			continue
		}
		kept = append(kept, g)
	}
	return dups
}

// PossibleDuplicateGuestIDs returns the sorted guest IDs participating in any
// IsPossibleDuplicate pair within the stay, or nil when there are none.
func PossibleDuplicateGuestIDs(guests []GuestIdentity) []int64 {
	if len(guests) < 2 {
		return nil
	}
	hit := map[int64]bool{}
	for i := 0; i < len(guests); i++ {
		for j := i + 1; j < len(guests); j++ {
			if IsPossibleDuplicate(guests[i], guests[j]) {
				hit[guests[i].ID] = true
				hit[guests[j].ID] = true
			}
		}
	}
	if len(hit) == 0 {
		return nil
	}
	out := make([]int64, 0, len(hit))
	for id := range hit {
		out = append(out, id)
	}
	slices.Sort(out)
	return out
}
