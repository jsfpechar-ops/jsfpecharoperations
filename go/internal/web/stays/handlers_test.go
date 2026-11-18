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
