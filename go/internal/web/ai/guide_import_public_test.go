package ai

import (
	"net/url"
	"strings"
	"testing"
)

func TestGuidePublicURLRefusals(t *testing.T) {
	cases := map[string]string{
		"http://www.example.test/p":        guidePublicURLErr,
		"https://h.cz:8443/x":              guidePublicURLErr,
		"https://u:p@h.cz/p":               guidePublicURLErr,
		"https://192.168.1.1/p":            guidePublicURLErr,
		"https://h.cz/p\u00e9":             guidePublicURLErr,
		"https://h.cz/" + strings.Repeat("a", 2040): guidePublicURLErr,
	}
	for raw, want := range cases {
		if _, err := guidePublicURL(raw); guideErrKey(err) != want {
			t.Errorf("%q: got %q want %q", raw[:min(40, len(raw))], guideErrKey(err), want)
		}
	}
	link, err := guidePublicURL("https://www.notion.so/workspace/Guide-abc")
	if err != nil || link.Source != "url" || !strings.HasPrefix(link.URL, "https://www.notion.so/") {
		t.Errorf("valid: %+v err=%v", link, err)
	}
}

func TestGuideImportPublicURLRoute(t *testing.T) {
	w := newGuideCardWorld(t)
	path := "/apartments/" + itoa64(w.apt) + "/guide"
	importPath := path + "/import"
	on := map[string]string{"UBYHOST_APIFY_TOKEN": "t"}
	mux := guideTestMux(w.s.pool, on)
	count := func() int64 {
		return guideTestCount(t, w.s.pool, `SELECT COUNT(*) FROM guide_import WHERE apartment_id = $1 AND source = 'url'`, w.apt)
	}
	ok := "https://www.notion.so/host/p"
	rec := guideTestDo(t, mux, "POST", importPath, w.host, url.Values{"public_url": {ok}})
	if rec.Code != 303 || !strings.Contains(rec.Header().Get("Location"), "?msg=") || count() != 1 {
		t.Fatalf("queue: %d loc=%q n=%d", rec.Code, rec.Header().Get("Location"), count())
	}
	for _, raw := range []string{"http://x.test/", "https://h.cz:8443", "https://u:p@h.cz", "https://1.2.3.4/x"} {
		n0 := count()
		rec := guideTestDo(t, mux, "POST", importPath, w.host, url.Values{"public_url": {raw}})
		if !strings.Contains(rec.Header().Get("Location"), "?err=") || count() != n0 {
			t.Errorf("%q: loc=%q rows=%d", raw, rec.Header().Get("Location"), count())
		}
	}
	guideTestExec(t, w.s.pool, `UPDATE guide_import SET status = 'used' WHERE apartment_id = $1 AND source = 'url'`, w.apt)
	rec = guideTestDo(t, mux, "POST", importPath, w.host, url.Values{"public_url": {ok}})
	if !strings.Contains(rec.Header().Get("Location"), "?err=") {
		t.Errorf("second import: %s", rec.Header().Get("Location"))
	}
	guideTestExec(t, w.s.pool, `UPDATE guide_import SET status = 'used', codes_left_out = 3 WHERE apartment_id = $1 AND source = 'url'`, w.apt)
	body := guideTestDo(t, mux, "GET", path, w.host, nil).Body.String()
	if !strings.Contains(body, "Codes and passwords left out: 3") || strings.Contains(body, "4827") {
		t.Errorf("notice missing or leaked code")
	}
	if rec := guideTestDo(t, mux, "GET", path, w.stranger, nil); rec.Code != 404 {
		t.Errorf("foreign apt: %d", rec.Code)
	}
}