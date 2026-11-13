package hostweb

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

const csrfTestSecret = "hostweb-test-secret-key-0123456789abcdef"

var csrfTestNow = time.Date(2026, 11, 13, 12, 0, 0, 0, time.UTC)

func csrfTestEnv(k string) string {
	switch k {
	case "UBYHOST_SECRET_KEY":
		return csrfTestSecret
	case "UBYHOST_PUBLIC_BASE_URL":
		return "https://app.example.test"
	}
	return ""
}

// csrfPair is a CSRF cookie and the signed token that matches it.
func csrfPair(t *testing.T) (*http.Cookie, string) {
	t.Helper()
	cookie := "hostweb-csrf-cookie"
	sum := sha256.Sum256([]byte(cookie))
	token, err := secure.NewTimedSerializer(csrfTestSecret, csrfSalt).Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, csrfTestNow)
	if err != nil {
		t.Fatal(err)
	}
	return &http.Cookie{Name: csrfCookie, Value: cookie}, token
}

// multipartBody is a multipart form with the given fields and one small file part.
func multipartBody(t *testing.T, fields map[string]string, fileSize int) (*bytes.Buffer, string) {
	t.Helper()
	var buf bytes.Buffer
	mw := multipart.NewWriter(&buf)
	for k, v := range fields {
		if err := mw.WriteField(k, v); err != nil {
			t.Fatal(err)
		}
	}
	fw, err := mw.CreateFormFile("photo", "p.jpg")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := fw.Write(bytes.Repeat([]byte{0xff}, fileSize)); err != nil {
		t.Fatal(err)
	}
	if err := mw.Close(); err != nil {
		t.Fatal(err)
	}
	return &buf, mw.FormDataContentType()
}

func TestCSRFFormBodies(t *testing.T) {
	ck, token := csrfPair(t)
	cases := []struct {
		name   string
		body   func() (*bytes.Buffer, string)
		wantOK bool
	}{
		{"url-encoded token", func() (*bytes.Buffer, string) {
			return bytes.NewBufferString(url.Values{csrfField: {token}, "name": {"x"}}.Encode()), "application/x-www-form-urlencoded"
		}, true},
		{"multipart token", func() (*bytes.Buffer, string) {
			return multipartBody(t, map[string]string{csrfField: token, "name": "x"}, 2<<20)
		}, true},
		{"multipart without token", func() (*bytes.Buffer, string) {
			return multipartBody(t, map[string]string{"name": "x"}, 10)
		}, false},
		{"multipart wrong token", func() (*bytes.Buffer, string) {
			return multipartBody(t, map[string]string{csrfField: "bad"}, 10)
		}, false},
		{"multipart over the cap", func() (*bytes.Buffer, string) {
			return multipartBody(t, map[string]string{csrfField: token}, csrfMaxMultipart+1)
		}, false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			body, contentType := c.body()
			req := httptest.NewRequest(http.MethodPost, "https://app.example.test/apartments/1", body)
			req.Header.Set("Content-Type", contentType)
			req.Header.Set("Origin", "https://app.example.test")
			req.AddCookie(ck)
			rec := httptest.NewRecorder()
			ok := CSRF(rec, req, csrfTestEnv, csrfTestNow)
			if ok != c.wantOK {
				t.Fatalf("CSRF = %v, want %v (code %d)", ok, c.wantOK, rec.Code)
			}
			if ok && req.PostForm.Get("name") != "x" {
				t.Fatalf("handler lost the form: name=%q", req.PostForm.Get("name"))
			}
			if !ok && rec.Code != http.StatusSeeOther {
				t.Fatalf("refused same-site post got %d, want 303", rec.Code)
			}
		})
	}
	t.Run("multipart file stays readable", func(t *testing.T) {
		body, contentType := multipartBody(t, map[string]string{csrfField: token}, 1234)
		req := httptest.NewRequest(http.MethodPost, "https://app.example.test/apartments/1", body)
		req.Header.Set("Content-Type", contentType)
		req.AddCookie(ck)
		if !CSRF(httptest.NewRecorder(), req, csrfTestEnv, csrfTestNow) {
			t.Fatal("CSRF refused a valid multipart post")
		}
		f, h, err := req.FormFile("photo")
		if err != nil {
			t.Fatal(err)
		}
		defer f.Close()
		if h.Size != 1234 || !strings.HasSuffix(h.Filename, ".jpg") {
			t.Fatalf("file part %q size %d", h.Filename, h.Size)
		}
	})
}
