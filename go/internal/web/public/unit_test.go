package public

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestLegalLinks(t *testing.T) {
	for in, want := range map[string]string{
		"/dpa":                      `<a href="/dpa">/dpa</a>`,
		"see /legal.":               `see <a href="/legal">/legal</a>.`,
		"(/terms) and /privacy, x":  `(<a href="/terms">/terms</a>) and <a href="/privacy">/privacy</a>, x`,
		"a/dpa /dpax /dpa/ x/legal": "a/dpa /dpax /dpa/ x/legal",
		"/subprocessors;/dpa":       `<a href="/subprocessors">/subprocessors</a>;/dpa`,
		"na\u00a0/dpa":              "na\u00a0" + `<a href="/dpa">/dpa</a>`,
		"/dpa /legal":               `<a href="/dpa">/dpa</a> <a href="/legal">/legal</a>`,
	} {
		if got := legalLinks(in); got != want {
			t.Errorf("legalLinks(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestResolveLang(t *testing.T) {
	signedIn := func(*http.Request) bool { return true }
	for _, c := range []struct {
		url, cookie string
		in          func(*http.Request) bool
		want        string
	}{
		{"/terms", "", nil, "cs"},
		{"/terms", "", signedIn, "en"},
		{"/terms?lang=EN-gb", "", signedIn, "en"},
		{"/terms?lang=xx", "cs", nil, "cs"},
		{"/terms?lang=vi", "", nil, "en"},
		{"/terms", "vi", nil, "en"},
		{"/terms?lang=cs", "en", signedIn, "cs"},
	} {
		req := httptest.NewRequest(http.MethodGet, c.url, nil)
		if c.cookie != "" {
			req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: c.cookie})
		}
		if got := resolveLang(req, c.in); got != c.want {
			t.Errorf("%s cookie %q: %s, want %s", c.url, c.cookie, got, c.want)
		}
	}
}

func TestRecipientIDs(t *testing.T) {
	for _, c := range []struct {
		env  map[string]string
		want string
	}{
		{map[string]string{}, "police municipality ttlock push"},
		{map[string]string{"UBYHOST_WEB_PUSH": "no"}, "police municipality ttlock"},
		{map[string]string{"UBYHOST_SIGNUP_ENABLED": "1"}, "google_ads police municipality ttlock push"},
		{map[string]string{"UBYHOST_SIGNUP_ENABLED": "true", "UBYHOST_META_DATASET_ID": "1", "UBYHOST_META_ACCESS_TOKEN": "x"},
			"google_ads meta_ads police municipality ttlock push"},
	} {
		got := strings.Join(recipientIDs(loadConfig(func(k string) string { return c.env[k] })), " ")
		if got != c.want {
			t.Errorf("%v: %q, want %q", c.env, got, c.want)
		}
	}
}

func TestEffectiveDateText(t *testing.T) {
	if got := effectiveDateText("2026-10-05", "cs"); got != "5. října 2026" {
		t.Errorf("cs: %q", got)
	}
	if got := effectiveDateText("2027-01-31", "en"); got != "31 January 2027" {
		t.Errorf("en: %q", got)
	}
}
