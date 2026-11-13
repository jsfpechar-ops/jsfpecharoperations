package admingate

import (
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"
)

func TestAdminsOnlyTextsMatchPython(t *testing.T) {
	en, err := os.ReadFile("../../../../App/app/host_i18n.py")
	if err != nil {
		t.Fatal(err)
	}
	vi, err := os.ReadFile("../../../../App/app/host_vi_i18n.py")
	if err != nil {
		t.Fatal(err)
	}
	for lang, src := range map[string][]byte{"en": en, "cs": en, "vi": vi} {
		if !strings.Contains(string(src), `"auth.error.admins_only": "`+AdminsOnlyTexts[lang]+`"`) {
			t.Errorf("%s: auth.error.admins_only differs from the Python file", lang)
		}
	}
}

func TestNoCookieRedirectsToLogin(t *testing.T) {
	getenv := func(k string) string {
		if k == "UBYHOST_SECRET_KEY" {
			return "admingate-test-secret-0123456789-abcdef"
		}
		return ""
	}
	w := httptest.NewRecorder()
	r := httptest.NewRequest(http.MethodGet, "/admin/customers", nil)
	h, err := Require(w, r, nil, getenv, time.Unix(1798761600, 0))
	if h != nil || err != nil || w.Code != http.StatusSeeOther || w.Header().Get("Location") != "/login?next=/admin/customers" {
		t.Fatalf("got %v %v %d %q", h, err, w.Code, w.Header().Get("Location"))
	}
}
