package public

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// The ČÚZK credit (brief 1700e) is on /legal once, in both languages, and on no
// other public page. The expected text is written out on purpose: changing
// ruian.Attribution must fail this test and the legal golden pages together.
func TestLegalShowsRuianCreditOnce(t *testing.T) {
	const credit = "Adresní data: ČÚZK, RÚIAN (CC BY 4.0)"
	get := func(path, lang string) string {
		req := httptest.NewRequest(http.MethodGet, path+"?lang="+lang, nil)
		rec := httptest.NewRecorder()
		Handler(path, Deps{Getenv: func(string) string { return "" }})(rec, req)
		if rec.Code != http.StatusOK {
			t.Fatalf("%s?lang=%s: status %d", path, lang, rec.Code)
		}
		return rec.Body.String()
	}
	for _, lang := range []string{"cs", "en"} {
		if n := strings.Count(get("/legal", lang), credit); n != 1 {
			t.Errorf("/legal?lang=%s shows the credit %d times, want 1", lang, n)
		}
		for _, path := range []string{"/privacy", "/terms", "/dpa", "/subprocessors"} {
			if n := strings.Count(get(path, lang), credit); n != 0 {
				t.Errorf("%s?lang=%s shows the credit %d times, want 0", path, lang, n)
			}
		}
	}
}
