package ai

import (
	"context"
	"net/url"
	"strings"
	"testing"
)

func TestGuideExternalURLValidator(t *testing.T) {
	long := "https://www.notion.so/" + strings.Repeat("a", 2049-len("https://www.notion.so/"))
	cases := []struct {
		raw string
		ok  bool
	}{
		{"https://www.notion.so/x?y=1", true},
		{"http://example.com/", false},
		{"javascript:alert(1)", false},
		{"https://u:p@h.cz", false},
		{"https://h.cz:8443", false},
		{"https://1.2.3.4/", false},
		{"https://localhost/", false},
		{long, false},
		{"https://www.notion.so/a\u00a0b", false},
		{"", true},
		{"   ", true},
	}
	for _, c := range cases {
		_, _, ok := guideExternalURL(c.raw)
		if ok != c.ok {
			t.Errorf("guideExternalURL(%q) ok=%v want %v", c.raw, ok, c.ok)
		}
	}
	clean, host, ok := guideExternalURL("https://WWW.Notion.So/Page")
	if !ok || host != "www.notion.so" || !strings.HasPrefix(clean, "https://") {
		t.Errorf("accept = %q %q %v", clean, host, ok)
	}
}

func TestGuideExternalSaveAndIndex(t *testing.T) {
	w := newGuideCardWorld(t)
	ctx := context.Background()
	path := w.path("/external")
	good := "https://www.notion.so/page"
	id := itoa64(w.apt)
	readURL := func() string {
		var v string
		if err := w.pool.QueryRow(ctx, `SELECT COALESCE(guide_external_url, '') FROM apartment WHERE id = $1`, w.apt).Scan(&v); err != nil {
			t.Fatal(err)
		}
		return v
	}
	rec := guideTestDo(t, w.mux, "POST", path, w.host, url.Values{"guide_external_url": {good}})
	loc := location(rec)
	if rec.Code != 303 || !strings.Contains(loc, "?msg=") || !strings.HasSuffix(loc, "#external") {
		t.Fatalf("save: %d %q", rec.Code, loc)
	}
	if got := readURL(); got != good {
		t.Errorf("column after save = %q", got)
	}
	if n := guideTestCount(t, w.pool, `SELECT COUNT(*) FROM audit WHERE action = 'guide_external_url_set' AND detail = $1`, "apartment="+id+" host=www.notion.so"); n != 1 {
		t.Errorf("audit rows for set: %d", n)
	}
	if n := guideTestCount(t, w.pool, `SELECT COUNT(*) FROM audit WHERE action = 'guide_external_url_set' AND detail LIKE $1`, "%/page%"); n != 0 {
		t.Error("audit must not carry the URL path")
	}
	body := guideTestDo(t, w.mux, "GET", w.path(), w.host, nil).Body.String()
	if !strings.Contains(body, `data-guide-external`) || !strings.Contains(body, "www.notion.so") {
		t.Error("index should show the saved domain")
	}
	if !strings.Contains(body, `id="external"`) || !strings.Contains(body, `name="guide_external_url"`) {
		t.Error("index should show the external section")
	}
	rec = guideTestDo(t, w.mux, "POST", path, w.host, url.Values{"guide_external_url": {"https://h.cz:8443"}})
	loc = location(rec)
	if !strings.Contains(loc, "?err=") || !strings.HasSuffix(loc, "#external") || readURL() != good {
		t.Errorf("bad POST: %q column=%q", loc, readURL())
	}
	rec = guideTestDo(t, w.mux, "POST", path, w.host, url.Values{"action": {"clear"}})
	loc = location(rec)
	if !strings.Contains(loc, "?msg=") || !strings.HasSuffix(loc, "#external") {
		t.Errorf("clear: %q", loc)
	}
	if readURL() != "" {
		t.Errorf("column after clear = %q", readURL())
	}
	if rec := guideTestDo(t, w.mux, "POST", path, w.stranger, url.Values{"guide_external_url": {good}}); rec.Code != 404 {
		t.Errorf("foreign save: %d", rec.Code)
	}
}
