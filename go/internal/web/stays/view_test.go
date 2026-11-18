package stays

import (
	"net/url"
	"strings"
	"testing"
)

func TestEncodeQueryStable(t *testing.T) {
	raw := url.Values{"range": {"all"}, "report": {"failed"}}
	a := encodeQuery(raw, 2)
	b := encodeQuery(raw, 2)
	if a != b || a != "range=all&report=failed&page=2" {
		t.Fatalf("encodeQuery: %q", a)
	}
}

func TestChipsAndPagerURLs(t *testing.T) {
	today := fixedToday()
	q := url.Values{
		"range":     {"custom"},
		"status":    {"cancelled"},
		"apartment": {"12"},
		"from":      {"2026-07-01"},
		"to":        {"2026-07-10"},
		"page":      {"3"},
	}
	p := ParseParams(q, today)
	p.Page = 1
	v := BuildView(p, nil, 0, 1, 2, 0, false)
	for _, chip := range v.Chips {
		if strings.Contains(chip.Href, "page=") || strings.Contains(chip.Href, "from=") || strings.Contains(chip.Href, "to=") {
			t.Fatalf("chip %q href must drop page/from/to: %s", chip.Key, chip.Href)
		}
		if !strings.Contains(chip.Href, "status=cancelled") || !strings.Contains(chip.Href, "apartment=12") {
			t.Fatalf("chip %q href must keep status and apartment: %s", chip.Key, chip.Href)
		}
	}
	var failed *Chip
	for i := range v.Chips {
		if v.Chips[i].Key == "failed" {
			failed = &v.Chips[i]
		}
	}
	if failed == nil || strings.Contains(failed.Href, "range=") {
		t.Fatalf("report failed chip: %+v", failed)
	}
	var archive *Chip
	for i := range v.Chips {
		if v.Chips[i].Key == "archive" {
			archive = &v.Chips[i]
		}
	}
	if archive == nil || !strings.Contains(archive.Href, "range=archive") {
		t.Fatalf("archive chip: %+v", archive)
	}
	if v.ResetHref != "/reservations?range=all" {
		t.Fatalf("reset href=%q", v.ResetHref)
	}
	next := pageURL(p, 2)
	if want := "/reservations?apartment=12&from=2026-07-01&range=custom&status=cancelled&to=2026-07-10&page=2"; next != want {
		t.Fatalf("next url order:\n got %q\nwant %q", next, want)
	}
	for _, part := range []string{"range=custom", "status=cancelled", "apartment=12", "from=2026-07-01", "to=2026-07-10", "page=2"} {
		if !strings.Contains(next, part) {
			t.Fatalf("next url missing %q: %s", part, next)
		}
	}
	if v.PrevURL != "" {
		t.Fatalf("prev on page 1 must be empty, got %q", v.PrevURL)
	}
	p2 := p
	p2.Page = 2
	v2 := BuildView(p2, nil, 12, 2, 2, 0, false)
	if v2.PrevURL == "" {
		t.Fatal("expected prev url on page 2")
	}
	if !strings.Contains(v2.PrevURL, "page=1") {
		t.Fatalf("prev url: %s", v2.PrevURL)
	}
}
