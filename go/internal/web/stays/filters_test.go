package stays

import (
	"net/url"
	"testing"
)

func TestChipHrefsKeepFiltersDropPage(t *testing.T) {
	today := fixedToday()
	p := ParseParams(url.Values{
		"range": {"upcoming"}, "status": {"cancelled"}, "apartment": {"7"}, "page": {"2"}, "from": {"2026-01-01"},
	}, today)
	chips := buildChips(p)
	for _, c := range chips {
		u, err := url.Parse(c.Href)
		if err != nil {
			t.Fatal(err)
		}
		q := u.Query()
		if q.Get("page") != "" || q.Get("from") != "" || q.Get("to") != "" {
			t.Fatalf("%s keeps page/from/to", c.Href)
		}
		if q.Get("status") != "cancelled" || q.Get("apartment") != "7" {
			t.Fatalf("%s drops filter", c.Href)
		}
		if c.Key == "failed" && q.Get("range") != "" {
			t.Fatalf("failed chip has range")
		}
	}
	v := BuildView(p, nil, 12, 2, 3, 0, false)
	if v.PrevURL == "" {
		t.Fatal("page2 prev")
	}
	if !stringsContains(v.Chips[0].Href, "apartment=7") {
		t.Fatal("chip apartment")
	}
}

func stringsContains(s, sub string) bool {
	return len(s) >= len(sub) && (s == sub || len(sub) == 0 || indexOf(s, sub) >= 0)
}

func indexOf(s, sub string) int {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return i
		}
	}
	return -1
}