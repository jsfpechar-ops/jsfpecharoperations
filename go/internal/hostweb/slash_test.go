package hostweb

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestCanonicalSlash(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /reservations/{reservation_id}", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("detail"))
	})
	mux.HandleFunc("POST /reservations/{reservation_id}", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("posted"))
	})
	mux.HandleFunc("GET /reservations", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("list"))
	})
	mux.HandleFunc("GET /static/", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("static"))
	})
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		NotFoundPage(w, r)
	})

	wrapped := CanonicalSlash(mux, mux)

	tests := []struct {
		name         string
		method       string
		path         string
		query        string
		accept       string
		wantCode     int
		wantRedirect string
	}{
		{
			name:         "redirect trailing slash to detail route",
			method:       "GET",
			path:         "/reservations/7/",
			wantCode:     http.StatusTemporaryRedirect,
			wantRedirect: "/reservations/7",
		},
		{
			name:         "redirect trailing slash preserves query",
			method:       "GET",
			path:         "/reservations/7/",
			query:        "return_to=%2F",
			wantCode:     http.StatusTemporaryRedirect,
			wantRedirect: "/reservations/7?return_to=%2F",
		},
		{
			name:         "redirect trailing slash preserves POST method",
			method:       "POST",
			path:         "/reservations/7/",
			wantCode:     http.StatusTemporaryRedirect,
			wantRedirect: "/reservations/7",
		},
		{
			name:     "root path unchanged",
			method:   "GET",
			path:     "/",
			wantCode: http.StatusNotFound,
		},
		{
			name:     "unknown path with trailing slash falls through",
			method:   "GET",
			path:     "/nope/",
			accept:   "text/html",
			wantCode: http.StatusNotFound,
		},
		{
			name:     "subtree route with trailing slash unchanged",
			method:   "GET",
			path:     "/static/app.css/",
			wantCode: http.StatusOK,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(tt.method, "http://example.com"+tt.path, nil)
			if tt.query != "" {
				req.URL.RawQuery = tt.query
			}
			if tt.accept != "" {
				req.Header.Set("Accept", tt.accept)
			}
			w := httptest.NewRecorder()
			wrapped.ServeHTTP(w, req)

			if w.Code != tt.wantCode {
				t.Errorf("code = %d, want %d", w.Code, tt.wantCode)
			}
			if tt.wantRedirect != "" {
				loc := w.Header().Get("Location")
				if loc != tt.wantRedirect {
					t.Errorf("redirect = %q, want %q", loc, tt.wantRedirect)
				}
			}
		})
	}
}
