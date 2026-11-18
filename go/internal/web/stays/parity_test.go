package stays

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

func renderStaysHTML(t *testing.T, data listPage) string {
	t.Helper()
	w := httptest.NewRecorder()
	r := httptest.NewRequest(http.MethodGet, "/reservations?lang=en", nil)
	page := layout.Page{Title: "Stays", Nav: "reservations", BodyKind: "list", V2: true, HowKey: "stays", BodyAlerts: false}
	env := layout.Env{Getenv: func(string) string { return "golden-secret-key-not-for-real-use" }, Now: fixedToday()}
	if err := layout.Render(w, r, env, nil, page, pages, "stays_list", data); err != nil {
		t.Fatal(err)
	}
	return w.Body.String()
}

func normalizeHTML(s string) string {
	s = regexp.MustCompile(`name="_csrf" value="[^"]*"`).ReplaceAllString(s, `name="_csrf" value="CSRF"`)
	s = regexp.MustCompile(`>\s+<`).ReplaceAllString(s, "><")
	s = regexp.MustCompile(`\s+`).ReplaceAllString(s, " ")
	return strings.TrimSpace(s)
}

func staysParityFragments(html string) string {
	var b strings.Builder
	for _, sel := range []struct{ open, close string }{
		{`<nav class="settings-pills"`, `</nav>`},
		{`<tbody class="stays-list">`, `</tbody>`},
		{`<nav class="stays-pager ph-hide"`, `</nav>`},
		{`data-stays-more`, `</div>`},
	} {
		i := strings.Index(html, sel.open)
		if i < 0 {
			continue
		}
		rest := html[i:]
		end := strings.Index(rest, sel.close)
		if end < 0 {
			continue
		}
		end += len(sel.close)
		b.WriteString(rest[:end])
		b.WriteByte('\n')
	}
	return b.String()
}

func parityFixture(today time.Time, page int, report string) listPage {
	p := ParseParams(url.Values{"range": {"all"}}, today)
	if page > 1 {
		p.Raw.Set("page", strconv.Itoa(page))
		p.Page = page
	}
	if report != "" {
		p.Report = report
		p.Raw.Set("report", report)
	}
	rows := parityRows(today)
	view := BuildView(p, rows[:minInt(5, len(rows))], 6, page, 2, 0, false)
	if page == 1 && len(rows) > 5 {
		view.Rows = rows[:5]
	}
	if page == 2 {
		view.Rows = rows[5:6]
	}
	return listPage{
		View: view, Apartments: []apartmentItem{{ID: 1, Name: "Chrome Flat"}},
		Status: "active", DateRange: "all", StayProperty: "Chrome Flat",
		ReturnTo: "/reservations?range=all", HasAny: 1, FeedCount: 1,
		CSVExportParams: "apartment=", PaymentsHidden: false, PublicBase: "https://guest.example",
		Today: pragueToday(today), PageSize: PageSize, Groups: groupRows(view.Rows, today),
	}
}

func parityRows(today time.Time) []Row {
	base := today
	type spec struct {
		from, to, status, source, name string
		failed                         bool
		archived                       bool
	}
	specs := []spec{
		{"2026-06-10", "2026-06-12", "active", "manual", "Sofia Costa", false, false},
		{"2026-06-13", "2026-06-14", "active", "manual", "", false, false},
		{"2026-06-15", "2026-06-17", "active", "manual", "Lead Three", false, false},
		{"2026-06-18", "2026-06-20", "active", "manual", "Lead Four", false, false},
		{"2026-06-21", "2026-06-23", "active", "manual", "Lead Five", false, false},
		{"2026-06-24", "2026-06-26", "cancelled", "manual", "Archived", false, true},
	}
	out := make([]Row, 0, len(specs))
	for i, s := range specs {
		guests := []Guest{}
		if s.name != "" {
			parts := strings.SplitN(s.name, " ", 2)
			sur := ""
			if len(parts) > 1 {
				sur = parts[1]
			}
			guests = append(guests, Guest{FirstName: parts[0], Surname: sur, IsLead: true})
		}
		st := "ready"
		if s.failed {
			st = "failed"
		}
		out = append(out, Row{
			Reservation: Reservation{
				ID: int64(1000 + i), ApartmentID: 1, DateFrom: s.from, DateTo: s.to,
				Status: s.status, Source: s.source, InternalName: "Chrome Flat",
				PermalinkToken: "tok", AutomationMode: "manual",
			},
			Progress: Progress{Status: st, Guests: guests, Filled: len(guests)},
		})
	}
	_ = base
	return out
}

func assertGolden(t *testing.T, name string, got string) {
	t.Helper()
	path := filepath.Join("testdata", name)
	if os.Getenv("STAYS_UPDATE_GOLDEN") == "1" {
		if err := os.MkdirAll("testdata", 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte(got), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	want, err := os.ReadFile(path)
	if err != nil {
		t.Skipf("missing golden %s (run with STAYS_UPDATE_GOLDEN=1)", name)
	}
	if normalizeHTML(string(want)) != normalizeHTML(got) {
		t.Fatalf("golden %s mismatch", name)
	}
}

func TestParityStaysPage1(t *testing.T) {
	today := fixedToday()
	data := parityFixture(today, 1, "")
	html := renderStaysHTML(t, data)
	frag := staysParityFragments(html)
	assertGolden(t, "stays_page1.html", frag)
}

func TestParityStaysPage2(t *testing.T) {
	today := fixedToday()
	data := parityFixture(today, 2, "")
	html := renderStaysHTML(t, data)
	frag := staysParityFragments(html)
	assertGolden(t, "stays_page2.html", frag)
}

func TestParityStaysReportFailed(t *testing.T) {
	today := fixedToday()
	data := parityFixture(today, 1, "failed")
	for i := range data.View.Rows {
		data.View.Rows[i].Progress.Status = "failed"
	}
	html := renderStaysHTML(t, data)
	frag := staysParityFragments(html)
	assertGolden(t, "stays_report_failed.html", frag)
}
