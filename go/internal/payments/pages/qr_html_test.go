package pages

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestHostQRDispatchPNG(t *testing.T) {
	png := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("X-Kind", "png")
	})
	page := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("X-Kind", "html")
	})
	h := HostQRDispatch(png, page)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/payments/qr/10.png", nil)
	req.SetPathValue("file", "10.png")
	h.ServeHTTP(rec, req)
	if rec.Header().Get("X-Kind") != "png" {
		t.Fatalf("png branch: got %q", rec.Header().Get("X-Kind"))
	}
}

func TestHostQRDispatchHTML(t *testing.T) {
	png := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("X-Kind", "png")
	})
	page := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("X-Kind", "html")
	})
	h := HostQRDispatch(png, page)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/payments/qr/10", nil)
	req.SetPathValue("file", "10")
	h.ServeHTTP(rec, req)
	if rec.Header().Get("X-Kind") != "html" {
		t.Fatalf("html branch: got %q", rec.Header().Get("X-Kind"))
	}
}

func TestGuestPayDispatch(t *testing.T) {
	png := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("X-Kind", "png")
	})
	page := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("X-Kind", "html")
	})
	h := GuestPayDispatch(png, page)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/pay/9/abc.png", nil)
	req.SetPathValue("id", "9")
	req.SetPathValue("file", "abc.png")
	h.ServeHTTP(rec, req)
	if rec.Header().Get("X-Kind") != "png" {
		t.Fatalf("guest png: %q", rec.Header().Get("X-Kind"))
	}
	rec = httptest.NewRecorder()
	req = httptest.NewRequest(http.MethodGet, "/pay/9/abc", nil)
	req.SetPathValue("id", "9")
	req.SetPathValue("file", "abc")
	h.ServeHTTP(rec, req)
	if rec.Header().Get("X-Kind") != "html" {
		t.Fatalf("guest html: %q", rec.Header().Get("X-Kind"))
	}
}

func TestPayNoAccountText(t *testing.T) {
	if payNoAccountText("de") == payNoAccountText("xx") && payNoAccountText("xx") == "" {
		t.Fatal("expected en fallback")
	}
	if !contains(payNoAccountText("cs"), "Hostitel") {
		t.Fatal("cs string")
	}
}

func contains(s, sub string) bool {
	return len(s) >= len(sub) && (s == sub || len(sub) == 0 || stringIndex(s, sub) >= 0)
}

func stringIndex(s, sub string) int {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return i
		}
	}
	return -1
}
