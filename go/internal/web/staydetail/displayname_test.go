package staydetail

import "testing"

func TestDisplayName(t *testing.T) {
	cases := []struct{ in, want string }{
		{"TOMAS NOVAK", "Tomas Novak"},
		{"ANNE-MARIE DUPONT", "Anne-Marie Dupont"},
		{"O'BRIEN", "O'Brien"},
		{"D\u2019ARTAGNAN", "D\u2019Artagnan"},
		{"NGUY\u1ec4N V\u0102N AN", "Nguy\u1ec5n V\u0103n An"},
		{"MARIE-\u00c9LISE", "Marie-\u00c9lise"},
		{"JOSEF PECHAR", "Josef Pechar"},
		{"  TOMAS   NOVAK ", "  Tomas   Novak "},
		{"Josef Pechar", "Josef Pechar"},
		{"McDonald", "McDonald"},
		{"van der Berg", "van der Berg"},
		{"Josef PECHAR", "Josef PECHAR"},
		{"", ""},
	}
	for _, c := range cases {
		if got := displayName(c.in); got != c.want {
			t.Errorf("displayName(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}
