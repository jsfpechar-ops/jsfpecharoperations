package public

import (
	"net/url"
	"testing"
	"time"
)

// Values below were printed by legal._graduated, _per_month and _kc.
func TestPricingArithmetic(t *testing.T) {
	year := rateList("base", "year")
	for count, want := range map[int]int{1: 1190, 4: 4760, 5: 5710, 9: 9510, 10: 10300, 12: 11880} {
		if got := graduated(count, year); got != want {
			t.Errorf("graduated(%d) = %d, want %d", count, got, want)
		}
	}
	for year, want := range map[int]int{1190: 99, 1234: 103, 470: 39, 5000: 417} {
		if got := perMonth(year); got != want {
			t.Errorf("perMonth(%d) = %d, want %d", year, got, want)
		}
	}
	cs := map[int]string{49: "49", 1190: "1\u00a0190", 12345: "12\u00a0345", 1234567: "1\u00a0234\u00a0567"}
	en := map[int]string{49: "49", 1190: "1,190", 12345: "12,345", 1234567: "1,234,567"}
	for n, want := range cs {
		if got := kc(n, "cs"); got != want {
			t.Errorf("kc(%d, cs) = %q, want %q", n, got, want)
		}
	}
	for n, want := range en {
		if got := kc(n, "en"); got != want {
			t.Errorf("kc(%d, en) = %q, want %q", n, got, want)
		}
	}
}

// TestSignupHrefMintsLikePython: a raw click identifier is signed with the
// page-view time; the token below is signup.issue_click({"gclid": "abc123"},
// 1700000000000) under the golden script's key.
func TestSignupHrefMintsLikePython(t *testing.T) {
	const secret = "public-legal-golden-secret-not-real-0123"
	const token = "eyJpIjp7ImdjbGlkIjoiYWJjMTIzIn0sInQiOjE3MDAwMDAwMDAwMDB9.5NnpcxV9Kow9KX_-1v4KMBfUAZY"
	got := signupHref(secret, "cs", url.Values{"gclid": {"abc123"}, "utm_source": {"g"}}, time.UnixMilli(1700000000000))
	want := "/signup?lang=cs&utm_source=g&click=" + token
	if got != want {
		t.Fatalf("signupHref:\n got %s\nwant %s", got, want)
	}
	if got := signupHref(secret, "vi", url.Values{}, time.Now()); got != "/signup?lang=vi" {
		t.Fatalf("plain signupHref = %s", got)
	}
}
