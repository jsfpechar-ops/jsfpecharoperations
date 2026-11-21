package booking

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"
)

type cancelPDFsGolden struct {
	Now   string `json:"now"`
	Seed  []any  `json:"seed"`
	Cases []struct {
		Name        string `json:"name"`
		Method      string `json:"method"`
		Path        string `json:"path"`
		Status      int    `json:"status"`
		Location    string `json:"location,omitempty"`
		ContentType string `json:"content_type,omitempty"`
	} `json:"cases"`
}

func loadCancelPDFsGolden(t *testing.T) cancelPDFsGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/cancel_pdfs_golden.json")
	if err != nil {
		t.Fatalf("golden: %v", err)
	}
	var g cancelPDFsGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestCancelPDFsGoldenShape(t *testing.T) {
	g := loadCancelPDFsGolden(t)
	if len(g.Cases) == 0 {
		t.Fatal("no cases")
	}
	for _, c := range g.Cases {
		if c.Status == 0 {
			t.Errorf("%s: missing status", c.Name)
		}
		if c.Method == http.MethodPost && c.Status == http.StatusSeeOther && !strings.HasPrefix(c.Location, "/p/") {
			t.Errorf("%s: location %q", c.Name, c.Location)
		}
	}
}

func TestCancelPDFsRoutes(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	seed(t, pool, g)
	env := map[string]string{"UBYHOST_SECRET_KEY": g.Secret}
	mux := http.NewServeMux()
	RegisterCancelPDFs(mux, pool, func(k string) string { return env[k] }, func() time.Time { return mustTime(t, g.Now) }, func(_ string, h http.HandlerFunc) http.Handler { return h })
	token := ManageToken(g.Secret, 501)
	bad := token + "x"
	for _, c := range []struct {
		method, path string
		want         int
	}{
		{http.MethodPost, "/p/old-town/b/501/" + bad + "/cancel", http.StatusNotFound},
		{http.MethodGet, "/p/old-town/b/501/" + bad + "/invoice.pdf", http.StatusNotFound},
		{http.MethodGet, "/p/old-town/b/501/" + token + "/correction.pdf", http.StatusNotFound},
	} {
		req := httptest.NewRequest(c.method, c.path, nil)
		req.RemoteAddr = "203.0.113.9:1"
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, req)
		if rec.Code != c.want {
			t.Errorf("%s %s: %d", c.method, c.path, rec.Code)
		}
	}
}

func TestGuestCancelIdempotentNotCancellable(t *testing.T) {
	url := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if url == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL unset")
	}
	pool := testPool(t)
	g := loadGolden(t)
	seed(t, pool, g)
	ctx := t.Context()
	now := mustTime(t, g.Now)
	_, err := GuestCancel(ctx, pool, 502, now, nil)
	if err != nil {
		t.Fatal(err)
	}
	res, err := GuestCancel(ctx, pool, 502, now, nil)
	if err != nil {
		t.Fatal(err)
	}
	if res.Error != "not_cancellable" {
		t.Fatalf("second cancel: %v", res)
	}
}
