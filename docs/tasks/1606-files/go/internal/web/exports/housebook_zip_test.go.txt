package exports

// Brief 1606: housebook._pdf_entry_name on rows the golden does not reach
// (values printed by the Python function on the same rows).

import (
	"strings"
	"testing"
)

func TestPDFEntryName(t *testing.T) {
	for _, c := range []struct {
		g    row
		want string
	}{
		{row{"id": int64(7)}, "guest-7.pdf"},
		{row{"id": int64(8), "surname": "---"}, "guest-8.pdf"},
		{row{"id": int64(9), "res_from": "2026-01-02", "surname": strings.Repeat("Ž", 120)},
			"2026-01-02-" + strings.Repeat("Ž", 85) + ".pdf"},
		{row{"id": int64(10), "stay_from": "2026-03-04", "res_from": "2026-01-02", "first_name": "a/b c"}, "2026-03-04-a_b_c.pdf"},
		{row{"id": int64(5), "surname": "O'Brien Smith", "first_name": "Zoë"}, "O_Brien_Smith-Zoë.pdf"},
	} {
		if got := pdfEntryName(c.g); got != c.want {
			t.Errorf("pdfEntryName(%v) = %q, want %q", c.g, got, c.want)
		}
	}
}
