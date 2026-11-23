package booking

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func pageMux() *http.ServeMux {
	mux := http.NewServeMux()
	mux.Handle("GET /terms/booking", TermsHandler())
	mux.Handle("GET /p/{slug}/thanks", ThanksHandler())
	return mux
}

func fetch(mux *http.ServeMux, method, path, cookie string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, path, nil)
	if cookie != "" {
		req.Header.Set("Cookie", cookie)
	}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

func TestTermsLanguageOrder(t *testing.T) {
	mux := pageMux()
	cases := []struct{ path, cookie, lang, title string }{
		{"/terms/booking", "", "cs", "<title>Podmínky rezervace · UbyHost</title>"},
		{"/terms/booking?lang=en", "", "en", "<title>Booking terms · UbyHost</title>"},
		{"/terms/booking", "ubyhost_lang=en", "en", "<title>Booking terms · UbyHost</title>"},
		{"/terms/booking?lang=cs", "ubyhost_lang=en", "cs", "<title>Podmínky rezervace · UbyHost</title>"},
		{"/terms/booking?lang=vi", "", "cs", "<title>Podmínky rezervace · UbyHost</title>"},
	}
	for _, c := range cases {
		rec := fetch(mux, "GET", c.path, c.cookie)
		body := rec.Body.String()
		if rec.Code != 200 || !strings.Contains(body, `<html lang="`+c.lang+`">`) || !strings.Contains(body, c.title) {
			t.Errorf("%s %q: code %d lang/title wrong", c.path, c.cookie, rec.Code)
		}
		if !strings.Contains(body, `hreflang="`+c.lang+`" lang="`+c.lang+`" aria-current="true"`) {
			t.Errorf("%s: aria-current missing on %s", c.path, c.lang)
		}
		if strings.Count(body, `" aria-current="true">`) != 1 {
			t.Errorf("%s: want exactly one aria-current", c.path)
		}
	}
}

func TestTermsIsAGuestPage(t *testing.T) {
	rec := fetch(pageMux(), "GET", "/terms/booking?lang=en", "")
	body := rec.Body.String()
	if got := rec.Header().Get("Set-Cookie"); got != "" {
		t.Errorf("no cookie may be set, got %q", got)
	}
	if ct := rec.Header().Get("Content-Type"); ct != "text/html; charset=utf-8" {
		t.Errorf("content type %q", ct)
	}
	for _, want := range []string{
		`<meta name="robots" content="noindex">`, `<body class="layout-host  no-nav">`,
		`<a class="skip-link" href="#main-content">`, `<main id="main-content" class="wrap  ">`,
		`<h1>Booking terms</h1>`, `.pp-bk-card`, `data-page-skeleton`, `id="unsaved-dialog"`,
	} {
		if !strings.Contains(body, want) {
			t.Errorf("missing %q", want)
		}
	}
	// Light mode, no third party: every script comes from /static/.
	for _, part := range strings.Split(body, "<script")[1:] {
		if !strings.HasPrefix(part, ` src="/static/`) {
			t.Errorf("script not from /static/: %.60s", part)
		}
	}
	if strings.Contains(body, "posthog") || strings.Contains(body, "turnstile") {
		t.Error("no analytics or third-party script on a booking page")
	}
	if strings.Contains(body, "host.js") || strings.Contains(body, "shell.js") {
		t.Error("host scripts must not load on a guest page")
	}
}

func TestHeadHasNoBody(t *testing.T) {
	rec := fetch(pageMux(), "HEAD", "/terms/booking", "")
	if rec.Code != 200 || rec.Body.Len() != 0 {
		t.Errorf("HEAD: %d with %d bytes", rec.Code, rec.Body.Len())
	}
}

func TestThanks(t *testing.T) {
	mux := pageMux()
	rec := fetch(mux, "GET", "/p/old-town/thanks?lang=en", "")
	body := rec.Body.String()
	if rec.Code != 200 || rec.Header().Get("X-Robots-Tag") != "noindex" {
		t.Fatalf("thanks: %d %q", rec.Code, rec.Header().Get("X-Robots-Tag"))
	}
	if !strings.Contains(body, `<a href="/p/old-town">`) || !strings.Contains(body, "<h1>") {
		t.Error("thanks page lacks the back link or h1")
	}
	// A slug cannot inject markup.
	rec = fetch(mux, "GET", "/p/%22%3E%3Cscript%3Ex%3C%2Fscript%3E/thanks", "")
	if strings.Contains(rec.Body.String(), `"><script>x`) {
		t.Error("slug was not escaped")
	}
}

func TestShellTranslatesBothLanguages(t *testing.T) {
	cs := Guest{Lang: "cs"}.T("a11y.skip_to_content")
	en := Guest{Lang: "en"}.T("a11y.skip_to_content")
	if cs == "" || en == "" || cs == en || cs == "a11y.skip_to_content" {
		t.Errorf("catalog lookup failed: %q %q", cs, en)
	}
}
