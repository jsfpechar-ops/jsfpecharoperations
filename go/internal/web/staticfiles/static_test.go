package staticfiles

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func TestRegisterServesFileWithVersionedCache(t *testing.T) {
	root := t.TempDir()
	staticDir := filepath.Join(root, "static")
	if err := os.MkdirAll(staticDir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(staticDir, "probe.txt"), []byte("ok"), 0o644); err != nil {
		t.Fatal(err)
	}
	t.Setenv("UBYHOST_APP_ROOT", root)

	mux := http.NewServeMux()
	Register(mux, os.Getenv, nil)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/static/probe.txt?v=1", nil)
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
	}
	if got := rec.Header().Get("Cache-Control"); got != cacheVersioned {
		t.Fatalf("cache=%q want versioned", got)
	}
	if rec.Body.String() != "ok" {
		t.Fatalf("body=%q", rec.Body.String())
	}
}

func TestRegisterDirectoryListing404(t *testing.T) {
	root := t.TempDir()
	staticDir := filepath.Join(root, "static")
	platforms := filepath.Join(staticDir, "platforms")
	if err := os.MkdirAll(platforms, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(staticDir, "tokens.css"), []byte("/* tok */"), 0o644); err != nil {
		t.Fatal(err)
	}
	t.Setenv("UBYHOST_APP_ROOT", root)
	mux := http.NewServeMux()
	Register(mux, os.Getenv, nil)
	for _, path := range []string{"/static/", "/static/platforms/"} {
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, path, nil))
		if rec.Code != http.StatusNotFound {
			t.Fatalf("%s: status=%d body=%s", path, rec.Code, rec.Body.String())
		}
	}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/static/tokens.css", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("tokens.css: status=%d", rec.Code)
	}
}

func TestRegisterSkipsWhenNoTree(t *testing.T) {
	t.Setenv("UBYHOST_APP_ROOT", "")
	mux := http.NewServeMux()
	Register(mux, func(string) string { return "" }, nil)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/static/missing.css", nil)
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status=%d", rec.Code)
	}
}
