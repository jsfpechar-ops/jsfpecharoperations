package stayfees

import "testing"

// The want values were printed by the Python functions the helpers copy
// (security.safe_local_path, routes/stay_fees.py fee_return_path and
// _fold_place, stay_fee.parse_month).
func TestSafeLocalPathAndFeeReturnPath(t *testing.T) {
	cases := []struct{ in, safe, back string }{
		{"/stay-fees", "/stay-fees", "/stay-fees"},
		{"/stay-fees/12/", "/stay-fees/12", "/stay-fees/12"},
		{"/stay-fees/./12?a=1#x", "/stay-fees/12?a=1", "/stay-fees/12?a=1"},
		{"//evil/stay-fees", "", ""},
		{"/stay-fees/%2e%2e/12", "/stay-fees/%2e%2e/12", ""},
		{"/%2F%2Fevil", "", ""},
		{"http:/stay-fees", "", ""},
		{"HTTP://x/stay-fees", "", ""},
		{"/stay-fees?month=2026-10&b=c", "/stay-fees?month=2026-10&b=c", "/stay-fees?month=2026-10&b=c"},
		{"  /stay-fees  ", "/stay-fees", "/stay-fees"},
		{"/stay-fees/12/../13", "/stay-fees/13", ""},
		{"/a:b", "/a:b", ""},
		{"///stay-fees", "/stay-fees", "/stay-fees"},
		{"/stay-fees\t", "/stay-fees", "/stay-fees"},
	}
	for _, c := range cases {
		if got := safeLocalPath(c.in, ""); got != c.safe {
			t.Errorf("safeLocalPath(%q) = %q, want %q", c.in, got, c.safe)
		}
		if got := feeReturnPath(c.in, 12); got != c.back {
			t.Errorf("feeReturnPath(%q) = %q, want %q", c.in, got, c.back)
		}
	}
}

func TestParseMonth(t *testing.T) {
	cases := []struct {
		in   string
		want string
	}{
		{"2026-10", "2026-10"}, {" 2026-01 ", "2026-01"}, {"1999-12", ""}, {"2026-13", ""},
		{"2026-00", ""}, {"2026/10", ""}, {"26-10", ""},
	}
	for _, c := range cases {
		m, ok := parseMonth(c.in)
		got := ""
		if ok {
			got = monthKey(m)
		}
		if got != c.want {
			t.Errorf("parseMonth(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}

func TestFoldPlace(t *testing.T) {
	cases := map[string]string{"Praha 3": "praha 3", "  ŘÍČANY ": "ricany", "Straße": "strasse", "ﬁ": "fi"}
	for in, want := range cases {
		if got := foldPlace(in); got != want {
			t.Errorf("foldPlace(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestOverlapKeys(t *testing.T) {
	m := monthStart(2026, 8)
	if got := overlapKeys("monthly", m); len(got) != 2 || got[0] != "2026-08" || got[1] != "2026-Q3" {
		t.Errorf("monthly overlap %v", got)
	}
	if got := overlapKeys("quarterly", m); len(got) != 4 || got[0] != "2026-Q3" || got[1] != "2026-07" || got[3] != "2026-09" {
		t.Errorf("quarterly overlap %v", got)
	}
}
