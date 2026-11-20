package properties

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestSmartLocksReturnTo(t *testing.T) {
	r := httptest.NewRequest(http.MethodPost, "/smart-locks/setup", nil)
	r.PostForm = map[string][]string{"return_to": {"/apartments/5"}}
	if got := smartLocksReturnTo(r, "/smart-locks"); got != "/apartments/5" {
		t.Fatalf("got %q", got)
	}
	r = httptest.NewRequest(http.MethodPost, "/smart-locks/setup", strings.NewReader(""))
	r.PostForm = map[string][]string{"return_to": {"https://evil.example/x"}}
	if got := smartLocksReturnTo(r, "/smart-locks"); got != "/smart-locks" {
		t.Fatalf("unsafe: %q", got)
	}
}

func TestSmartLocksSection(t *testing.T) {
	r := httptest.NewRequest(http.MethodPost, "/smart-locks/refresh", nil)
	r.PostForm = map[string][]string{"section": {"share"}}
	if smartLocksSection(r, true) != "share" {
		t.Fatal("share")
	}
	if smartLocksSection(httptest.NewRequest(http.MethodPost, "/smart-locks/refresh", nil), true) != "list" {
		t.Fatal("default list")
	}
	if smartLocksSection(httptest.NewRequest(http.MethodPost, "/smart-locks/refresh", nil), false) != "share" {
		t.Fatal("default share")
	}
}