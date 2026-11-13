package cleaning

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

// TestTodayPragueMidnight: from 22:00 UTC (summer) or 23:00 UTC (winter) it is
// already the next day in Prague. The golden pins cleaning.today() to one
// constant date in cleaning_golden.py, so it never reaches this edge.
func TestTodayPragueMidnight(t *testing.T) {
	cases := []struct {
		at   time.Time
		want string
	}{
		{time.Date(2026, 5, 10, 21, 59, 0, 0, time.UTC), "2026-05-10"},
		{time.Date(2026, 5, 10, 22, 30, 0, 0, time.UTC), "2026-05-11"},
		{time.Date(2026, 12, 31, 22, 30, 0, 0, time.UTC), "2026-12-31"},
		{time.Date(2026, 12, 31, 23, 30, 0, 0, time.UTC), "2027-01-01"},
	}
	for _, c := range cases {
		if got := iso(today(c.at)); got != c.want {
			t.Errorf("today(%s) = %s, want %s", c.at.Format(time.RFC3339), got, c.want)
		}
	}
}

func TestColorNegativeID(t *testing.T) {
	want := map[int64]string{-4: "purple", -3: "teal", -2: "blue", -1: "purple", 0: "teal", 1: "blue", 2: "purple", 3: "teal"}
	for id, w := range want {
		if got := color(id); got != w {
			t.Errorf("color(%d) = %s, want %s", id, got, w)
		}
	}
}

func TestParseLimitedForm(t *testing.T) {
	post := func(body string) (*http.Request, *httptest.ResponseRecorder) {
		r := httptest.NewRequest(http.MethodPost, "/cleaning/events/1/delete", strings.NewReader(body))
		r.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		return r, httptest.NewRecorder()
	}
	r, w := post("revision=3")
	if !parseLimitedForm(w, r) || r.PostForm.Get("revision") != "3" {
		t.Fatalf("small form: ok=false or revision=%q", r.PostForm.Get("revision"))
	}
	r, w = post("revision=3&pad=" + strings.Repeat("a", formMaxBody))
	if parseLimitedForm(w, r) {
		t.Fatal("oversized form accepted")
	}
	if w.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("status %d, want 413", w.Code)
	}
}
