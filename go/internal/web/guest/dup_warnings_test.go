package guest

import (
	"reflect"
	"testing"
)

// TestDupWarningsFor: the same pairs guest.py _duplicate_warnings flags, a
// non-duplicate, and the owned-only rule.
func TestDupWarningsFor(t *testing.T) {
	keyAsText := func(k string) string { return k }
	cases := []struct {
		name   string
		guests []dupGuest
		owned  []int64
		want   []dupWarning
	}{
		{
			name: "same document number, spacing and case ignored",
			guests: []dupGuest{
				{ID: 1, First: "jan", Surname: "novák", Birth: "1990-05-05", Doc: "x-1"},
				{ID: 2, First: "eva", Surname: "novak", Birth: "1991-01-01", Doc: "X 1"},
			},
			owned: []int64{1},
			want:  []dupWarning{{Name: "Jan Novák", What: "dup_what_doc"}},
		},
		{
			name: "same name and birth date",
			guests: []dupGuest{
				{ID: 3, First: "olga", Surname: "DVORAK ", Birth: "1970-02-02", Doc: "Z9"},
				{ID: 4, First: " Olga", Surname: "Dvorak", Birth: "1970-02-02", Doc: "Q7"},
			},
			owned: []int64{3},
			want:  []dupWarning{{Name: "Olga Dvorak", What: "dup_what_person"}},
		},
		{
			name: "document and person together",
			guests: []dupGuest{
				{ID: 5, First: "Ida", Surname: "Kral", Birth: "1999-09-09", Doc: "M5"},
				{ID: 6, First: "IDA", Surname: "KRAL", Birth: "1999-09-09", Doc: "M5"},
			},
			owned: []int64{5},
			want:  []dupWarning{{Name: "Ida Kral", What: "dup_what_doc, dup_what_person"}},
		},
		{
			name: "other person's duplicate is not shown",
			guests: []dupGuest{
				{ID: 6, First: "IDA", Surname: "KRAL", Birth: "1999-09-09", Doc: "M5"},
				{ID: 7, First: "Ida", Surname: "Kral", Birth: "1999-09-09", Doc: "M5"},
			},
			owned: []int64{7},
			want:  []dupWarning{{Name: "Ida Kral", What: "dup_what_doc, dup_what_person"}},
		},
		{
			name: "non-duplicate",
			guests: []dupGuest{
				{ID: 8, First: "Tom", Surname: "Hill", Birth: "2000-01-01", Doc: "T1"},
				{ID: 9, First: "Tom", Surname: "Hill", Birth: "2001-01-01", Doc: "T2"},
			},
			owned: []int64{8, 9},
			want:  nil,
		},
		{
			name: "INPASS is not a document number",
			guests: []dupGuest{
				{ID: 10, First: "Lea", Surname: "Park", Birth: "2015-03-03", Doc: "INPASS"},
				{ID: 11, First: "Max", Surname: "Park", Birth: "2012-04-04", Doc: "INPASS"},
			},
			owned: []int64{10, 11},
			want:  nil,
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			owned := map[int64]bool{}
			for _, id := range tc.owned {
				owned[id] = true
			}
			got := dupWarningsFor(tc.guests, owned, keyAsText)
			if !reflect.DeepEqual(got, tc.want) {
				t.Errorf("got %+v, want %+v", got, tc.want)
			}
		})
	}
}
