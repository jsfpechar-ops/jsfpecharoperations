package guest

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

type formPagesGolden struct {
	Now       string                `json:"now"`
	Token     string                `json:"token"`
	PinToken  string                `json:"pin_token"`
	StayID    int64                 `json:"stay_id"`
	StayPinID int64                 `json:"stay_pin_id"`
	AdultID   int64                 `json:"adult_id"`
	MinorID   int64                 `json:"minor_id"`
	ForeignID int64                 `json:"foreign_id"`
	Cases     []formPagesGoldenCase `json:"cases"`
}

type formPagesGoldenCase struct {
	Name     string   `json:"name"`
	Method   string   `json:"method"`
	Path     string   `json:"path"`
	Lang     string   `json:"lang"`
	Status   int      `json:"status"`
	Location string   `json:"location"`
	Lines    []string `json:"lines"`
}

func loadFormPagesGolden(t *testing.T) formPagesGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/form_pages_golden.json")
	if err != nil {
		t.Fatalf("golden: %v", err)
	}
	var g formPagesGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestFormPagesGoldenFile(t *testing.T) {
	g := loadFormPagesGolden(t)
	if len(g.Cases) != 8 {
		t.Fatalf("cases: got %d want 8", len(g.Cases))
	}
	for _, c := range g.Cases {
		if c.Method == "" || c.Name == "" {
			t.Fatalf("case shape: %+v", c)
		}
	}
}

func TestFormPagesGoldenShape(t *testing.T) {
	g := loadFormPagesGolden(t)
	wantGET := map[string]int{
		"new_en": 200, "new_cs": 200, "edit_adult": 200, "edit_minor": 200,
		"edit_foreigner": 200, "remove_confirm": 200,
	}
	for _, c := range g.Cases {
		if exp, ok := wantGET[c.Name]; ok {
			if c.Status != exp {
				t.Errorf("%s status %d want %d", c.Name, c.Status, exp)
			}
			if len(c.Lines) < 30 {
				t.Errorf("%s lines %d", c.Name, len(c.Lines))
			}
		}
		if c.Name == "remove_post" || c.Name == "relang_cs" {
			if c.Status == 0 {
				t.Errorf("%s missing status", c.Name)
			}
		}
	}
}

func TestFormPagesRoutePattern(t *testing.T) {
	mux := http.NewServeMux()
	RegisterFormPages(mux, nil, nil, nil, func(_ string, h http.HandlerFunc) http.Handler { return h })
	cases := []struct{ method, path, pattern string }{
		{http.MethodGet, "/l/tok/1/new", "GET /l/{token}/{reservation_id}/new"},
		{http.MethodGet, "/l/tok/1/edit/2", "GET /l/{token}/{reservation_id}/edit/{guest_id}"},
		{http.MethodGet, "/l/tok/1/remove/2", "GET /l/{token}/{reservation_id}/remove/{guest_id}"},
		{http.MethodPost, "/l/tok/1/remove/2", "POST /l/{token}/{reservation_id}/remove/{guest_id}"},
		{http.MethodPost, "/l/tok/1/relang", "POST /l/{token}/{reservation_id}/relang"},
	}
	for _, c := range cases {
		req := httptest.NewRequest(c.method, c.path, nil)
		req.SetPathValue("token", "tok")
		req.SetPathValue("reservation_id", "1")
		req.SetPathValue("guest_id", "2")
		_, pattern := mux.Handler(req)
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q", c.method, c.path, pattern)
		}
	}
}

// formPagesVisibleLines must stay aligned with visible_lines() in App/scripts/go_form_pages_golden.py.
func formPagesVisibleLines(page string) []string {
	idx := strings.Index(page, `class="g-wrap`)
	start := strings.LastIndex(page[:idx+1], "<div")
	if idx < 0 || start < 0 {
		return nil
	}
	page = page[start:]
	if end := strings.Index(page, `<div class="g-page-skeleton"`); end >= 0 {
		page = page[:end]
	}
	// Minimal normaliser: keep tags with class= and form fields for parity tests.
	var out []string
	for _, line := range strings.Split(page, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		if strings.Contains(line, "class=") || strings.Contains(line, "<form") || strings.Contains(line, "g-checkin") {
			out = append(out, line)
		}
	}
	return out
}

func TestFormPagesVisibleLinesHelper(t *testing.T) {
	sample := "<div class=\"g-wrap x\">\n<div class=\"g-checkin-main\">\n<form id=\"guest-form\" method=\"post\"></form>\n</div>\n<div class=\"g-page-skeleton\"></div>"
	lines := formPagesVisibleLines(sample)
	if len(lines) < 2 {
		t.Fatalf("lines %v", lines)
	}
}

func TestFormPagesRegisterNilPool(t *testing.T) {
	mux := http.NewServeMux()
	RegisterFormPages(mux, nil, func(string) string { return "" }, nil, func(_ string, h http.HandlerFunc) http.Handler { return h })
	req := httptest.NewRequest(http.MethodGet, "/l/tok/9/new", nil)
	req.SetPathValue("token", "tok")
	req.SetPathValue("reservation_id", "9")
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusInternalServerError {
		t.Fatalf("nil pool: status %d", rec.Code)
	}
}
