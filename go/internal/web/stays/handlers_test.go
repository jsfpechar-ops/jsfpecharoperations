package stays

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestRegisterRoutesGET(t *testing.T) {
	mux := http.NewServeMux()
	Register(mux, nil, func(string) string { return "" }, func() time.Time { return fixedToday() },
		func(_ string, h http.HandlerFunc) http.Handler { return h })
	req := httptest.NewRequest(http.MethodGet, "/reservations", nil)
	if h, p := mux.Handler(req); h == nil || p == "" {
		t.Fatalf("no GET handler pattern=%q", p)
	}
	req = httptest.NewRequest(http.MethodPost, "/reservations", nil)
	if h, p := mux.Handler(req); h == nil || p == "" {
		t.Fatalf("no POST handler pattern=%q", p)
	}
}

func TestStaysListRendersPortalSourceLabels(t *testing.T) {
	rows := parityRows(fixedToday())
	rows[0].Reservation.Source = "airbnb"
	rows[1].Reservation.Source = "booking"
	data := parityFixture(fixedToday(), 1, "")
	data.View.Rows = rows[:2]
	data.Groups = groupRows(data.View.Rows, data.Today)
	data.Lang = "en"
	html := renderStaysHTML(t, data)
	for _, label := range []string{"Airbnb", "Booking.com"} {
		if !strings.Contains(html, label) {
			t.Fatalf("html missing portal label %q", label)
		}
	}
	for _, raw := range []string{"stays.source.airbnb", "stays.source.booking"} {
		if strings.Contains(html, raw) {
			t.Fatalf("html contains raw i18n key %q", raw)
		}
	}
}

func TestStaysListTemplateRenderMarkers(t *testing.T) {
	data := parityFixture(fixedToday(), 1, "")
	html := renderStaysHTML(t, data)
	for _, needle := range []string{
		`data-filter-panel`,
		`data-stays-more`,
		`stays-pager ph-hide`,
		`settings-pills`,
		`add-stay-panel`,
		`tbody class="stays-list"`,
		`stays-index-card`,
	} {
		if !strings.Contains(html, needle) {
			t.Fatalf("render missing %q", needle)
		}
	}
}
